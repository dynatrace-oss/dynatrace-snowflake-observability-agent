-- ============================================================================
-- Query Deep Dive dashboard simulation setup for DSOA telemetry validation
-- Creates synthetic workload to exercise ALL dashboard tiles.
--
-- Dashboard: Snowflake Query Deep Dive (9dbac33a-25ba-4192-b748-c8b6fe561c3b)
-- Required plugin: query_history
--
-- Objects created
--   Warehouse: DSOA_TEST_WH           (XSMALL, auto-suspend 60 s)
--   Database : DSOA_TEST_DB
--   Schema   : DSOA_TEST_DB.QUERY_HISTORY_TEST
--
--   Tables (source data for query patterns):
--     FACT_ORDERS          (~12 000 rows across 3+ micro-partitions)
--     FACT_EVENTS          (~8 000 rows — wide rows to stress bytes-scanned)
--     DIM_CUSTOMERS        (~1 000 rows)
--     STAGING_ORDERS       (transient, populated + truncated each run)
--
--   Stored procedures:
--     SP_WORKLOAD_CHILD()  called by SP_WORKLOAD_ROOT — exercises parent-child spans
--     SP_WORKLOAD_ROOT()   issues the full workload; called by task
--
--   Task:
--     T_QUERY_WORKLOAD     every 5 minutes via DSOA_TEST_WH
--
-- Dashboard tile coverage
--   Section 1 — Costly Repeated Queries
--     tile 1 (bytes scanned)    → repeated GROUP BY on FACT_ORDERS; same query_hash every run
--     tile 2 (spill)            → cross-join query that forces spill on XSMALL
--     tile 3 (bytes over time)  → above queries hitting QUERY_HISTORY_TEST DB
--
--   Section 2 — Table Performance Degradation
--     tile 5 (partition scan ratio) → full-scan GROUP BY on FACT_ORDERS (high ratio)
--     tile 6 (spill volumes)        → cross-join query above
--     tile 7 (cache hit rate)       → repeated identical SELECT forces result-cache hits
--
--   Section 3 — Query Acceleration
--     tiles 9-10 → Snowflake evaluates eligibility automatically for slow SELECTs.
--                  XSMALL warehouse + large table may not trigger eligibility; these
--                  tiles show real production eligibility data. No synthetic needed.
--
--   Section 4 — Multi-level Query Analysis
--     tile 12 (parent-child) → SP_WORKLOAD_ROOT calls SP_WORKLOAD_CHILD (CALL statement
--                               produces parent_query_id in QUERY_HISTORY)
--     tile 13 (operator stats) → queries must exceed slow_queries_threshold (set to 100 ms
--                                in conf/config-test-qa.yml) to get GET_QUERY_OPERATOR_STATS
--                                called; the GROUP BY + JOIN queries satisfy this
--
--   Section 5 — External Functions
--     tiles 15-16 → requires an actual remote service endpoint; not simulated here
--                   (external_function_total_invocations remains 0 unless real ext fns exist).
--                   Tiles will show real data if external functions are used in the account.
--
--   Section 6 — Query Origin & Security
--     tile 18 (client app)  → populated from session.client_application_id automatically;
--                              the task uses SnowSQL / Snowpark connector, which sets
--                              client.application.id to "SnowSQL" / connector name
--     tile 19 (auth type)   → populated from session.authentication_method automatically;
--                              reflects the method used by the DSOA service user
--
--   Section 7 — Cost Attribution & Data Transfer
--     tile 21 (credits by user/role) → credits_used_cloud_services on each query
--     tile 22 (credits by warehouse) → same, grouped by warehouse
--     tile 23 (cross-region transfer) → requires cross-cloud COPY INTO / SELECT;
--                                        not simulated (inbound/outbound bytes remain 0)
--
-- Agent threshold note
--   conf/config-test-qa.yml sets slow_queries_threshold: 100
--   This ensures operator stats are collected for any query > 100 ms, making
--   Section 4 tiles populate with the synthetic workload. In production,
--   restore to 5000-10000 ms to avoid excessive GET_QUERY_OPERATOR_STATS calls.
--
-- Cost: near-zero — XSMALL warehouse, auto-suspends in 60 s.
--       One 5-minute task run typically uses < 0.01 credits.
--
-- ============================================================================
-- CONFIGURATION REFERENCE (conf/config-<env>.yml → plugins.query_history)
-- ============================================================================
--
-- Key                          Default    Test-QA   Notes
-- ---------------------------  ---------  --------  ---------------------------
-- schedule                     */30 * *   (same)    How often the plugin runs.
--                              * * * UTC            Lower for faster data if
--                                                   needed (min: */5).
--
-- slow_queries_threshold       10000      100       Milliseconds. Queries that
--                                                   exceed this threshold get
--                                                   GET_QUERY_OPERATOR_STATS
--                                                   called, producing spans for
--                                                   Section 4 operator tiles.
--                                                   Set low (100-500) for sim;
--                                                   restore to 5000-10000 in
--                                                   production to limit costs.
--
-- slow_queries_to_analyze_limit 50        (same)    Cap on how many slow queries
--                                                   per agent run get operator
--                                                   stats fetched. Raise to 100+
--                                                   if Section 4 tiles are sparse
--                                                   under high query volume.
--
-- telemetry                    [metrics,  (same)    Remove items to disable
--                               logs,               specific signal types.
--                               biz_events,         e.g. remove "spans" to stop
--                               spans]              operator stat collection
--                                                   entirely (saves credits).
--
-- disabled_telemetry           []         []        Alternative: list types to
--                                                   suppress without removing
--                                                   from the telemetry array.
--
-- Example test-qa stanza:
--   plugins:
--     query_history:
--       slow_queries_threshold: 100        # low for sim — catches any query > 100 ms
--       slow_queries_to_analyze_limit: 50  # default; raise if spans tiles are sparse
--       telemetry:
--         - metrics
--         - logs
--         - biz_events
--         - spans
-- ============================================================================

-- ---- CONFIGURATION ---------------------------------------------------------
-- Edit these two values; leave everything else unchanged.
SET owner_role     = 'DTAGENT_QA_OWNER';   -- role that will own all objects
SET viewer_role    = 'DTAGENT_QA_VIEWER';  -- DSOA reader role (needs SELECT grants)
SET task_warehouse = 'DSOA_TEST_WH';       -- warehouse used by the task (created below)
-- ----------------------------------------------------------------------------

-- 1. Account-level grants that require ACCOUNTADMIN.
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE IDENTIFIER($owner_role);

-- 2. Create warehouse (XSMALL, auto-suspend) if it doesn't exist.
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE   = XSMALL
    AUTO_SUSPEND     = 60
    AUTO_RESUME      = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'DSOA simulation warehouse — XSMALL, auto-suspend 60 s';

USE ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE DSOA_TEST_WH TO ROLE IDENTIFIER($owner_role);
GRANT OPERATE ON WAREHOUSE DSOA_TEST_WH TO ROLE IDENTIFIER($owner_role);

-- 3. Create database owned by owner_role.
USE ROLE SYSADMIN;
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
USE ROLE ACCOUNTADMIN;
GRANT OWNERSHIP ON DATABASE DSOA_TEST_DB
    TO ROLE IDENTIFIER($owner_role) COPY CURRENT GRANTS;

-- 4. Everything else as owner_role.
USE ROLE IDENTIFIER($owner_role);
USE DATABASE DSOA_TEST_DB;
USE WAREHOUSE IDENTIFIER($task_warehouse);

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.QUERY_HISTORY_TEST;
USE SCHEMA DSOA_TEST_DB.QUERY_HISTORY_TEST;

-- ── Source tables ─────────────────────────────────────────────────────────

-- FACT_ORDERS: ~12 000 rows (3 batches of 4 000), wide enough to generate
--   non-trivial bytes_scanned and multiple micro-partitions.
CREATE OR REPLACE TABLE DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS (
    order_id      NUMBER,
    customer_id   NUMBER,
    region        VARCHAR(50),
    product_code  VARCHAR(100),
    quantity      NUMBER,
    unit_price    NUMBER(12, 4),
    discount_pct  NUMBER(5, 2),
    order_date    DATE,
    ship_date     DATE,
    status        VARCHAR(20),
    notes         VARCHAR(500),  -- wide column to increase bytes_scanned
    created_at    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Populate with 3 batches spread over different date ranges to get 3+ micro-partitions.
INSERT INTO DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
    (order_id, customer_id, region, product_code, quantity, unit_price, discount_pct,
     order_date, ship_date, status, notes)
SELECT
    SEQ4()                                              AS order_id,
    UNIFORM(1, 1000, RANDOM(42))                        AS customer_id,
    CASE MOD(SEQ4(), 5)
        WHEN 0 THEN 'US-EAST'
        WHEN 1 THEN 'US-WEST'
        WHEN 2 THEN 'EU-WEST'
        WHEN 3 THEN 'APAC'
        ELSE 'LATAM'
    END                                                 AS region,
    'PROD-' || LPAD(UNIFORM(1, 500, RANDOM(43))::VARCHAR, 6, '0') AS product_code,
    UNIFORM(1, 100, RANDOM(44))                         AS quantity,
    ROUND(UNIFORM(5, 500, RANDOM(45))::FLOAT, 2)        AS unit_price,
    ROUND(UNIFORM(0, 30, RANDOM(46))::FLOAT, 2)         AS discount_pct,
    DATEADD(DAY, -UNIFORM(1, 90, RANDOM(47)), CURRENT_DATE())  AS order_date,
    DATEADD(DAY,  UNIFORM(1, 10, RANDOM(48)), DATEADD(DAY, -UNIFORM(1, 90, RANDOM(47)), CURRENT_DATE())) AS ship_date,
    CASE MOD(SEQ4(), 3) WHEN 0 THEN 'COMPLETE' WHEN 1 THEN 'PENDING' ELSE 'SHIPPED' END AS status,
    RPAD('note_batch1_', 400, 'x')                      AS notes  -- ~400 bytes per row
FROM TABLE(GENERATOR(ROWCOUNT => 4000));

INSERT INTO DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
    (order_id, customer_id, region, product_code, quantity, unit_price, discount_pct,
     order_date, ship_date, status, notes)
SELECT
    4000 + SEQ4(),
    UNIFORM(1, 1000, RANDOM(52)),
    CASE MOD(SEQ4(), 5) WHEN 0 THEN 'US-EAST' WHEN 1 THEN 'US-WEST' WHEN 2 THEN 'EU-WEST'
        WHEN 3 THEN 'APAC' ELSE 'LATAM' END,
    'PROD-' || LPAD(UNIFORM(1, 500, RANDOM(53))::VARCHAR, 6, '0'),
    UNIFORM(1, 100, RANDOM(54)),
    ROUND(UNIFORM(5, 500, RANDOM(55))::FLOAT, 2),
    ROUND(UNIFORM(0, 30, RANDOM(56))::FLOAT, 2),
    DATEADD(DAY, -UNIFORM(91, 180, RANDOM(57)), CURRENT_DATE()),
    DATEADD(DAY,  UNIFORM(1, 10, RANDOM(58)), DATEADD(DAY, -UNIFORM(91, 180, RANDOM(57)), CURRENT_DATE())),
    CASE MOD(SEQ4(), 3) WHEN 0 THEN 'COMPLETE' WHEN 1 THEN 'PENDING' ELSE 'SHIPPED' END,
    RPAD('note_batch2_', 400, 'x')
FROM TABLE(GENERATOR(ROWCOUNT => 4000));

INSERT INTO DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
    (order_id, customer_id, region, product_code, quantity, unit_price, discount_pct,
     order_date, ship_date, status, notes)
SELECT
    8000 + SEQ4(),
    UNIFORM(1, 1000, RANDOM(62)),
    CASE MOD(SEQ4(), 5) WHEN 0 THEN 'US-EAST' WHEN 1 THEN 'US-WEST' WHEN 2 THEN 'EU-WEST'
        WHEN 3 THEN 'APAC' ELSE 'LATAM' END,
    'PROD-' || LPAD(UNIFORM(1, 500, RANDOM(63))::VARCHAR, 6, '0'),
    UNIFORM(1, 100, RANDOM(64)),
    ROUND(UNIFORM(5, 500, RANDOM(65))::FLOAT, 2),
    ROUND(UNIFORM(0, 30, RANDOM(66))::FLOAT, 2),
    DATEADD(DAY, -UNIFORM(181, 365, RANDOM(67)), CURRENT_DATE()),
    DATEADD(DAY,  UNIFORM(1, 10, RANDOM(68)), DATEADD(DAY, -UNIFORM(181, 365, RANDOM(67)), CURRENT_DATE())),
    CASE MOD(SEQ4(), 3) WHEN 0 THEN 'COMPLETE' WHEN 1 THEN 'PENDING' ELSE 'SHIPPED' END,
    RPAD('note_batch3_', 400, 'x')
FROM TABLE(GENERATOR(ROWCOUNT => 4000));

-- DIM_CUSTOMERS: 1 000 rows, used for JOIN queries.
CREATE OR REPLACE TABLE DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS (
    customer_id   NUMBER,
    customer_name VARCHAR(200),
    segment       VARCHAR(50),
    country       VARCHAR(50)
);
INSERT INTO DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS
SELECT
    SEQ4() + 1,
    'Customer ' || (SEQ4() + 1),
    CASE MOD(SEQ4(), 4) WHEN 0 THEN 'ENTERPRISE' WHEN 1 THEN 'SMB' WHEN 2 THEN 'STARTUP' ELSE 'PUBLIC' END,
    CASE MOD(SEQ4(), 5) WHEN 0 THEN 'US' WHEN 1 THEN 'DE' WHEN 2 THEN 'JP' WHEN 3 THEN 'BR' ELSE 'AU' END
FROM TABLE(GENERATOR(ROWCOUNT => 1000));

-- STAGING_ORDERS: transient staging table, populated + truncated each run to exercise INSERT/UPDATE/DELETE.
CREATE OR REPLACE TRANSIENT TABLE DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS (
    order_id    NUMBER,
    status      VARCHAR(20),
    updated_at  TIMESTAMP_LTZ
) DATA_RETENTION_TIME_IN_DAYS = 0;

-- ── Child stored procedure ────────────────────────────────────────────────
-- Called from SP_WORKLOAD_ROOT → produces a PARENT_QUERY_ID relationship
-- visible in Section 4 parent-child tile.
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_CHILD(run_ts VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    v_count NUMBER;
BEGIN
    -- Aggregation query that shows up as a child span with TableScan + Aggregate operators.
    SELECT COUNT(*) INTO :v_count FROM (
        SELECT
            region,
            COUNT(*)                    AS order_count,
            SUM(quantity * unit_price)  AS revenue,
            AVG(discount_pct)           AS avg_discount
        FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
        WHERE status = 'COMPLETE'
        GROUP BY region
        ORDER BY revenue DESC
    );

    -- DML in child proc: INSERT into staging, then UPDATE status.
    INSERT INTO DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS (order_id, status, updated_at)
    SELECT order_id, 'PROCESSED', CURRENT_TIMESTAMP()
    FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
    WHERE status = 'COMPLETE'
    LIMIT 100;

    UPDATE DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS
    SET    status = 'ARCHIVED', updated_at = CURRENT_TIMESTAMP()
    WHERE  updated_at < DATEADD(MINUTE, -1, CURRENT_TIMESTAMP());

    RETURN 'child done at ' || :run_ts;
END;
$$;

-- ── Root stored procedure ─────────────────────────────────────────────────
-- Issues a varied workload on each run to exercise all dashboard sections.
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_ROOT()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    run_ts  VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
    v_dummy NUMBER;
BEGIN

    -- ── Query 1: Full-table GROUP BY + JOIN (bytes_scanned, partition_scan_ratio)
    --   Identical SQL every run → same query_hash → accumulates in "costly repeated" tiles.
    --   Join to DIM_CUSTOMERS forces multi-table operator plan (TableScan + HashJoin operators).
    SELECT COUNT(*) INTO :v_dummy FROM (
        SELECT
            c.segment,
            o.region,
            COUNT(o.order_id)               AS order_count,
            SUM(o.quantity * o.unit_price)  AS total_revenue,
            AVG(o.discount_pct)             AS avg_discount,
            MAX(o.order_date)               AS latest_order
        FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS  o
        JOIN DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS c ON c.customer_id = o.customer_id
        GROUP BY c.segment, o.region
        ORDER BY total_revenue DESC
    );

    -- ── Query 2: Cross-join on a small set — forces spill on XSMALL
    --   50 rows × 50 rows = 2500 intermediate rows with wide FACT_ORDERS columns.
    SELECT COUNT(*) INTO :v_dummy FROM (
        SELECT
            a.notes || b.notes AS combined_notes,
            a.quantity * b.unit_price AS cross_value
        FROM (SELECT * FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS LIMIT 50) a
        CROSS JOIN (SELECT * FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS LIMIT 50) b
        WHERE LENGTH(a.notes) > 10
    );

    -- ── Query 3: Repeated identical SELECT (result-cache tile — Section 2 tile 7)
    --   Run twice to force a cache-hit on the second execution.
    SELECT COUNT(*) INTO :v_dummy
    FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS;

    SELECT COUNT(*) INTO :v_dummy
    FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS;

    -- ── Query 4: DELETE + INSERT to refresh staging (DML for operation variety)
    DELETE FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS;

    -- ── Child proc call → parent_query_id relationship (Section 4 tile 12)
    CALL DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_CHILD(:run_ts);

    RETURN 'workload complete at ' || :run_ts;
END;
$$;

-- ── Task ──────────────────────────────────────────────────────────────────
CREATE OR REPLACE TASK DSOA_TEST_DB.QUERY_HISTORY_TEST.T_QUERY_WORKLOAD
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '5 MINUTE'
    COMMENT   = 'DSOA Query Deep Dive dashboard simulation — runs every 5 minutes'
AS
    CALL DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_ROOT();

ALTER TASK DSOA_TEST_DB.QUERY_HISTORY_TEST.T_QUERY_WORKLOAD RESUME;

-- ── Grants to DSOA viewer role ─────────────────────────────────────────────
-- The query_history plugin reads from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY —
-- account-level view, no per-table grants needed. These grants allow DSOA to
-- read any monitoring or config views in this database if needed in the future.
GRANT USAGE    ON DATABASE DSOA_TEST_DB                                      TO ROLE IDENTIFIER($viewer_role);
GRANT USAGE    ON SCHEMA   DSOA_TEST_DB.QUERY_HISTORY_TEST                   TO ROLE IDENTIFIER($viewer_role);
GRANT SELECT   ON TABLE    DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS        TO ROLE IDENTIFIER($viewer_role);
GRANT SELECT   ON TABLE    DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS      TO ROLE IDENTIFIER($viewer_role);
GRANT SELECT   ON TABLE    DSOA_TEST_DB.QUERY_HISTORY_TEST.STAGING_ORDERS     TO ROLE IDENTIFIER($viewer_role);

-- ── Run once immediately so data appears in ACCOUNT_USAGE before waiting ──
CALL DSOA_TEST_DB.QUERY_HISTORY_TEST.SP_WORKLOAD_ROOT();

-- ── Verify setup ─────────────────────────────────────────────────────────
SHOW TASKS    IN SCHEMA DSOA_TEST_DB.QUERY_HISTORY_TEST;
SHOW TABLES   IN SCHEMA DSOA_TEST_DB.QUERY_HISTORY_TEST;

SELECT 'FACT_ORDERS row count' AS table_name, COUNT(*) AS row_count
FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.FACT_ORDERS
UNION ALL
SELECT 'DIM_CUSTOMERS', COUNT(*)
FROM DSOA_TEST_DB.QUERY_HISTORY_TEST.DIM_CUSTOMERS;

-- Check recent queries in ACCOUNT_USAGE (typically visible within 2-5 minutes).
-- Run this ~5 minutes after setup to confirm workload is being recorded.
/*
SELECT query_id, query_type, warehouse_name, total_elapsed_time,
       bytes_scanned, partitions_scanned, partitions_total, execution_status
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE query_text ILIKE '%QUERY_HISTORY_TEST%'
ORDER BY start_time DESC
LIMIT 20;
*/

-- ============================================================================
-- CLEANUP (run when done testing):
-- USE ROLE IDENTIFIER($owner_role);
-- ALTER TASK DSOA_TEST_DB.QUERY_HISTORY_TEST.T_QUERY_WORKLOAD SUSPEND;
-- DROP DATABASE IF EXISTS DSOA_TEST_DB;
-- DROP WAREHOUSE IF EXISTS DSOA_TEST_WH;
-- ============================================================================

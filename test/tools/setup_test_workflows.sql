-- ============================================================================
-- Workflow anomaly detection test setup for DSOA telemetry validation
-- Database: DSOA_TEST_DB   Schema: DSOA_TEST_DB.WORKFLOWS
-- Cost: near-zero (XSMALL, auto-suspend 60 s)
--
-- Covers all 4 plugins required by the 5 anomaly detection workflows:
--   resource_monitors  → BDX-1820 Credits Exhaustion Prediction
--   data_volume        → BDX-1822 Data Volume Anomaly Detection
--   dynamic_tables     → BDX-1827 Dynamic Table Refresh Drift Detection
--   query_history      → BDX-1821 Query Slowdown Detection
--                      → BDX-1826 Table Performance Degradation Detection
--
-- NOTE: This script is DSOA-independent. No DTAGENT_* roles or objects are
-- referenced. DSOA's own deploy grants its viewer role access to DSOA_TEST_DB.
-- ============================================================================

-- ============================================================================
-- 1. Shared warehouse (SYSADMIN — owns the warehouse)
-- ============================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Shared warehouse for DSOA synthetic test setups';

-- Grant DTAGENT_QA_OWNER usage on the shared warehouse so it can create and
-- query objects in DSOA_TEST_DB (which it owns).
GRANT USAGE ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER;

-- ============================================================================
-- 2. Database and schema (DTAGENT_QA_OWNER — owns DSOA_TEST_DB)
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.WORKFLOWS;

USE DATABASE DSOA_TEST_DB;
USE SCHEMA   DSOA_TEST_DB.WORKFLOWS;

-- ============================================================================
-- 3. DATA_VOLUME plugin — tables with varied row counts
--    The data_volume plugin reads from INFORMATION_SCHEMA.TABLE_STORAGE_METRICS
--    and ACCOUNT_USAGE.TABLE_STORAGE_METRICS scoped to the configured include
--    pattern. The plugin emits snowflake.data.rows and snowflake.data.bytes.
--    The data-volume-anomaly workflow alerts on drops in row counts.
-- ============================================================================

-- Large fact table — varied row count over time simulates pipeline activity
CREATE OR REPLACE TABLE DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS (
    ORDER_ID     NUMBER        NOT NULL,
    CUSTOMER_ID  NUMBER        NOT NULL,
    AMOUNT       NUMBER(10, 2) NOT NULL,
    STATUS       VARCHAR(20)   NOT NULL,
    ORDER_TS     TIMESTAMP_NTZ NOT NULL
);

-- Populate with a healthy row count (~3 000 rows)
INSERT INTO DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS
SELECT
    SEQ4()                                                AS ORDER_ID,
    UNIFORM(1, 500, RANDOM())                             AS CUSTOMER_ID,
    ROUND(UNIFORM(10, 9999, RANDOM()) / 100.0, 2)        AS AMOUNT,
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'PENDING'
        WHEN 2 THEN 'SHIPPED'
        WHEN 3 THEN 'DELIVERED'
        ELSE 'CANCELLED'
    END                                                   AS STATUS,
    DATEADD(SECOND, -UNIFORM(0, 2592000, RANDOM()), CURRENT_TIMESTAMP()) AS ORDER_TS
FROM TABLE(GENERATOR(ROWCOUNT => 3000));

-- Medium events table (~1 500 rows)
CREATE OR REPLACE TABLE DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS (
    EVENT_ID   NUMBER        NOT NULL,
    EVENT_TYPE VARCHAR(30)   NOT NULL,
    USER_ID    NUMBER        NOT NULL,
    EVENT_TS   TIMESTAMP_NTZ NOT NULL
);

INSERT INTO DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS
SELECT
    SEQ4(),
    CASE UNIFORM(1, 3, RANDOM())
        WHEN 1 THEN 'PAGE_VIEW'
        WHEN 2 THEN 'CLICK'
        ELSE 'PURCHASE'
    END,
    UNIFORM(1, 200, RANDOM()),
    DATEADD(SECOND, -UNIFORM(0, 604800, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 1500));

-- Small dimension table (~200 rows) — stable, rarely changes
CREATE OR REPLACE TABLE DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS (
    CUSTOMER_ID   NUMBER      NOT NULL,
    CUSTOMER_NAME VARCHAR(60) NOT NULL,
    REGION        VARCHAR(20) NOT NULL
);

INSERT INTO DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS
SELECT
    SEQ4() + 1,
    'Customer_' || (SEQ4() + 1),
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'NORTH'
        WHEN 2 THEN 'SOUTH'
        WHEN 3 THEN 'EAST'
        ELSE 'WEST'
    END
FROM TABLE(GENERATOR(ROWCOUNT => 200));

-- ============================================================================
-- 4. DYNAMIC_TABLES plugin — tables with measurable lag
--    The dynamic_tables plugin reads from INFORMATION_SCHEMA.DYNAMIC_TABLES
--    and ACCOUNT_USAGE.DYNAMIC_TABLES scoped by include/exclude patterns.
--    It emits snowflake.table.dynamic.lag.mean and .target.value.
--    The dynamic-table-drift workflow alerts when lag_excess rises above baseline.
--
--    We create:
--      DT_UPSTREAM   — base table refreshed by a task (simulates source data)
--      DT_DOWNSTREAM — dynamic table with a 1-minute target lag reading from it
--
--    Because CURRENT_TIMESTAMP() in the DT query forces FULL refresh mode
--    (Snowflake limitation), the lag will typically be non-zero and measurable.
-- ============================================================================

-- Base table that the dynamic table reads from
CREATE OR REPLACE TABLE DSOA_TEST_DB.WORKFLOWS.DT_SOURCE (
    ID          NUMBER        NOT NULL,
    VALUE       NUMBER(10, 2) NOT NULL,
    CATEGORY    VARCHAR(20)   NOT NULL,
    CREATED_AT  TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- Seed with initial data
INSERT INTO DSOA_TEST_DB.WORKFLOWS.DT_SOURCE
SELECT
    SEQ4() + 1,
    ROUND(UNIFORM(1, 1000, RANDOM()) / 10.0, 2),
    CASE UNIFORM(1, 3, RANDOM())
        WHEN 1 THEN 'TYPE_A'
        WHEN 2 THEN 'TYPE_B'
        ELSE 'TYPE_C'
    END,
    DATEADD(SECOND, -UNIFORM(0, 3600, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 500));

-- Dynamic table with a 1-minute target lag
-- FULL refresh mode is expected (non-deterministic function in query) — this is fine
CREATE OR REPLACE DYNAMIC TABLE DSOA_TEST_DB.WORKFLOWS.DT_SUMMARY
    TARGET_LAG = '1 minute'
    WAREHOUSE  = DSOA_TEST_WH
    AS
    SELECT
        CATEGORY,
        COUNT(*)                                     AS ROW_COUNT,
        ROUND(AVG(VALUE), 2)                         AS AVG_VALUE,
        ROUND(SUM(VALUE), 2)                         AS TOTAL_VALUE,
        MAX(CREATED_AT)                              AS LAST_UPDATED,
        CURRENT_TIMESTAMP()                          AS REPORT_TS
    FROM DSOA_TEST_DB.WORKFLOWS.DT_SOURCE
    GROUP BY CATEGORY;

-- Task that injects new rows into DT_SOURCE every 2 minutes so DT_SUMMARY
-- has measurable lag and refresh history for Davis to learn from.
-- NOTE: Plain SQL body (no $$-block) to avoid snow-cli parse issues with
-- DECLARE/BEGIN/END inside $$. Fixed batch of 30 rows per run is sufficient
-- for synthetic lag signal.
CREATE OR REPLACE TASK DSOA_TEST_DB.WORKFLOWS.T_INSERT_DT_SOURCE
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '2 MINUTE'
AS
    INSERT INTO DSOA_TEST_DB.WORKFLOWS.DT_SOURCE (ID, VALUE, CATEGORY, CREATED_AT)
    SELECT
        (SELECT COALESCE(MAX(ID), 0) FROM DSOA_TEST_DB.WORKFLOWS.DT_SOURCE) + SEQ4() + 1,
        ROUND(UNIFORM(1, 1000, RANDOM()) / 10.0, 2),
        CASE UNIFORM(1, 3, RANDOM())
            WHEN 1 THEN 'TYPE_A'
            WHEN 2 THEN 'TYPE_B'
            ELSE 'TYPE_C'
        END,
        CURRENT_TIMESTAMP()
    FROM TABLE(GENERATOR(ROWCOUNT => 30));

-- ============================================================================
-- 5. QUERY_HISTORY plugin — generate varied query history
--    The query_history plugin reads ACCOUNT_USAGE.QUERY_HISTORY.
--    It emits snowflake.time.execution, snowflake.partitions.scanned/total,
--    and snowflake.warehouse.name / db.namespace dimensions.
--    Executing a mix of fast and slow queries against the tables above
--    produces the signal needed by:
--      - query-slowdown-detection (avg exec time per warehouse/db)
--      - table-perf-degradation (partition scan ratio per table)
-- ============================================================================

-- Fast analytical queries against the tables we just created
SELECT COUNT(*), STATUS FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS GROUP BY STATUS;
SELECT REGION, COUNT(*) FROM DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS GROUP BY REGION;
SELECT AVG(AMOUNT), STATUS FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS GROUP BY STATUS;
SELECT COUNT(*) FROM DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS;
SELECT * FROM DSOA_TEST_DB.WORKFLOWS.DT_SUMMARY;

-- Slightly heavier queries using joins to produce non-trivial execution times
SELECT
    c.REGION,
    COUNT(o.ORDER_ID)   AS ORDER_COUNT,
    SUM(o.AMOUNT)       AS TOTAL_REVENUE
FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS o
JOIN DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
GROUP BY c.REGION
ORDER BY TOTAL_REVENUE DESC;

SELECT
    o.STATUS,
    COUNT(e.EVENT_ID)   AS EVENT_COUNT,
    COUNT(o.ORDER_ID)   AS ORDER_COUNT
FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS o
LEFT JOIN DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS e ON o.CUSTOMER_ID = e.USER_ID
GROUP BY o.STATUS;

-- Full-scan queries to register partition activity (needed for scan ratio metric)
SELECT * FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS WHERE AMOUNT > 50;
SELECT * FROM DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS WHERE EVENT_TYPE = 'PURCHASE';
SELECT * FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS ORDER BY AMOUNT DESC LIMIT 100;
SELECT * FROM DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS ORDER BY EVENT_TS DESC LIMIT 100;

-- Repeat several times with small delays to build up query history
SELECT COUNT(*), AVG(AMOUNT) FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS;
SELECT COUNT(*) FROM DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS WHERE USER_ID < 100;
SELECT MAX(AMOUNT), MIN(AMOUNT) FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS;
SELECT DISTINCT STATUS FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS;

-- ============================================================================
-- 6. Resume the insert task so DT_SUMMARY accumulates lag history
--    (requires EXECUTE TASK privilege on the SYSADMIN role's task)
-- ============================================================================
ALTER TASK DSOA_TEST_DB.WORKFLOWS.T_INSERT_DT_SOURCE RESUME;

-- ============================================================================
-- 7. Verify setup
-- ============================================================================
SHOW TABLES   IN SCHEMA DSOA_TEST_DB.WORKFLOWS;
SHOW DYNAMIC TABLES IN SCHEMA DSOA_TEST_DB.WORKFLOWS;
SHOW TASKS    IN SCHEMA DSOA_TEST_DB.WORKFLOWS;

SELECT 'FACTS_ORDERS'  AS table_name, COUNT(*) AS row_count FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS   UNION ALL
SELECT 'FACTS_EVENTS',                COUNT(*)               FROM DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS   UNION ALL
SELECT 'DIM_CUSTOMERS',               COUNT(*)               FROM DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS  UNION ALL
SELECT 'DT_SOURCE',                   COUNT(*)               FROM DSOA_TEST_DB.WORKFLOWS.DT_SOURCE;

-- ============================================================================
-- CLEANUP (run when done testing):
--   ALTER TASK DSOA_TEST_DB.WORKFLOWS.T_INSERT_DT_SOURCE SUSPEND;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.WORKFLOWS;
-- ============================================================================

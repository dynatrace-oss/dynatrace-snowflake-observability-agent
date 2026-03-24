-- ============================================================================
-- Tasks & Pipelines test setup for DSOA telemetry validation
-- Creates objects to exercise the `tasks` and `dynamic_tables` plugins.
--
-- Self-contained: creates its own warehouse (DSOA_TEST_WH) and database
-- (DSOA_TEST_DB) — no external warehouse or configuration variables required.
--
-- Objects created
--   Warehouse: DSOA_TEST_WH            (XSMALL, auto-suspend 60 s)
--   Database : DSOA_TEST_DB
--   Schema   : DSOA_TEST_DB.TASKS_TEST
--
--   Tables (base sources for dynamic tables):
--     DSOA_TEST_DB.TASKS_TEST.RAW_EVENTS      -- raw source table
--     DSOA_TEST_DB.TASKS_TEST.RAW_ORDERS      -- raw source table with intentional data churn
--
--   Dynamic Tables (exercises dynamic_tables plugin):
--     DSOA_TEST_DB.TASKS_TEST.DT_EVENT_SUMMARY  -- incremental, 1-minute target lag
--     DSOA_TEST_DB.TASKS_TEST.DT_ORDER_TOTALS   -- incremental, 2-minute target lag
--     DSOA_TEST_DB.TASKS_TEST.DT_DOWNSTREAM     -- depends on DT_EVENT_SUMMARY (pipeline graph)
--
--   Stored Procedures (called by tasks):
--     DSOA_TEST_DB.TASKS_TEST.SP_INSERT_EVENTS()
--     DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS()
--     DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS_WITH_ERRORS()  -- causes task failure for error tiles
--
--   Tasks (exercises tasks plugin):
--     DSOA_TEST_DB.TASKS_TEST.T_INSERT_EVENTS        -- every 5 min, succeeds
--     DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS        -- child of above, every 5 min, succeeds
--     DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS_FAIL   -- every 10 min, always fails + auto-retries 3x (retry tiles)
--
-- Coverage per dashboard tile
--   tile 1  Task Execution States over Time  → T_INSERT_EVENTS (SUCCEEDED), T_INSERT_ORDERS_FAIL (FAILED)
--   tile 2  Failed Tasks with Error Details  → T_INSERT_ORDERS_FAIL error code + message
--   tile 3  Task Run Duration Trend          → scheduled_time / completed_time from all tasks
--   tile 4  Task Retry Patterns              → T_INSERT_ORDERS_FAIL retries (ATTEMPT_NUMBER > 1)
--   tile 6  Total Serverless Credits         → N/A (warehouse tasks, not serverless)
--   tile 7  Serverless Credits by Task       → N/A (warehouse tasks, not serverless)
--   tile 8  Credits by Database and Schema   → N/A (warehouse tasks, not serverless)
--   tile 10 Scheduling State Heatmap         → DT_EVENT_SUMMARY, DT_ORDER_TOTALS, DT_DOWNSTREAM
--   tile 11 Mean Lag vs Target Lag           → lag metrics from dynamic_tables context
--   tile 12 Time Above Target Lag            → TIME_ABOVE_TARGET_LAG_SEC
--   tile 13 Within-Target-Lag Ratio          → TIME_WITHIN_TARGET_LAG_RATIO
--   tile 14 Recent Refresh History           → dynamic_table_refresh_history context events
--   tile 15 Refresh Action Distribution      → INCREMENTAL / FULL / NO_DATA actions
--
-- Cost: near-zero — XSMALL warehouse, auto-suspends in 60 s, tiny row counts.
--
-- Deployed and validated on: test-qa (DYNATRACEDIGITALBUSINESSDW, AWS_US_EAST_1)
-- Viewer role granted:        DTAGENT_QA_VIEWER
-- ============================================================================

-- ============================================================================
-- 1. Account-level grants (ACCOUNTADMIN)
--    EXECUTE TASK allows DTAGENT_QA_OWNER to resume/run its own tasks.
-- ============================================================================
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE DTAGENT_QA_OWNER;

-- ============================================================================
-- 2. Warehouse — created by SYSADMIN, owned by DTAGENT_QA_OWNER
-- ============================================================================
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Synthetic test warehouse for DSOA tasks/dynamic_tables validation';

GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;

-- ============================================================================
-- 3. Database — created by SYSADMIN, ownership transferred to DTAGENT_QA_OWNER
-- ============================================================================
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
GRANT OWNERSHIP ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;

-- ============================================================================
-- 4. All remaining objects owned by DTAGENT_QA_OWNER from birth
-- ============================================================================
USE ROLE      DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;
USE DATABASE  DSOA_TEST_DB;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.TASKS_TEST;
USE SCHEMA DSOA_TEST_DB.TASKS_TEST;

-- ============================================================================
-- 5. Base source tables
-- ============================================================================

CREATE OR REPLACE TABLE DSOA_TEST_DB.TASKS_TEST.RAW_EVENTS (
    event_id    NUMBER AUTOINCREMENT,
    event_type  VARCHAR(50),
    payload     VARCHAR(500),
    event_ts    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE DSOA_TEST_DB.TASKS_TEST.RAW_ORDERS (
    order_id    NUMBER AUTOINCREMENT,
    customer_id NUMBER,
    item        VARCHAR(100),
    amount      NUMBER(10, 2),
    order_ts    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================================
-- 6. Dynamic Tables
--    Short target lags (1–3 min) so refreshes appear quickly in
--    DYNAMIC_TABLE_REFRESH_HISTORY and populate the dynamic_tables context.
-- ============================================================================

CREATE OR REPLACE DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_EVENT_SUMMARY
    TARGET_LAG = '1 minute'
    WAREHOUSE  = DSOA_TEST_WH
AS
SELECT
    event_type,
    COUNT(*)        AS event_count,
    MAX(event_ts)   AS last_seen
FROM DSOA_TEST_DB.TASKS_TEST.RAW_EVENTS
GROUP BY event_type;

CREATE OR REPLACE DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_ORDER_TOTALS
    TARGET_LAG = '2 minutes'
    WAREHOUSE  = DSOA_TEST_WH
AS
SELECT
    customer_id,
    COUNT(*)        AS order_count,
    SUM(amount)     AS total_amount,
    MAX(order_ts)   AS last_order_ts
FROM DSOA_TEST_DB.TASKS_TEST.RAW_ORDERS
GROUP BY customer_id;

-- Downstream table — depends on DT_EVENT_SUMMARY, exercises pipeline graph history
CREATE OR REPLACE DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_DOWNSTREAM
    TARGET_LAG = '3 minutes'
    WAREHOUSE  = DSOA_TEST_WH
AS
SELECT
    s.event_type,
    s.event_count,
    CURRENT_TIMESTAMP() AS report_ts
FROM DSOA_TEST_DB.TASKS_TEST.DT_EVENT_SUMMARY s
WHERE s.event_count > 0;

-- ============================================================================
-- 7. Stored procedures (called by tasks)
-- ============================================================================

-- 7a. Insert varied events — succeeds every run
--     Note: UNIFORM() must be captured into DECLARE variables first; Snowflake
--     does not allow UNIFORM() inline in VALUES alongside string concatenation.
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.TASKS_TEST.SP_INSERT_EVENTS()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    run_ts   VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
    order_no NUMBER  DEFAULT UNIFORM(1000, 9999, RANDOM());
    page_no  NUMBER  DEFAULT UNIFORM(1, 50, RANDOM());
BEGIN
    INSERT INTO DSOA_TEST_DB.TASKS_TEST.RAW_EVENTS (event_type, payload) VALUES
        ('click',    'homepage at '    || :run_ts),
        ('purchase', 'order #'         || :order_no || ' at ' || :run_ts),
        ('signup',   'new user at '    || :run_ts),
        ('pageview', 'product page '   || :page_no  || ' at ' || :run_ts),
        ('search',   'query at '       || :run_ts),
        ('logout',   'session end at ' || :run_ts);
    RETURN 'Inserted 6 events at ' || :run_ts;
END;
$$;

-- 7b. Insert orders — succeeds every run
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    run_ts VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
    c1 NUMBER DEFAULT UNIFORM(100, 199, RANDOM());
    c2 NUMBER DEFAULT UNIFORM(200, 299, RANDOM());
    c3 NUMBER DEFAULT UNIFORM(300, 399, RANDOM());
    c4 NUMBER DEFAULT UNIFORM(400, 499, RANDOM());
BEGIN
    INSERT INTO DSOA_TEST_DB.TASKS_TEST.RAW_ORDERS (customer_id, item, amount) VALUES
        (:c1, 'Widget A',  29.99),
        (:c2, 'Widget B', 149.50),
        (:c3, 'Gadget X',  79.00),
        (:c4, 'Gadget Y',  49.99);
    RETURN 'Inserted 4 orders at ' || :run_ts;
END;
$$;

-- 7c. Always fails — generates FAILED runs with ERROR_CODE + ERROR_MESSAGE,
--     exercising tiles 2 (Failed Tasks) and 4 (Retry Patterns).
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS_WITH_ERRORS()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    -- Intentional type error: 'not-a-number' cannot cast to NUMBER(10,2).
    -- Produces a non-null ERROR_CODE in INFORMATION_SCHEMA.TASK_HISTORY.
    INSERT INTO DSOA_TEST_DB.TASKS_TEST.RAW_ORDERS (customer_id, item, amount)
    VALUES (999, 'Bad Row', 'not-a-number');
    RETURN 'Should not reach here';
END;
$$;

-- ============================================================================
-- 8. Tasks
-- ============================================================================

-- 8a. Root task: inserts events every 5 minutes
CREATE OR REPLACE TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_EVENTS
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '5 MINUTE'
AS
    CALL DSOA_TEST_DB.TASKS_TEST.SP_INSERT_EVENTS();

-- 8b. Child task: runs after T_INSERT_EVENTS (exercises task graph / predecessor)
CREATE OR REPLACE TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS
    WAREHOUSE = DSOA_TEST_WH
    AFTER     DSOA_TEST_DB.TASKS_TEST.T_INSERT_EVENTS
AS
    CALL DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS();

-- 8c. Independent failing task every 10 minutes (exercises error + retry tiles).
--     TASK_AUTO_RETRY_ATTEMPTS = 3 causes Snowflake to retry on failure, generating
--     ATTEMPT_NUMBER > 1 rows in TASK_HISTORY — required for the Retry Patterns tile.
CREATE OR REPLACE TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS_FAIL
    WAREHOUSE                = DSOA_TEST_WH
    SCHEDULE                 = '10 MINUTE'
    TASK_AUTO_RETRY_ATTEMPTS = 3
AS
    CALL DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS_WITH_ERRORS();

-- Resume: children before root
ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS      RESUME;
ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_EVENTS      RESUME;
ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS_FAIL RESUME;

-- ============================================================================
-- 9. Seed initial data and trigger immediate refreshes
-- ============================================================================
CALL DSOA_TEST_DB.TASKS_TEST.SP_INSERT_EVENTS();
CALL DSOA_TEST_DB.TASKS_TEST.SP_INSERT_ORDERS();

ALTER DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_EVENT_SUMMARY REFRESH;
ALTER DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_ORDER_TOTALS  REFRESH;
ALTER DYNAMIC TABLE DSOA_TEST_DB.TASKS_TEST.DT_DOWNSTREAM    REFRESH;

-- Trigger one immediate failing run to seed FAILED history entry
EXECUTE TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS_FAIL;

-- ============================================================================
-- 10. Grant DTAGENT_QA_VIEWER access to all test objects
-- ============================================================================
GRANT USAGE   ON WAREHOUSE DSOA_TEST_WH                                   TO ROLE DTAGENT_QA_VIEWER;
GRANT USAGE   ON DATABASE  DSOA_TEST_DB                                   TO ROLE DTAGENT_QA_VIEWER;
GRANT USAGE   ON SCHEMA    DSOA_TEST_DB.TASKS_TEST                        TO ROLE DTAGENT_QA_VIEWER;
GRANT SELECT  ON ALL TABLES         IN SCHEMA DSOA_TEST_DB.TASKS_TEST     TO ROLE DTAGENT_QA_VIEWER;
GRANT SELECT  ON ALL DYNAMIC TABLES IN SCHEMA DSOA_TEST_DB.TASKS_TEST     TO ROLE DTAGENT_QA_VIEWER;
GRANT MONITOR ON ALL TASKS          IN SCHEMA DSOA_TEST_DB.TASKS_TEST     TO ROLE DTAGENT_QA_VIEWER;

-- ============================================================================
-- 11. Verify setup
-- ============================================================================
SHOW TASKS          IN SCHEMA DSOA_TEST_DB.TASKS_TEST;
SHOW DYNAMIC TABLES IN SCHEMA DSOA_TEST_DB.TASKS_TEST;

-- ============================================================================
-- TEARDOWN (run when done testing):
-- Suspends all synthetic tasks before dropping objects. Tasks must be
-- suspended before dropping the database — Snowflake will refuse to drop
-- a database that contains running tasks.
-- Note: DSOA_TEST_WH was granted ownership to DTAGENT_QA_OWNER; dropping it
-- requires ACCOUNTADMIN (SYSADMIN alone is insufficient).
-- ============================================================================
-- USE ROLE DTAGENT_QA_OWNER;
-- ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_EVENTS      SUSPEND;
-- ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS      SUSPEND;
-- ALTER TASK DSOA_TEST_DB.TASKS_TEST.T_INSERT_ORDERS_FAIL SUSPEND;
-- DROP DATABASE  IF EXISTS DSOA_TEST_DB;
-- USE ROLE ACCOUNTADMIN;
-- DROP WAREHOUSE IF EXISTS DSOA_TEST_WH;
-- ============================================================================

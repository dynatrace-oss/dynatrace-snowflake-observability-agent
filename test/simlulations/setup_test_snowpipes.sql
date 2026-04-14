-- ============================================================================
-- Minimal Snowpipe test setup for DSOA telemetry validation
-- Creates: 1 database, 1 schema, 2 target tables, 2 stages, 2 pipes,
--          1 stored procedure, 1 Snowflake Task (runs every 30 minutes)
-- Cost: near-zero (auto-ingest off, manual refresh via task)
--
-- Traffic pattern (per task run):
--   EVENTS_PIPE  - 6 rows of varied event types (all load successfully)
--   ORDERS_PIPE  - 3 rows: 2 good + 1 intentionally malformed to exercise
--                  load error telemetry (tiles: Load Errors, Errors by Table,
--                  Top Pipes by Error Count)
--
-- Ownership model:
--   All objects are created directly by OWNER_ROLE so no post-hoc ownership
--   transfers are needed (which would require pausing pipes, etc.).
--   ACCOUNTADMIN is used only for the two account-level grants that cannot
--   be issued by a non-ACCOUNTADMIN role.
--
-- **IMPORTANT** Before running:
--   1. Set OWNER_ROLE to the role that should own all objects.
--   2. Set TASK_WAREHOUSE to a warehouse that OWNER_ROLE can use.
-- ============================================================================

-- ---- CONFIGURATION ---------------------------------------------------------
-- Edit these two values; leave everything else unchanged.
SET owner_role     = 'OWNER_ROLE';       -- role that will own all objects
SET task_warehouse = 'TASK_WAREHOUSE';  -- warehouse used by the task
-- ----------------------------------------------------------------------------

-- 1. Account-level grants that require ACCOUNTADMIN.
--    EXECUTE TASK  - allows OWNER_ROLE to resume/run tasks it owns.
--    WAREHOUSE USAGE - allows the task to start the warehouse at runtime.
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK  ON ACCOUNT                               TO ROLE IDENTIFIER($owner_role);
GRANT USAGE         ON WAREHOUSE IDENTIFIER($task_warehouse) TO ROLE IDENTIFIER($owner_role);

-- 2. Create the database as SYSADMIN, then immediately grant ownership to
--    OWNER_ROLE before any other objects exist (database has no running pipes
--    yet, so the ownership transfer is safe).
USE ROLE SYSADMIN;
CREATE DATABASE IF NOT EXISTS DSOA_PIPE_TEST_DB;
USE ROLE ACCOUNTADMIN;
GRANT OWNERSHIP ON DATABASE DSOA_PIPE_TEST_DB TO ROLE IDENTIFIER($owner_role) COPY CURRENT GRANTS;

-- 3. Switch to OWNER_ROLE for everything else. All objects created from here
--    are owned by OWNER_ROLE from birth — no ownership transfers needed.
USE ROLE IDENTIFIER($owner_role);
USE DATABASE DSOA_PIPE_TEST_DB;

CREATE SCHEMA IF NOT EXISTS DSOA_PIPE_TEST_DB.INGEST;

-- 4. Target tables
CREATE OR REPLACE TABLE DSOA_PIPE_TEST_DB.INGEST.EVENTS (
    event_id    NUMBER AUTOINCREMENT,
    event_type  VARCHAR(100),
    payload     VARCHAR(500),
    created_at  TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE DSOA_PIPE_TEST_DB.INGEST.ORDERS (
    order_id    NUMBER AUTOINCREMENT,
    customer_id NUMBER,
    amount      NUMBER(10,2),
    created_at  TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 5. Internal stages (no cloud storage needed)
CREATE OR REPLACE STAGE DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

CREATE OR REPLACE STAGE DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

-- 6. Pipes (auto_ingest=false — no SQS/SNS cost)
CREATE OR REPLACE PIPE DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO DSOA_PIPE_TEST_DB.INGEST.EVENTS (event_type, payload)
    FROM @DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE;

CREATE OR REPLACE PIPE DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO DSOA_PIPE_TEST_DB.INGEST.ORDERS (customer_id, amount)
    FROM @DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE;

-- 7. Stored procedure: stages fresh data and refreshes both pipes.
--    Called by the task every 30 minutes.
--
--    EVENTS: 6 rows with varied event types and a timestamp-stamped payload so
--            every file is unique (Snowpipe deduplicates by file path + MD5,
--            so identical files staged repeatedly are skipped).
--    ORDERS: 2 valid rows + 1 malformed row (amount is a non-numeric string)
--            to produce exactly one load error per run.
CREATE OR REPLACE PROCEDURE DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    run_ts VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
BEGIN
    -- Stage fresh EVENTS data (varied types, timestamped payload for uniqueness)
    COPY INTO @DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE
    FROM (
        SELECT 'event_type,payload' AS c1
        UNION ALL SELECT 'click,"homepage visit at '    || :run_ts || '"'
        UNION ALL SELECT 'purchase,"order #' || UNIFORM(1000, 9999, RANDOM()) || ' at ' || :run_ts || '"'
        UNION ALL SELECT 'signup,"new user at '         || :run_ts || '"'
        UNION ALL SELECT 'pageview,"product page at '   || :run_ts || '"'
        UNION ALL SELECT 'search,"query at '            || :run_ts || '"'
        UNION ALL SELECT 'logout,"session end at '      || :run_ts || '"'
    )
    FILE_FORMAT = (TYPE = CSV COMPRESSION = NONE)
    SINGLE = TRUE
    MAX_FILE_SIZE = 5000000
    HEADER = FALSE
    OVERWRITE = TRUE;

    -- Stage ORDERS data: 2 valid rows + 1 malformed row (intentional error)
    COPY INTO @DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE
    FROM (
        SELECT 'customer_id,amount' AS c1
        UNION ALL SELECT UNIFORM(100, 199, RANDOM()) || ',29.99'
        UNION ALL SELECT UNIFORM(200, 299, RANDOM()) || ',149.50'
        -- Intentionally malformed: amount is not a valid number -> load error
        UNION ALL SELECT '999,"not-a-number"'
    )
    FILE_FORMAT = (TYPE = CSV COMPRESSION = NONE)
    SINGLE = TRUE
    MAX_FILE_SIZE = 5000000
    HEADER = FALSE
    OVERWRITE = TRUE;

    -- Refresh both pipes to trigger ingestion of the newly staged files
    ALTER PIPE DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE REFRESH;
    ALTER PIPE DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE REFRESH;

    RETURN 'Refreshed at ' || :run_ts;
END;
$$;

-- 8. Task: calls the procedure every 30 minutes.
--    Because OWNER_ROLE already has EXECUTE TASK (granted in step 1) and owns
--    this task, ALTER TASK ... RESUME will succeed without further grants.
CREATE OR REPLACE TASK DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES_TASK
    WAREHOUSE = IDENTIFIER($task_warehouse)
    SCHEDULE  = '30 MINUTE'
AS
    CALL DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES();

ALTER TASK DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES_TASK RESUME;

-- 9. Run the procedure once immediately so data is available right away.
CALL DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES();

-- 10. Grant MONITOR on the test pipes to the DSOA viewer role so the agent
--     can read pipe status and copy-history telemetry.
--     Adjust the viewer role name to match your deployment tag.
-- GRANT USAGE   ON DATABASE DSOA_PIPE_TEST_DB              TO ROLE DTAGENT_094_VIEWER;
-- GRANT USAGE   ON SCHEMA   DSOA_PIPE_TEST_DB.INGEST        TO ROLE DTAGENT_094_VIEWER;
-- GRANT MONITOR ON PIPE     DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE TO ROLE DTAGENT_094_VIEWER;
-- GRANT MONITOR ON PIPE     DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE TO ROLE DTAGENT_094_VIEWER;

-- 11. Verify setup
SHOW PIPES IN SCHEMA DSOA_PIPE_TEST_DB.INGEST;
SHOW TASKS IN SCHEMA DSOA_PIPE_TEST_DB.INGEST;
SELECT SYSTEM$PIPE_STATUS('DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE');
SELECT SYSTEM$PIPE_STATUS('DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE');

-- Wait ~2 minutes for pipe loads to appear in COPY_HISTORY, then verify:
-- SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
-- WHERE PIPE_NAME LIKE '%DSOA_PIPE_TEST%'
-- ORDER BY LAST_LOAD_TIME DESC LIMIT 10;

-- ============================================================================
-- CLEANUP (run when done testing):
-- USE ROLE IDENTIFIER($owner_role);
-- ALTER TASK DSOA_PIPE_TEST_DB.INGEST.REFRESH_TEST_PIPES_TASK SUSPEND;
-- DROP DATABASE IF EXISTS DSOA_PIPE_TEST_DB;
-- ============================================================================

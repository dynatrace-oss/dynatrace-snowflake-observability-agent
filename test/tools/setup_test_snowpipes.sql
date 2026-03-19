-- ============================================================================
-- Minimal Snowpipe test setup for DSOA telemetry validation
-- Creates: 1 database, 1 schema, 1 target table, 1 stage, 2 pipes
-- Cost: near-zero (auto-ingest off, manual file loading)
-- ============================================================================

-- 1. Create test database and schema
USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS DSOA_PIPE_TEST_DB;
CREATE SCHEMA IF NOT EXISTS DSOA_PIPE_TEST_DB.INGEST;

-- 2. Create target tables (minimal columns)
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

-- 3. Create internal stages (no cloud storage needed)
CREATE OR REPLACE STAGE DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

CREATE OR REPLACE STAGE DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

-- 4. Create pipes (auto_ingest=false to avoid SQS/SNS costs)
CREATE OR REPLACE PIPE DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO DSOA_PIPE_TEST_DB.INGEST.EVENTS (event_type, payload)
    FROM @DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE;

CREATE OR REPLACE PIPE DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO DSOA_PIPE_TEST_DB.INGEST.ORDERS (customer_id, amount)
    FROM @DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE;

-- 5. Upload sample data files to stages
-- Events data
COPY INTO @DSOA_PIPE_TEST_DB.INGEST.EVENTS_STAGE
FROM (
    SELECT 'event_type,payload' AS c1
    UNION ALL SELECT 'click,"homepage visit"'
    UNION ALL SELECT 'purchase,"order #1001"'
    UNION ALL SELECT 'signup,"new user registration"'
)
FILE_FORMAT = (TYPE = CSV COMPRESSION = NONE)
SINGLE = TRUE
MAX_FILE_SIZE = 5000000
HEADER = FALSE
OVERWRITE = TRUE;

-- Orders data
COPY INTO @DSOA_PIPE_TEST_DB.INGEST.ORDERS_STAGE
FROM (
    SELECT 'customer_id,amount' AS c1
    UNION ALL SELECT '101,29.99'
    UNION ALL SELECT '102,149.50'
    UNION ALL SELECT '103,9.99'
)
FILE_FORMAT = (TYPE = CSV COMPRESSION = NONE)
SINGLE = TRUE
MAX_FILE_SIZE = 5000000
HEADER = FALSE
OVERWRITE = TRUE;

-- 6. Trigger pipe refresh (loads the staged files)
ALTER PIPE DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE REFRESH;
ALTER PIPE DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE REFRESH;

-- 7. Grant MONITOR on the test pipes to the DSOA viewer role
-- Adjust the role name if your deployment uses a tag (e.g. DTAGENT_094_VIEWER)
-- GRANT USAGE ON DATABASE DSOA_PIPE_TEST_DB TO ROLE DTAGENT_094_VIEWER;
-- GRANT USAGE ON SCHEMA DSOA_PIPE_TEST_DB.INGEST TO ROLE DTAGENT_094_VIEWER;
-- GRANT MONITOR ON PIPE DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE TO ROLE DTAGENT_094_VIEWER;
-- GRANT MONITOR ON PIPE DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE TO ROLE DTAGENT_094_VIEWER;

-- 8. Verify setup
SHOW PIPES IN SCHEMA DSOA_PIPE_TEST_DB.INGEST;
SELECT SYSTEM$PIPE_STATUS('DSOA_PIPE_TEST_DB.INGEST.EVENTS_PIPE');
SELECT SYSTEM$PIPE_STATUS('DSOA_PIPE_TEST_DB.INGEST.ORDERS_PIPE');

-- Wait ~2 minutes for pipe loads to appear in COPY_HISTORY, then verify:
-- SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
-- WHERE PIPE_NAME LIKE '%DSOA_PIPE_TEST%'
-- ORDER BY LAST_LOAD_TIME DESC LIMIT 10;

-- ============================================================================
-- CLEANUP (run when done testing):
-- DROP DATABASE IF EXISTS DSOA_PIPE_TEST_DB;
-- ============================================================================

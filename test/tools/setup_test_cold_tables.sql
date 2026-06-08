-- ============================================================================
-- Cold Tables plugin test setup for DSOA telemetry validation
-- Exercises: table access frequency tracking and cold/warm classification
--
-- Coverage:
--   C2.15 — Cold tables: access metrics reported (BDX-676)
--           snowflake.table.days_since_last_access, snowflake.table.access.count
--
-- Strategy:
--   The cold_tables plugin reads SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
--   flattening BASE_OBJECTS_ACCESSED for objectDomain='Table'. It computes
--   days since last access and classifies tables as 'cold' (> threshold days)
--   or 'warm'.
--
--   ACCESS_HISTORY has ~24h latency. Tables accessed TODAY will not appear
--   until tomorrow. Tables NOT accessed recently will show up as 'cold'.
--
--   To generate meaningful test data:
--     1. Create tables that we ACCESS now (will be 'warm' after 24h lag)
--     2. Create tables that we DO NOT access (will be 'cold' if they existed
--        before cold_threshold_days ago — but new tables won't be cold)
--     3. Rely on existing tables in the account that haven't been accessed
--        in > cold_threshold_days
--
--   For immediate testing: set cold_threshold_days: 1 in config and check
--   against tables created yesterday that haven't been accessed since.
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - cold_tables plugin must be enabled
--   - ACCESS_HISTORY must have data (24h latency)
--
-- LATENCY: This test is [DEFERRED] — seed data today, verify tomorrow.
--
-- Cost: near-zero
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_cold_tables.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.COLD_TABLES_TEST;
USE SCHEMA DSOA_TEST_DB.COLD_TABLES_TEST;

-- ============================================================================
-- 2. Create tables that WILL be accessed (warm candidates)
--    After 24h, these will appear in ACCESS_HISTORY as recently accessed.
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_A (
    ID    NUMBER NOT NULL,
    DATA  VARCHAR(100) NOT NULL
);

INSERT INTO DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_A
SELECT SEQ4() + 1, 'warm_data_' || (SEQ4() + 1)
FROM TABLE(GENERATOR(ROWCOUNT => 100));

CREATE OR REPLACE TABLE DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_B (
    ID    NUMBER NOT NULL,
    VALUE NUMBER(10, 2) NOT NULL
);

INSERT INTO DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_B
SELECT SEQ4() + 1, ROUND(UNIFORM(1, 999, RANDOM()) / 10.0, 2)
FROM TABLE(GENERATOR(ROWCOUNT => 100));

-- Access the warm tables (this generates ACCESS_HISTORY entries after 24h)
SELECT COUNT(*) FROM DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_A;
SELECT AVG(VALUE) FROM DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_B;

-- ============================================================================
-- 3. Create tables that will NOT be accessed after creation (cold candidates)
--    These tables exist but no SELECT will be run against them.
--    With cold_threshold_days: 1, they'll be classified as 'cold' after 24h
--    of no access (the CREATE + INSERT count as access, but after 24h
--    with no further access, they exceed the threshold).
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.COLD_TABLES_TEST.COLD_TABLE_ABANDONED (
    ID    NUMBER NOT NULL,
    DATA  VARCHAR(100) NOT NULL
);

INSERT INTO DSOA_TEST_DB.COLD_TABLES_TEST.COLD_TABLE_ABANDONED
SELECT SEQ4() + 1, 'abandoned_' || (SEQ4() + 1)
FROM TABLE(GENERATOR(ROWCOUNT => 50));

CREATE OR REPLACE TABLE DSOA_TEST_DB.COLD_TABLES_TEST.COLD_TABLE_STALE (
    ID    NUMBER NOT NULL,
    DATA  VARCHAR(100) NOT NULL
);

INSERT INTO DSOA_TEST_DB.COLD_TABLES_TEST.COLD_TABLE_STALE
SELECT SEQ4() + 1, 'stale_' || (SEQ4() + 1)
FROM TABLE(GENERATOR(ROWCOUNT => 50));

-- DO NOT query COLD_TABLE_ABANDONED or COLD_TABLE_STALE after this point!

-- ============================================================================
-- 4. Schedule periodic access to warm tables (keeps them warm)
-- ============================================================================
CREATE OR REPLACE TASK DSOA_TEST_DB.COLD_TABLES_TEST.T_WARM_ACCESS
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '60 MINUTE'
AS
    SELECT COUNT(*) FROM DSOA_TEST_DB.COLD_TABLES_TEST.WARM_TABLE_A;

ALTER TASK DSOA_TEST_DB.COLD_TABLES_TEST.T_WARM_ACCESS RESUME;

-- ============================================================================
-- 5. Config requirements
-- ============================================================================
-- In conf/config-test-qa.yml:
--   plugins:
--     cold_tables:
--       is_enabled: true
--       cold_threshold_days: 1        # Low threshold for testing (default 90)
--       lookback_days: 7              # Short lookback for test speed
--       include:
--         - "DSOA_TEST_DB.COLD_TABLES_TEST.%"
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

-- ============================================================================
-- 6. Verification DQL (run 24+ hours after this script)
-- ============================================================================
-- C2.15 — Access metrics:
--   timeseries avg(snowflake.table.days_since_last_access)
--   | filter deployment.environment == "DEV-095"
--
-- Cold vs warm classification:
--   fetch logs
--   | filter dsoa.run.plugin == "cold_tables"
--   | filter deployment.environment == "DEV-095"
--   | summarize count(), by: {snowflake.table.cold_status, db.collection.name}
--
-- Expected after 24h:
--   WARM_TABLE_A, WARM_TABLE_B → cold_status = "warm"
--   COLD_TABLE_ABANDONED, COLD_TABLE_STALE → cold_status = "cold"

-- ============================================================================
-- 7. Verify setup
-- ============================================================================
SHOW TABLES IN SCHEMA DSOA_TEST_DB.COLD_TABLES_TEST;
SHOW TASKS IN SCHEMA DSOA_TEST_DB.COLD_TABLES_TEST;

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   ALTER TASK DSOA_TEST_DB.COLD_TABLES_TEST.T_WARM_ACCESS SUSPEND;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.COLD_TABLES_TEST CASCADE;
-- ============================================================================

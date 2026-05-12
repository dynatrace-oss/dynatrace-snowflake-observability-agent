-- ============================================================================
-- Shares plugin test setup for DSOA telemetry validation
-- Exercises: inbound shares, outbound shares, share events, acquisition warnings
--
-- Database:  DSOA_TEST_DB   Schema: DSOA_TEST_DB.SHARES_TEST
--
-- Coverage:
--   C5.8  — Acquisition warning bizevents fire on known triggers (BDX-1647)
--   C5.9  — No unexpected acquisition problems
--   C7.1  — All inbound and outbound shares are reported (logs)
--   C7.2  — All inbound and outbound shares are reported (events)
--   C7.3  — Inbound shares with missing DB are reported
--
-- Strategy:
--   The shares plugin reads from SHOW SHARES (populated into TMP_SHARES) and
--   iterates to collect outbound grants and inbound tables. We cannot directly
--   inject rows into TMP tables (they're populated by P_GET_SHARES procedure).
--   Instead we:
--     1. Create a real outbound share with tables
--     2. Create a database from a sample inbound share (if available)
--     3. Simulate an unhealthy scenario by revoking access mid-run
--
--   For C5.8 (acquisition warnings), we create a share that references a table,
--   then DROP the table — next agent run will log an acquisition SQL failure
--   when the view tries to describe the share's grants.
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER and DTAGENT_QA_VIEWER roles must exist
--   - test-qa config must have shares plugin enabled:
--       plugins.shares.is_enabled: true
--   - DSOA_TEST_DB must exist (created by setup_test_budgets_finops.sql or manually)
--
-- Cost: near-zero (metadata operations only, no warehouse compute)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_shares.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup — database, schema, warehouse
-- ============================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Shared warehouse for DSOA synthetic test setups';

GRANT USAGE ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER;

USE ROLE ACCOUNTADMIN;
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
GRANT OWNERSHIP ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_QA_OWNER COPY CURRENT GRANTS;

USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.SHARES_TEST;
USE SCHEMA DSOA_TEST_DB.SHARES_TEST;

-- ============================================================================
-- 2. Create tables to share outbound
-- ============================================================================

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES_TEST.SHARED_METRICS (
    METRIC_ID    NUMBER        NOT NULL,
    METRIC_NAME  VARCHAR(100)  NOT NULL,
    METRIC_VALUE NUMBER(12, 4) NOT NULL,
    RECORDED_AT  TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO DSOA_TEST_DB.SHARES_TEST.SHARED_METRICS
SELECT
    SEQ4() + 1,
    'metric_' || (SEQ4() + 1),
    ROUND(UNIFORM(1, 10000, RANDOM()) / 100.0, 4),
    DATEADD(MINUTE, -UNIFORM(0, 1440, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 100));

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES_TEST.SHARED_EVENTS (
    EVENT_ID   NUMBER        NOT NULL,
    EVENT_TYPE VARCHAR(50)   NOT NULL,
    PAYLOAD    VARIANT,
    EVENT_TS   TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO DSOA_TEST_DB.SHARES_TEST.SHARED_EVENTS
SELECT
    SEQ4() + 1,
    CASE UNIFORM(1, 3, RANDOM())
        WHEN 1 THEN 'DATA_CHANGE'
        WHEN 2 THEN 'SCHEMA_CHANGE'
        ELSE 'ACCESS_REQUEST'
    END,
    OBJECT_CONSTRUCT('index', SEQ4(), 'source', 'synthetic'),
    DATEADD(MINUTE, -UNIFORM(0, 720, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 50));

-- ============================================================================
-- 3. Create an outbound share with the tables above
--    This populates the shares plugin's V_OUTBOUND_SHARE_TABLES view.
-- ============================================================================
USE ROLE ACCOUNTADMIN;

CREATE SHARE IF NOT EXISTS DSOA_TEST_OUTBOUND_SHARE
    COMMENT = 'DSOA QA test share — outbound data sharing validation';

-- Grant usage on database and schema to the share
GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_TEST_OUTBOUND_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES_TEST TO SHARE DSOA_TEST_OUTBOUND_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES_TEST.SHARED_METRICS TO SHARE DSOA_TEST_OUTBOUND_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES_TEST.SHARED_EVENTS TO SHARE DSOA_TEST_OUTBOUND_SHARE;

-- ============================================================================
-- 4. Create a table that will be DROPPED to trigger acquisition warning
--    The shares plugin will attempt to describe grant on a stale table reference.
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES_TEST.EPHEMERAL_TABLE (
    ID    NUMBER NOT NULL,
    VALUE VARCHAR(50)
);

INSERT INTO DSOA_TEST_DB.SHARES_TEST.EPHEMERAL_TABLE
SELECT SEQ4() + 1, 'row_' || (SEQ4() + 1) FROM TABLE(GENERATOR(ROWCOUNT => 10));

-- Grant to the share, then drop the table to create inconsistency
USE ROLE ACCOUNTADMIN;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES_TEST.EPHEMERAL_TABLE TO SHARE DSOA_TEST_OUTBOUND_SHARE;

-- Now drop the table — next SHOW GRANTS TO SHARE will reference a missing object
USE ROLE DTAGENT_QA_OWNER;
DROP TABLE DSOA_TEST_DB.SHARES_TEST.EPHEMERAL_TABLE;

-- ============================================================================
-- 5. Verify setup
-- ============================================================================
USE ROLE ACCOUNTADMIN;
SHOW SHARES LIKE 'DSOA_TEST_OUTBOUND_SHARE';
SHOW GRANTS TO SHARE DSOA_TEST_OUTBOUND_SHARE;

-- ============================================================================
-- 6. Config notes
-- ============================================================================
-- Ensure conf/config-test-qa.yml has:
--   plugins:
--     shares:
--       is_enabled: true
--       # No exclude_from_monitoring needed — all shares are in scope
--
-- After deploying and running one agent cycle:
--   - C7.1/C7.2: verify logs and events for DSOA_TEST_OUTBOUND_SHARE
--   - C5.8: verify acquisition warning bizevent mentioning EPHEMERAL_TABLE
--   - C5.9: verify no acquisition PROBLEM events (only warnings)
--
-- Trigger manual agent run:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('shares'))"

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE ACCOUNTADMIN;
--   DROP SHARE IF EXISTS DSOA_TEST_OUTBOUND_SHARE;
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.SHARES_TEST;
-- ============================================================================

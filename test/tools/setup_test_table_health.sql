-- ============================================================================
-- Table Health plugin test setup for DSOA telemetry validation
-- Exercises: storage metrics, clustering metrics, and derived metrics
--
-- Coverage:
--   C2.9  — Table health: storage metrics are reported (BDX-1829)
--   C2.10 — Table health: clustering metrics are reported (BDX-1829)
--
-- Strategy:
--   The table_health plugin reads from:
--     - SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS (active_bytes, time_travel_bytes, etc.)
--     - P_COLLECT_CLUSTERING_INFO() which calls SYSTEM$CLUSTERING_INFORMATION()
--
--   For storage metrics: create tables large enough to exceed min_table_bytes
--   threshold (default 1 GB). Since we can't create 1 GB in a test easily,
--   we set min_table_bytes: 0 in config to capture ALL tables.
--
--   For clustering metrics: create a table with a CLUSTER BY key and insert
--   enough data to generate measurable clustering depth/overlap.
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - table_health plugin must be enabled with min_table_bytes: 0
--
-- ACCOUNT_USAGE lag: TABLE_STORAGE_METRICS has ~2h lag.
-- Allow 2-3h after table creation for metrics to appear.
--
-- Cost: minimal (~0.01 credits for data insertion)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_table_health.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Shared warehouse for DSOA synthetic test setups';
GRANT USAGE ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER;

USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.TABLE_HEALTH_TEST;
USE SCHEMA DSOA_TEST_DB.TABLE_HEALTH_TEST;

-- ============================================================================
-- 2. Create a CLUSTERED table with significant row count
--    Clustering metrics require a table with:
--      - A CLUSTER BY key defined
--      - Enough micro-partitions to have measurable depth/overlap
--    ~100K rows on XSMALL should produce 3-5 micro-partitions.
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.TABLE_HEALTH_TEST.CLUSTERED_FACTS (
    ID          NUMBER        NOT NULL,
    CATEGORY    VARCHAR(20)   NOT NULL,
    REGION      VARCHAR(20)   NOT NULL,
    AMOUNT      NUMBER(12, 2) NOT NULL,
    CREATED_AT  TIMESTAMP_NTZ NOT NULL
)
CLUSTER BY (CATEGORY, REGION);

-- Insert 100K rows with varied distribution
INSERT INTO DSOA_TEST_DB.TABLE_HEALTH_TEST.CLUSTERED_FACTS
SELECT
    SEQ4() + 1,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'ELECTRONICS'
        WHEN 2 THEN 'CLOTHING'
        WHEN 3 THEN 'FOOD'
        WHEN 4 THEN 'AUTOMOTIVE'
        ELSE 'OTHER'
    END,
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'NORTH'
        WHEN 2 THEN 'SOUTH'
        WHEN 3 THEN 'EAST'
        ELSE 'WEST'
    END,
    ROUND(UNIFORM(100, 99999, RANDOM()) / 100.0, 2),
    DATEADD(SECOND, -UNIFORM(0, 7776000, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 100000));

-- ============================================================================
-- 3. Create a non-clustered table for storage-only metrics
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.TABLE_HEALTH_TEST.LARGE_EVENTS (
    EVENT_ID    NUMBER        NOT NULL,
    EVENT_TYPE  VARCHAR(50)   NOT NULL,
    PAYLOAD     VARCHAR(1000) NOT NULL,
    EVENT_TS    TIMESTAMP_NTZ NOT NULL
);

-- Insert 50K rows with larger payloads to generate measurable bytes
INSERT INTO DSOA_TEST_DB.TABLE_HEALTH_TEST.LARGE_EVENTS
SELECT
    SEQ4() + 1,
    CASE UNIFORM(1, 6, RANDOM())
        WHEN 1 THEN 'USER_LOGIN'
        WHEN 2 THEN 'PAGE_VIEW'
        WHEN 3 THEN 'PURCHASE'
        WHEN 4 THEN 'SEARCH'
        WHEN 5 THEN 'API_CALL'
        ELSE 'SYSTEM_EVENT'
    END,
    REPEAT('x', UNIFORM(100, 800, RANDOM())),
    DATEADD(SECOND, -UNIFORM(0, 2592000, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 50000));

-- ============================================================================
-- 4. Create a table with TIME_TRAVEL data (delete + undrop scenario)
--    Deleting rows generates time_travel_bytes in TABLE_STORAGE_METRICS.
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.TABLE_HEALTH_TEST.TIME_TRAVEL_TABLE (
    ID    NUMBER NOT NULL,
    DATA  VARCHAR(200) NOT NULL
) DATA_RETENTION_TIME_IN_DAYS = 1;

INSERT INTO DSOA_TEST_DB.TABLE_HEALTH_TEST.TIME_TRAVEL_TABLE
SELECT SEQ4() + 1, REPEAT('d', 100)
FROM TABLE(GENERATOR(ROWCOUNT => 10000));

-- Delete half the rows to generate time_travel_bytes
DELETE FROM DSOA_TEST_DB.TABLE_HEALTH_TEST.TIME_TRAVEL_TABLE WHERE ID > 5000;

-- ============================================================================
-- 5. Verify clustering info is available
-- ============================================================================
SELECT SYSTEM$CLUSTERING_INFORMATION('DSOA_TEST_DB.TABLE_HEALTH_TEST.CLUSTERED_FACTS');

-- ============================================================================
-- 6. Config requirements
-- ============================================================================
-- In conf/config-test-qa.yml:
--   plugins:
--     table_health:
--       is_enabled: true
--       min_table_bytes: 0           # Capture all tables (default 1 GB too high for test)
--       max_tables: 500
--       clustering_enabled: true
--       include:
--         - "DSOA_TEST_DB.TABLE_HEALTH_TEST.%"
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm
--
-- Trigger:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('table_health'))"

-- ============================================================================
-- 7. Verification DQL (run 2-3h after table creation for ACCOUNT_USAGE lag)
-- ============================================================================
-- C2.9 — Storage metrics:
--   timeseries avg(snowflake.table.active_bytes), by:{deployment.environment}
--   | filter deployment.environment == "DEV-{CURR_TAG}"
--
-- C2.10 — Clustering metrics:
--   timeseries avg(snowflake.table.clustering.depth), by:{deployment.environment}
--   | filter deployment.environment == "DEV-{CURR_TAG}"

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.TABLE_HEALTH_TEST CASCADE;
-- ============================================================================

-- ============================================================================
-- Query Cost Attribution test setup for DSOA telemetry validation
-- Exercises: cost attribution metrics from QUERY_ATTRIBUTION_HISTORY (BDX-703)
--
-- Coverage:
--   C2.16 — Query cost attribution metrics reported
--           snowflake.credits.attributed_compute,
--           snowflake.credits.query_acceleration,
--           snowflake.cost_attribution.query_count
--
-- Strategy:
--   The query_history plugin (when query_cost_attribution.enabled=true) reads
--   from SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY which provides
--   per-query credit attribution broken down by:
--     - CREDITS_ATTRIBUTED_COMPUTE
--     - CREDITS_USED_QUERY_ACCELERATION
--     - QUERY_COUNT (aggregated)
--
--   QUERY_ATTRIBUTION_HISTORY has an ~8h latency from query execution.
--   We generate compute-heavy queries that will appear in this view after
--   the lag period.
--
--   The plugin aggregates by warehouse + database and emits metrics per
--   attribution window (typically hourly rollups from Snowflake).
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - query_history plugin must have query_cost_attribution.enabled: true
--   - Snowflake account must support QUERY_ATTRIBUTION_HISTORY
--     (Enterprise Edition, BCR-2024_02+)
--
-- LATENCY: This test is [DEFERRED] — seed queries now, verify after 8+ hours.
--
-- Cost: ~0.05-0.1 credits (compute-heavy queries on XSMALL)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_query_cost_attribution.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.COST_ATTRIBUTION_TEST;
USE SCHEMA DSOA_TEST_DB.COST_ATTRIBUTION_TEST;

-- ============================================================================
-- 2. Create a large table for compute-heavy queries
--    Need queries that consume measurable compute credits to appear in
--    QUERY_ATTRIBUTION_HISTORY.
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE (
    ID          NUMBER        NOT NULL,
    CATEGORY    VARCHAR(20)   NOT NULL,
    REGION      VARCHAR(20)   NOT NULL,
    AMOUNT      NUMBER(12, 4) NOT NULL,
    DESCRIPTION VARCHAR(500)  NOT NULL,
    CREATED_AT  TIMESTAMP_NTZ NOT NULL
);

-- Insert 200K rows to make queries non-trivial
INSERT INTO DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE
SELECT
    SEQ4() + 1,
    CASE UNIFORM(1, 8, RANDOM())
        WHEN 1 THEN 'COMPUTE'
        WHEN 2 THEN 'STORAGE'
        WHEN 3 THEN 'NETWORK'
        WHEN 4 THEN 'DATABASE'
        WHEN 5 THEN 'SECURITY'
        WHEN 6 THEN 'ANALYTICS'
        WHEN 7 THEN 'STREAMING'
        ELSE 'OTHER'
    END,
    CASE UNIFORM(1, 6, RANDOM())
        WHEN 1 THEN 'US-EAST'
        WHEN 2 THEN 'US-WEST'
        WHEN 3 THEN 'EU-WEST'
        WHEN 4 THEN 'EU-CENTRAL'
        WHEN 5 THEN 'APAC'
        ELSE 'GLOBAL'
    END,
    ROUND(UNIFORM(1, 999999, RANDOM()) / 100.0, 4),
    REPEAT('x', UNIFORM(100, 400, RANDOM())),
    DATEADD(SECOND, -UNIFORM(0, 7776000, RANDOM()), CURRENT_TIMESTAMP())
FROM TABLE(GENERATOR(ROWCOUNT => 200000));

-- ============================================================================
-- 3. Execute compute-heavy queries
--    These consume measurable credits and will appear in QUERY_ATTRIBUTION_HISTORY.
-- ============================================================================

-- Heavy aggregation (full table scan + group by)
SELECT
    CATEGORY,
    REGION,
    COUNT(*) AS cnt,
    SUM(AMOUNT) AS total_amount,
    AVG(AMOUNT) AS avg_amount,
    STDDEV(AMOUNT) AS stddev_amount,
    MEDIAN(AMOUNT) AS median_amount
FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE
GROUP BY CATEGORY, REGION
ORDER BY total_amount DESC;

-- Self-join (forces hash join, higher compute cost)
SELECT
    a.CATEGORY,
    COUNT(*) AS match_count,
    SUM(a.AMOUNT + b.AMOUNT) AS combined_amount
FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE a
JOIN DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE b
    ON a.CATEGORY = b.CATEGORY AND a.REGION = b.REGION AND a.ID != b.ID
WHERE a.AMOUNT > 5000
GROUP BY a.CATEGORY
LIMIT 100;

-- Window function query (sorts entire dataset)
SELECT
    ID, CATEGORY, REGION, AMOUNT,
    ROW_NUMBER() OVER (PARTITION BY CATEGORY ORDER BY AMOUNT DESC) AS rank_in_category,
    SUM(AMOUNT) OVER (PARTITION BY REGION ORDER BY CREATED_AT ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) AS rolling_sum
FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE
QUALIFY rank_in_category <= 10;

-- Multiple full scans with different predicates
SELECT COUNT(*), SUM(AMOUNT) FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE WHERE AMOUNT > 1000;
SELECT COUNT(*), AVG(LENGTH(DESCRIPTION)) FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE WHERE REGION = 'EU-WEST';
SELECT CATEGORY, COUNT(DISTINCT REGION), MAX(AMOUNT) FROM DSOA_TEST_DB.COST_ATTRIBUTION_TEST.HEAVY_TABLE GROUP BY CATEGORY;

-- ============================================================================
-- 4. Verify QUERY_ATTRIBUTION_HISTORY availability
--    This view may not be available on all account editions.
-- ============================================================================
SELECT
    'QUERY_ATTRIBUTION_HISTORY' AS source_view,
    COUNT(*) AS row_count,
    MIN(START_TIME) AS earliest,
    MAX(START_TIME) AS latest
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
WHERE START_TIME >= DATEADD(HOUR, -48, CURRENT_TIMESTAMP());

-- ============================================================================
-- 5. Config requirements
-- ============================================================================
-- In conf/config-test-qa.yml:
--   plugins:
--     query_history:
--       is_enabled: true
--       query_cost_attribution:
--         enabled: true
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

-- ============================================================================
-- 6. Verification DQL (run 8+ hours after executing this script)
-- ============================================================================
-- C2.16 — Cost attribution metrics:
--   timeseries avg(snowflake.credits.attributed_compute), by:{deployment.environment}
--   | filter deployment.environment == "DEV-095"
--
-- Additional checks:
--   fetch logs
--   | filter dsoa.run.context == "query_cost_attribution"
--   | filter deployment.environment == "DEV-095"
--   | summarize count(), by: {snowflake.warehouse.name}
--
-- Expected: rows with credit values > 0 for DSOA_TEST_WH

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.COST_ATTRIBUTION_TEST CASCADE;
-- ============================================================================

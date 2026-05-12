-- ============================================================================
-- Resource Monitor Alert Events test setup for DSOA telemetry validation
-- Exercises threshold-crossing Davis events at 50/80/90/100% credit levels.
--
-- Coverage:
--   C5.10 — Resource monitor credit alert events (BDX-623)
--   C3.6  — Warnings on missing warehouse and global resource monitors
--
-- Strategy:
--   The resource_monitors plugin reads SHOW RESOURCE MONITORS and computes
--   used_pct = 100 * credits_used / credit_quota. It then determines which
--   threshold band [info=50, warn=80, critical=90, exhausted=100] the monitor
--   is in and emits Davis events on band transitions.
--
--   We create multiple resource monitors with different credit_quota values
--   and assign them to test warehouses. By running queries on those warehouses,
--   credits accumulate naturally. For immediate testing we use LOW quotas so
--   that even minimal warehouse activity pushes past thresholds.
--
--   We also create a warehouse WITHOUT a resource monitor (triggers C3.6 warning).
--
-- Prerequisites:
--   - ACCOUNTADMIN role (resource monitors require it)
--   - DTAGENT_QA_OWNER and DTAGENT_QA_VIEWER roles must exist
--   - test-qa config must have resource_monitors plugin enabled:
--       plugins.resource_monitors.is_enabled: true
--       plugins.resource_monitors.credits_quota_thresholds.defaults: [50, 80, 90, 100]
--
-- Cost: minimal (~0.01 credits per warehouse resume)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_resource_monitor_alert.sql
-- ============================================================================

-- ============================================================================
-- 1. Create test warehouses (SYSADMIN)
-- ============================================================================
USE ROLE SYSADMIN;

-- Warehouse that will be monitored (low quota = quick threshold breach)
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_RM_WH_LOW
    WAREHOUSE_SIZE     = XSMALL
    AUTO_SUSPEND       = 60
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT            = 'DSOA QA: low-quota resource monitor test';

-- Warehouse WITHOUT a resource monitor (triggers unmonitored warning)
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_UNMONITORED_WH
    WAREHOUSE_SIZE     = XSMALL
    AUTO_SUSPEND       = 60
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT            = 'DSOA QA: deliberately unmonitored warehouse for C3.6';

-- ============================================================================
-- 2. Create resource monitors with LOW quotas (ACCOUNTADMIN)
-- ============================================================================
USE ROLE ACCOUNTADMIN;

-- A resource monitor with 1 credit quota — even a few seconds of XSMALL usage
-- will push past the 50% threshold (0.5 credits).
-- Triggers: 50% (NOTIFY), 80% (NOTIFY), 90% (NOTIFY), 100% (SUSPEND)
CREATE OR REPLACE RESOURCE MONITOR DSOA_TEST_RM_LOW_QUOTA
    WITH CREDIT_QUOTA = 1
    FREQUENCY        = MONTHLY
    START_TIMESTAMP  = IMMEDIATELY
    TRIGGERS
        ON 50  PERCENT DO NOTIFY
        ON 80  PERCENT DO NOTIFY
        ON 90  PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND;

-- A resource monitor with 5 credit quota — moderate threshold
CREATE OR REPLACE RESOURCE MONITOR DSOA_TEST_RM_MED_QUOTA
    WITH CREDIT_QUOTA = 5
    FREQUENCY        = MONTHLY
    START_TIMESTAMP  = IMMEDIATELY
    TRIGGERS
        ON 75  PERCENT DO NOTIFY
        ON 90  PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND;

-- Assign the low-quota monitor to the test warehouse
ALTER WAREHOUSE DSOA_TEST_RM_WH_LOW SET RESOURCE_MONITOR = DSOA_TEST_RM_LOW_QUOTA;

-- Grant ownership to QA owner for management
GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_RM_WH_LOW
    TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;
GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_UNMONITORED_WH
    TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;

-- ============================================================================
-- 3. Generate warehouse activity to consume credits
--    Even 1-2 minutes of XSMALL runtime = ~0.03 credits per minute
--    With 1 credit quota, 50% = 0.5 credits ≈ 17 minutes of runtime.
--    We run queries to ensure the warehouse is active.
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_RM_WH_LOW;

-- Run a few queries to keep the warehouse active and consuming credits
SELECT SUM(UNIFORM(1, 1000, RANDOM())) FROM TABLE(GENERATOR(ROWCOUNT => 10000));
SELECT COUNT(*) FROM TABLE(GENERATOR(ROWCOUNT => 50000));
SELECT CURRENT_TIMESTAMP(), SUM(SEQ4()) FROM TABLE(GENERATOR(ROWCOUNT => 100000));

-- Also run on the unmonitored warehouse to make it visible
USE WAREHOUSE DSOA_TEST_UNMONITORED_WH;
SELECT COUNT(*) FROM TABLE(GENERATOR(ROWCOUNT => 1000));

-- ============================================================================
-- 4. Verify setup
-- ============================================================================
USE ROLE ACCOUNTADMIN;
SHOW RESOURCE MONITORS LIKE 'DSOA_TEST_RM%';
SHOW WAREHOUSES LIKE 'DSOA_TEST_%';

-- Check current credit usage vs quota
SELECT
    "name",
    "credit_quota",
    "used_credits",
    ROUND(100 * "used_credits" / NULLIF("credit_quota", 0), 1) AS used_pct
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-2)))
WHERE "name" LIKE 'DSOA_TEST_RM%';

-- ============================================================================
-- 5. Config notes
-- ============================================================================
-- Ensure conf/config-test-qa.yml has:
--   plugins:
--     resource_monitors:
--       is_enabled: true
--       credits_quota_thresholds:
--         defaults: [50, 80, 90, 100]
--
-- After deploying and running one agent cycle:
--   - C5.10: verify events at thresholds (may need to wait for credits to accumulate)
--   - C3.6: verify WARN log for DSOA_TEST_UNMONITORED_WH
--
-- Trigger manual agent run:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('resource_monitors'))"
--
-- NOTE: Credit accumulation takes real time. For immediate testing of threshold
-- band transitions, you can manually ALTER the resource monitor to a very low quota
-- after credits have accumulated:
--   ALTER RESOURCE MONITOR DSOA_TEST_RM_LOW_QUOTA SET CREDIT_QUOTA = 0.01;
-- This instantly puts usage above 100%.

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE ACCOUNTADMIN;
--   ALTER WAREHOUSE DSOA_TEST_RM_WH_LOW SET RESOURCE_MONITOR = NULL;
--   DROP RESOURCE MONITOR IF EXISTS DSOA_TEST_RM_LOW_QUOTA;
--   DROP RESOURCE MONITOR IF EXISTS DSOA_TEST_RM_MED_QUOTA;
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP WAREHOUSE IF EXISTS DSOA_TEST_RM_WH_LOW;
--   DROP WAREHOUSE IF EXISTS DSOA_TEST_UNMONITORED_WH;
-- ============================================================================

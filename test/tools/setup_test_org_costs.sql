-- ============================================================================
-- Org Costs plugin test setup for DSOA telemetry validation
-- Exercises: organization-level cost metrics (BDX-682, requires ORGADMIN)
--
-- Coverage:
--   C2.12 — Org costs: credit metrics are reported
--   C2.13 — Org costs: storage metrics are reported
--   C2.14 — Org costs: billing/contract balance reported
--
-- Strategy:
--   The org_costs plugin reads from SNOWFLAKE.ORGANIZATION_USAGE views:
--     - METERING_DAILY_HISTORY (credits by account)
--     - STORAGE_DAILY_HISTORY (average stored bytes by account)
--     - DATA_TRANSFER_DAILY_HISTORY (bytes transferred)
--     - USAGE_IN_CURRENCY_DAILY (billing in currency)
--     - REMAINING_BALANCE_DAILY (contract capacity balance)
--
--   These views are READ-ONLY system views populated by Snowflake's billing
--   system. We CANNOT insert synthetic data. However, any active Snowflake
--   account with ORGADMIN privileges will have data in these views from
--   normal operations (warehouse usage, storage, etc.).
--
--   This script:
--     1. Verifies ORGADMIN access is available
--     2. Queries each source view to confirm data exists
--     3. Grants the necessary roles to the DSOA viewer
--     4. Documents expected metrics and verification steps
--
-- Prerequisites:
--   - ORGADMIN role must be granted to the connection user
--   - Organization must have multiple accounts (for meaningful org-level data)
--   - org_costs plugin must be enabled in config
--
-- Cost: zero (read-only queries)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_org_costs.sql
-- ============================================================================

-- ============================================================================
-- 1. Verify ORGADMIN access
-- ============================================================================
USE ROLE ORGADMIN;

-- If this fails, the connection user does not have ORGADMIN — skip org_costs tests
SELECT CURRENT_ROLE() AS current_role, CURRENT_ACCOUNT() AS account;

-- ============================================================================
-- 2. Check data availability in each source view
-- ============================================================================

-- Metering (credits by account — should have data from past 48h of normal usage)
SELECT
    'METERING_DAILY_HISTORY' AS source_view,
    COUNT(*) AS row_count,
    MIN(USAGE_DATE) AS earliest_date,
    MAX(USAGE_DATE) AS latest_date,
    COUNT(DISTINCT ACCOUNT_NAME) AS distinct_accounts
FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
WHERE USAGE_DATE >= DATEADD(DAY, -7, CURRENT_DATE());

-- Storage (average bytes stored per account)
SELECT
    'STORAGE_DAILY_HISTORY' AS source_view,
    COUNT(*) AS row_count,
    MIN(USAGE_DATE) AS earliest_date,
    MAX(USAGE_DATE) AS latest_date,
    COUNT(DISTINCT ACCOUNT_NAME) AS distinct_accounts
FROM SNOWFLAKE.ORGANIZATION_USAGE.STORAGE_DAILY_HISTORY
WHERE USAGE_DATE >= DATEADD(DAY, -7, CURRENT_DATE());

-- Data transfer (bytes transferred between regions/clouds)
SELECT
    'DATA_TRANSFER_DAILY_HISTORY' AS source_view,
    COUNT(*) AS row_count,
    MIN(USAGE_DATE) AS earliest_date,
    MAX(USAGE_DATE) AS latest_date
FROM SNOWFLAKE.ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY
WHERE USAGE_DATE >= DATEADD(DAY, -7, CURRENT_DATE());

-- Billing usage in currency
SELECT
    'USAGE_IN_CURRENCY_DAILY' AS source_view,
    COUNT(*) AS row_count,
    MIN(USAGE_DATE) AS earliest_date,
    MAX(USAGE_DATE) AS latest_date,
    COUNT(DISTINCT ACCOUNT_NAME) AS distinct_accounts
FROM SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY
WHERE USAGE_DATE >= DATEADD(DAY, -7, CURRENT_DATE());

-- Remaining balance (contract capacity)
SELECT
    'REMAINING_BALANCE_DAILY' AS source_view,
    COUNT(*) AS row_count,
    MIN(DATE) AS earliest_date,
    MAX(DATE) AS latest_date
FROM SNOWFLAKE.ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY
WHERE DATE >= DATEADD(DAY, -7, CURRENT_DATE());

-- ============================================================================
-- 3. Grant ORGANIZATION_USAGE_VIEWER to DSOA viewer role
--    The org_costs plugin needs this to read org-level views.
-- ============================================================================
USE ROLE ACCOUNTADMIN;

-- Grant the database role that provides access to ORGANIZATION_USAGE
GRANT DATABASE ROLE SNOWFLAKE.ORGANIZATION_USAGE_VIEWER TO ROLE DTAGENT_QA_VIEWER;

-- Also grant ORGADMIN directly if needed (some views require it)
-- NOTE: This is a powerful role — only grant in test environments
GRANT ROLE ORGADMIN TO ROLE DTAGENT_QA_OWNER;

-- ============================================================================
-- 4. Config requirements
-- ============================================================================
-- In conf/config-test-qa.yml:
--   plugins:
--     org_costs:
--       is_enabled: true
--       lookback_hours: 48
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm
--
-- Trigger manual run:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('org_costs'))"

-- ============================================================================
-- 5. Verification DQL
-- ============================================================================
-- C2.12 — Credit metrics:
--   timeseries avg(snowflake.org.credits.used), by:{deployment.environment}
--   | filter deployment.environment == "DEV-095"
--
-- C2.13 — Storage metrics:
--   timeseries avg(snowflake.org.data.stored), by:{deployment.environment}
--   | filter deployment.environment == "DEV-095"
--
-- C2.14 — Billing balance:
--   timeseries avg(snowflake.org.billing.capacity_balance)
--   | filter deployment.environment == "DEV-095"
--
-- NOTE: If any source view returns 0 rows above, that metric cannot be tested.
-- Data transfer and remaining balance may be empty in single-account test orgs.
-- Mark those items as [SKIP: no org data available] in the checklist.

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE ACCOUNTADMIN;
--   REVOKE DATABASE ROLE SNOWFLAKE.ORGANIZATION_USAGE_VIEWER FROM ROLE DTAGENT_QA_VIEWER;
--   REVOKE ROLE ORGADMIN FROM ROLE DTAGENT_QA_OWNER;
-- ============================================================================

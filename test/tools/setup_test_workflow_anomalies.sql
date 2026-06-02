-- ============================================================================
-- setup_test_workflow_anomalies.sql
-- Supplemental synthetic data for DSOA workflow execution testing.
-- Covers workflows NOT addressed by setup_test_workflows.sql:
--
--   login_history  → Security Anomaly Detection
--   query_history  → Long-Running Queries Detection (via SYSTEM$WAIT)
--   query_history  → Warehouse Sensitive Change Alert (DDL events)
--   shares         → Shares Broken Detection (unhealthy share)
--   org_costs      → Org Contract Balance Warning  [SKIP — requires ORGADMIN]
--
-- USAGE:
--   snow sql -c snow_agent_test-qa -f test/tools/setup_test_workflow_anomalies.sql
--
-- PREREQUISITES:
--   setup_test_workflows.sql must have been run first (creates DSOA_TEST_DB.WORKFLOWS).
--
-- NOTE: This script uses only DTAGENT_QA_OWNER — no SYSADMIN calls.
--       The shares section requires an existing inbound share to reference.
--       The org_costs section is omitted — it requires ORGADMIN privileges
--       and cannot be tested without them.  Mark E2.5 as SKIP when ORGADMIN
--       is unavailable (consistent with HAS_ORGADMIN checks in qa-runner).
--
-- CLEANUP: see bottom of this file.
-- ============================================================================

USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DTAGENT_QA_WH;
USE DATABASE DSOA_TEST_DB;

-- ============================================================================
-- 1. Security Anomaly Detection
--    The security-anomaly-detection workflow monitors login counts, session
--    counts, query volumes, and data scan rates per user via Davis AI.
--    DSOA's login_history plugin reads ACCOUNT_USAGE.LOGIN_HISTORY and emits
--    snowflake.login.attempts.* metrics.
--
--    We cannot directly generate failed login attempts via SQL, but we can:
--    (a) Create a test user and attempt connections — not safe in automation.
--    (b) Verify the workflow DQL runs against existing login history data.
--
--    Action: document this as a "data-presence" test.  The workflow will
--    execute against real account login history; the test passes if Davis
--    returns output (even empty — no anomaly detected).
-- ============================================================================

-- No DDL needed — security-anomaly-detection reads from ACCOUNT_USAGE.LOGIN_HISTORY
-- which is populated by normal agent and user activity on the account.
-- Verify that login_history data exists:
SELECT
    'login_history_check'   AS check_name,
    COUNT(*)                AS record_count,
    MIN(event_timestamp)    AS earliest_event,
    MAX(event_timestamp)    AS latest_event
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE event_timestamp > DATEADD(HOUR, -24, CURRENT_TIMESTAMP());

-- ============================================================================
-- 2. Long-Running Queries Detection (supplemental heavy queries)
--    The long-running-queries workflow detects max execution time anomalies
--    per warehouse.  We generate heavier queries against the existing
--    WORKFLOWS schema tables to produce measurable execution times.
--    SYSTEM$WAIT is used to simulate deliberate slowness.
-- ============================================================================

USE SCHEMA DSOA_TEST_DB.WORKFLOWS;

-- Slow queries to simulate long-running pattern
-- Note: SYSTEM$WAIT requires a small credit spend but is the safest method
-- to generate controlled long-running query history without side effects.
CALL SYSTEM$WAIT(3);  -- 3-second artificial pause (simulates a slow query)
CALL SYSTEM$WAIT(5);  -- 5-second pause

-- Heavy aggregation to increase execution time naturally
SELECT
    o.STATUS,
    c.REGION,
    COUNT(*)                AS ORDERS,
    SUM(o.AMOUNT)           AS TOTAL,
    AVG(o.AMOUNT)           AS AVG_AMOUNT,
    STDDEV(o.AMOUNT)        AS STDDEV_AMOUNT,
    MIN(o.ORDER_TS)         AS FIRST_ORDER,
    MAX(o.ORDER_TS)         AS LAST_ORDER
FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS o
JOIN DSOA_TEST_DB.WORKFLOWS.DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
CROSS JOIN DSOA_TEST_DB.WORKFLOWS.FACTS_EVENTS e
GROUP BY o.STATUS, c.REGION
ORDER BY TOTAL DESC;

CALL SYSTEM$WAIT(4);  -- Additional 4-second pause after heavy join

-- ============================================================================
-- 3. Warehouse Sensitive Change Alert
--    The warehouse-sensitive-change-alert workflow queries DSOA spans for
--    DDL operations on warehouses (snowflake.object.ddl.operation).
--    DSOA's query_history plugin captures DDL queries when
--    plugins.query_history.track_ddl_changes=true.
--
--    We generate DDL events on a test warehouse object.
--    Using a TEST_ prefixed warehouse to avoid impacting production objects.
-- ============================================================================

-- Create a test warehouse for DDL change simulation
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH_DDL_SIM
    WAREHOUSE_SIZE   = XSMALL
    AUTO_SUSPEND     = 60
    AUTO_RESUME      = TRUE
    COMMENT          = 'Temporary warehouse for DSOA DDL change simulation — safe to drop';

-- ALTER the warehouse to generate an ALTER DDL event
ALTER WAREHOUSE DSOA_TEST_WH_DDL_SIM SET AUTO_SUSPEND = 120;
ALTER WAREHOUSE DSOA_TEST_WH_DDL_SIM SET COMMENT = 'Updated comment — DSOA DDL simulation step 2';
ALTER WAREHOUSE DSOA_TEST_WH_DDL_SIM SET WAREHOUSE_SIZE = XSMALL;

-- Verify the warehouse exists and changes are recorded
SHOW WAREHOUSES LIKE 'DSOA_TEST_WH_DDL_SIM';

-- ============================================================================
-- 4. Shares Broken Detection
--    The shares-broken-detection workflow queries DSOA share telemetry for
--    shares with missing, unavailable, or degraded databases.
--    DSOA's shares plugin emits events for unhealthy inbound shares.
--
--    We cannot reliably create a "broken" share in a test environment without
--    ACCOUNTADMIN.  Instead, we verify the workflow executes against existing
--    share data (which may already include degraded shares in the test account).
--
--    For a forced broken-share simulation, use setup_test_shares.sql which
--    creates an inbound share pointing to a dropped database (requires the
--    shares test setup that already exists).
-- ============================================================================

-- Verify share data is available for the workflow to evaluate:
SELECT
    'shares_check'                          AS check_name,
    COUNT(*)                                AS total_shares,
    SUM(IFF(share_kind = 'INBOUND', 1, 0)) AS inbound_shares,
    SUM(IFF(share_kind = 'OUTBOUND', 1, 0)) AS outbound_shares
FROM SNOWFLAKE.ACCOUNT_USAGE.SHARES
WHERE created_on > DATEADD(DAY, -30, CURRENT_TIMESTAMP());

-- ============================================================================
-- 5. Org Contract Balance Warning  [DOCUMENTED SKIP — requires ORGADMIN]
--    The org-contract-balance-warning workflow reads org-level billing metrics
--    (snowflake.org.billing.*) which require ORGADMIN privileges.
--    This section is intentionally skipped.
--    Mark checklist item E2.5 as SKIP when HAS_ORGADMIN=false.
-- ============================================================================

SELECT 'org_contract_balance_warning: SKIP — requires ORGADMIN privileges' AS status;

-- ============================================================================
-- 6. Data Volume Anomaly — insert deliberate spike for Davis baseline
--    Adds a large batch of rows to FACTS_ORDERS to create a detectable spike.
--    Davis needs ~7 days of baseline data before detecting anomalies.
-- ============================================================================

-- Spike: 10x the normal row count in a single batch
INSERT INTO DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS
SELECT
    (SELECT MAX(ORDER_ID) FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS) + SEQ4() + 1,
    UNIFORM(1, 500, RANDOM()),
    ROUND(UNIFORM(10, 9999, RANDOM()) / 100.0, 2),
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'PENDING'
        WHEN 2 THEN 'SHIPPED'
        WHEN 3 THEN 'DELIVERED'
        ELSE 'CANCELLED'
    END,
    CURRENT_TIMESTAMP()
FROM TABLE(GENERATOR(ROWCOUNT => 30000));  -- 10x the baseline ~3000 rows

SELECT 'data_volume_spike_inserted' AS status, COUNT(*) AS new_total
FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS;

-- ============================================================================
-- 7. Credits Exhaustion Prediction — ensure metering data is present
--    The credits-exhaustion-prediction workflow uses resource_monitors plugin
--    data.  Verify resource monitor data is available (created by deploy).
-- ============================================================================

SHOW RESOURCE MONITORS;

-- ============================================================================
-- Verification summary
-- ============================================================================
SELECT 'setup_complete' AS status, CURRENT_TIMESTAMP() AS completed_at;

-- ============================================================================
-- CLEANUP (run when done testing):
--
--   ALTER WAREHOUSE DSOA_TEST_WH_DDL_SIM SUSPEND;
--   DROP WAREHOUSE IF EXISTS DSOA_TEST_WH_DDL_SIM;
--   DELETE FROM DSOA_TEST_DB.WORKFLOWS.FACTS_ORDERS WHERE ORDER_TS > DATEADD(MINUTE, -5, CURRENT_TIMESTAMP());
-- ============================================================================

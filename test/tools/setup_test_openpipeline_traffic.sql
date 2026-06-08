-- ============================================================================
-- OpenPipeline derived metrics traffic generation for DSOA telemetry validation
-- Exercises: login_history and tasks logs that OpenPipeline converts to metrics
--
-- Coverage:
--   C9.1 — Failed login attempts metric (snowflake.login.attempts.failed)
--   C9.2 — Successful login attempts metric (snowflake.login.attempts.successful)
--   C9.3 — Total login attempts metric (snowflake.login.attempts.total)
--   C9.4 — Failed task runs metric (snowflake.task.run.failed)
--   C9.5 — Cancelled task runs metric (snowflake.task.run.cancelled)
--   C9.6 — Successful task runs metric (snowflake.task.run.successful)
--
-- Strategy:
--   OpenPipeline rules extract metrics from DSOA log records. The rules are
--   deployed via docs/openpipeline/snowagent-logs-pipeline/snowagent-logs-pipeline.yml.
--   They match on:
--     - dsoa.run.context == "login_history" + snowflake.login.is_success field
--     - dsoa.run.context == "tasks" + snowflake.task.state field
--
--   To generate the source logs, we need:
--     1. Login attempts (successful + failed) — captured by login_history plugin
--        from SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
--     2. Task runs with varied states — captured by tasks plugin from
--        SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
--
--   For failed logins: attempt to connect with wrong password (generates
--   LOGIN_HISTORY entries with IS_SUCCESS='NO').
--   For task states: create tasks that succeed, fail (divide by zero), and
--   get cancelled (via ALTER TASK ... SUSPEND while running).
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - login_history and tasks plugins must be enabled
--   - OpenPipeline rules deployed:
--       ./scripts/deploy/deploy_dt_assets.sh --scope=openpipeline --env=test-qa
--
-- ACCOUNT_USAGE lag: LOGIN_HISTORY has ~2h lag; TASK_HISTORY has ~45min lag.
-- Allow 2-3h after running this script before verifying OpenPipeline metrics.
--
-- Cost: near-zero
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_openpipeline_traffic.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup — Tasks that produce varied states
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.OPENPIPELINE_TEST;
USE SCHEMA DSOA_TEST_DB.OPENPIPELINE_TEST;

-- ============================================================================
-- 2. Task that SUCCEEDS (generates snowflake.task.state = 'SUCCEEDED')
-- ============================================================================
CREATE OR REPLACE TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_SUCCESS
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '5 MINUTE'
AS
    SELECT 1 + 1 AS result;

-- ============================================================================
-- 3. Task that FAILS (generates snowflake.task.state = 'FAILED')
--    Division by zero causes a runtime error.
-- ============================================================================
CREATE OR REPLACE TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_FAILURE
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '5 MINUTE'
AS
    SELECT 1 / 0 AS should_fail;

-- ============================================================================
-- 4. Task that will be CANCELLED
--    Strategy: create a long-running task, start it, then suspend it.
--    Snowflake records the interrupted execution as CANCELLED in TASK_HISTORY.
-- ============================================================================
CREATE OR REPLACE TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_CANCEL_TARGET
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '60 MINUTE'
AS
    -- Long query that will be interrupted
    SELECT SYSTEM$WAIT(30);

-- ============================================================================
-- 5. Resume tasks to start generating history
-- ============================================================================
ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_SUCCESS RESUME;
ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_FAILURE RESUME;
ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_CANCEL_TARGET RESUME;

-- ============================================================================
-- 6. Generate failed login attempts
--    NOTE: This requires running a separate snow CLI command with wrong password.
--    Snowflake will record the failed attempt in LOGIN_HISTORY.
--    Run from terminal (this WILL fail — that's the point):
--
--    snow sql --connection snow_agent_test-qa \
--      --password "WRONG_PASSWORD_DSOA_QA_TEST" \
--      -q "SELECT 1" 2>/dev/null || true
--
--    Repeat 3-5 times to generate multiple failed login entries.
--    The successful logins come from normal agent operation and this script.
-- ============================================================================

-- Successful logins are generated by this script's connection itself.
-- Additional successful logins come from every agent run.
SELECT 'Login traffic generated — this connection = 1 successful login' AS status;

-- ============================================================================
-- 7. Cancel the long-running task after it starts
--    Wait ~10 seconds for T_CANCEL_TARGET to start, then suspend it.
-- ============================================================================
-- NOTE: Execute this manually after T_CANCEL_TARGET has started:
--   ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_CANCEL_TARGET SUSPEND;
-- This records a CANCELLED state in TASK_HISTORY.

-- ============================================================================
-- 8. Verify setup
-- ============================================================================
SHOW TASKS IN SCHEMA DSOA_TEST_DB.OPENPIPELINE_TEST;

-- ============================================================================
-- 9. Verification (run after 2-3h for ACCOUNT_USAGE lag + 15min for OP metrics)
-- ============================================================================
-- DQL for OpenPipeline metrics:
--
--   # C9.1 - Failed logins:
--   timeseries count(snowflake.login.attempts.failed), by:{deployment.environment}
--
--   # C9.2 - Successful logins:
--   timeseries count(snowflake.login.attempts.successful), by:{deployment.environment}
--
--   # C9.4 - Failed tasks:
--   timeseries count(snowflake.task.run.failed), by:{deployment.environment}
--
--   # C9.5 - Cancelled tasks:
--   timeseries count(snowflake.task.run.cancelled), by:{deployment.environment}
--
--   # C9.6 - Successful tasks:
--   timeseries count(snowflake.task.run.successful), by:{deployment.environment}

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_SUCCESS SUSPEND;
--   ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_FAILURE SUSPEND;
--   ALTER TASK DSOA_TEST_DB.OPENPIPELINE_TEST.T_CANCEL_TARGET SUSPEND;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.OPENPIPELINE_TEST CASCADE;
-- ============================================================================

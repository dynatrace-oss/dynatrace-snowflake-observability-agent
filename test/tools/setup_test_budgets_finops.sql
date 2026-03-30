-- ============================================================================
-- Budgets & FinOps dashboard test setup for DSOA telemetry validation
-- Covers plugins: budgets, event_usage, warehouse_usage, resource_monitors
--
-- Database:  DSOA_TEST_DB   Schema: DSOA_TEST_DB.BUDGETS_FINOPS
--
-- Objects created:
--   1. A small test warehouse  (DSOA_TEST_FINOPS_WH)
--   2. A resource monitor      (DSOA_TEST_RM) assigned to that warehouse
--   3. A Snowflake Budget       (DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET)
--   4. An event table           (DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS)
--   5. A stored procedure + task that runs every 30 min:
--      - inserts rows into the event table  (drives event_usage telemetry)
--      - issues a few SELECT queries        (drives warehouse_usage/load telemetry)
--
-- Sections exercised by this data:
--   Section 1 (Budget Analysis)        -- budgets plugin: TMP_BUDGETS / TMP_BUDGET_SPENDING
--   Section 2 (Event Table Ingest)     -- event_usage plugin: ACCOUNT_USAGE.EVENT_USAGE_HISTORY
--   Section 3 (Warehouse Optimization) -- resource_monitors plugin: SHOW WAREHOUSES
--   Section 4 (Warehouse Load)         -- warehouse_usage plugin: ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
--
-- Cost: near-zero (X-Small warehouse, task runs every 30 min, minimal data)
--
-- ACCOUNT_USAGE lag:
--   EVENT_USAGE_HISTORY / WAREHOUSE_LOAD_HISTORY have a ~45-180 min ingestion
--   lag in Snowflake.  Sections 2 and 4 tiles will not be visible immediately
--   after first run -- allow up to 3 h before verifying those tiles.
--   Sections 1 and 3 (budgets, resource_monitors) appear within ~5 min.
--
-- Prerequisites:
--   DTAGENT_QA_OWNER and DTAGENT_QA_VIEWER roles must already exist (created
--   by the DSOA base deployment).  No AWS / cloud resources required.
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_budgets_finops.sql
-- ============================================================================

-- ---- STEP 1: Account-level grants (ACCOUNTADMIN required) -------------------
-- EXECUTE TASK lets DTAGENT_QA_OWNER resume the maintenance task.
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE DTAGENT_QA_OWNER;

-- ---- STEP 2: Test warehouse (SYSADMIN creates, then ownership to QA owner) --
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_FINOPS_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Test warehouse for DSOA Budgets & FinOps dashboard validation';

-- Transfer ownership so DTAGENT_QA_OWNER can manage it fully
USE ROLE ACCOUNTADMIN;
GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_FINOPS_WH
    TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;

-- ---- STEP 3: Resource monitor (ACCOUNTADMIN required for CREATE) ------------
-- A 100-credit monthly monitor assigned to DSOA_TEST_FINOPS_WH.
-- This populates Sections 3 (Warehouse Optimization) via SHOW RESOURCE MONITORS
-- and SHOW WAREHOUSES read by the resource_monitors plugin.
USE ROLE ACCOUNTADMIN;
CREATE RESOURCE MONITOR IF NOT EXISTS DSOA_TEST_RM
    WITH CREDIT_QUOTA = 100
    FREQUENCY        = MONTHLY
    START_TIMESTAMP  = IMMEDIATELY
    TRIGGERS
        ON 75  PERCENT DO NOTIFY
        ON 90  PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND;

-- Assign monitor to the test warehouse
ALTER WAREHOUSE DSOA_TEST_FINOPS_WH SET RESOURCE_MONITOR = DSOA_TEST_RM;

-- ---- STEP 4: Test database, schema, and event table (owner role) -----------
USE ROLE ACCOUNTADMIN;
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
GRANT OWNERSHIP ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_QA_OWNER COPY CURRENT GRANTS;
USE ROLE DTAGENT_QA_OWNER;
CREATE SCHEMA  IF NOT EXISTS DSOA_TEST_DB.BUDGETS_FINOPS;

-- Snowflake event table — inserting rows into it drives EVENT_USAGE_HISTORY
-- which the event_usage plugin reads (Section 2).
-- Use explicit column types to avoid truncation issues.
CREATE TABLE IF NOT EXISTS DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS (
    TIMESTAMP           TIMESTAMP_LTZ,
    resource_attributes VARCHAR(4096),
    body                VARIANT
) CLUSTER BY (TIMESTAMP::DATE);

-- ---- STEP 5: Custom budget with limit and linked resources -------------------
-- The ACCOUNT_ROOT_BUDGET does NOT support !GET_SPENDING_LIMIT(),
-- !GET_LINKED_RESOURCES(), or !GET_SPENDING_HISTORY() — those instance methods
-- only work on custom (database-scoped) budgets.  Creating a real custom budget
-- is required for tiles 1-3 (Budget spending vs limit, trend, by service type)
-- to populate.
--
-- Snowflake Budget DDL uses instance-method syntax (OBJECT!METHOD).
-- CREATE BUDGET does NOT support IF NOT EXISTS — omit it; re-running this step
-- when the budget already exists will raise an error that can be safely ignored.
--
-- We create DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET with a 50-credit limit
-- and link DSOA_TEST_FINOPS_WH as a monitored resource.
--
-- TAG-SUBSTITUTION NOTE (tagged environments such as test-qa):
--   prepare_deploy_script.sh rewrites DTAGENT_ SQL identifiers (DTAGENT_DB,
--   DTAGENT_WH, DTAGENT_VIEWER, etc.) when a core.tag is configured.
--   With tag=QA the deployed config table will contain the budget FQN exactly
--   as written in conf/config-<env>.yml — string literals are NOT rewritten.
--   Therefore write the FQN in the config file using the actual Snowflake object
--   names that will exist at runtime (e.g. DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET),
--   not DTAGENT_* placeholder names.
--
-- Grant the BUDGET_VIEWER app role to DTAGENT_QA_VIEWER so P_GET_BUDGETS can
-- call the instance methods on both the root budget and the custom budget.
USE ROLE ACCOUNTADMIN;
GRANT APPLICATION ROLE SNOWFLAKE.BUDGET_VIEWER TO ROLE DTAGENT_QA_VIEWER;

-- Create the custom budget (requires ACCOUNTADMIN or BUDGET privilege).
-- If the budget already exists this statement will raise an error — ignore it.
USE ROLE ACCOUNTADMIN;
CREATE BUDGET DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET;

-- Set a 50-credit monthly spending limit on the budget.
CALL DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET!SET_SPENDING_LIMIT(50);

-- Link the test warehouse so it counts against the budget.
CALL DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET!ADD_RESOURCE(
    '{"name": "DSOA_TEST_FINOPS_WH", "domain": "WAREHOUSE"}'
);

-- Grant usage on the budget schema so DTAGENT_QA_VIEWER can inspect it.
GRANT USAGE ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_QA_VIEWER;
GRANT USAGE ON SCHEMA   DSOA_TEST_DB.BUDGETS_FINOPS TO ROLE DTAGENT_QA_VIEWER;

-- Add the custom budget FQN to conf/config-test-qa.yml using the actual
-- Snowflake object names (NOT DTAGENT_* placeholders — those are only for
-- agent infrastructure objects, not user-created budgets):
--   plugins:
--     budgets:
--       monitored_budgets:
--         - "SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET"
--         - "DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET"
-- Then redeploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm
--
-- Verify the budget was created and limit is set:
CALL DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET!GET_SPENDING_LIMIT();
CALL DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET!GET_LINKED_RESOURCES();

-- ---- STEP 6: Stored procedure — generates load on each call ----------------
-- Inserts event-table rows (drives event_usage) and executes lightweight
-- queries on the test warehouse (drives warehouse_usage / load history).
USE ROLE DTAGENT_QA_OWNER;
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.BUDGETS_FINOPS.SP_GENERATE_LOAD()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    run_ts VARCHAR DEFAULT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS');
    i      NUMBER  DEFAULT 0;
BEGIN
    -- Insert 20 rows into the event table.
    -- Snowflake charges credits for event-table ingestion which then appears in
    -- ACCOUNT_USAGE.EVENT_USAGE_HISTORY (event_usage plugin, Section 2).
    INSERT INTO DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS (TIMESTAMP, resource_attributes, body)
    SELECT
        DATEADD(second, SEQ4(), CURRENT_TIMESTAMP()),
        'dsoa_test_run=' || :run_ts,
        OBJECT_CONSTRUCT('event_index', SEQ4(), 'run', :run_ts)
    FROM TABLE(GENERATOR(ROWCOUNT => 20));

    -- Run lightweight compute queries to generate load history entries
    -- (warehouse_usage plugin, Sections 3 & 4 via WAREHOUSE_LOAD_HISTORY).
    SELECT COUNT(*) FROM DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS;
    SELECT SUM(UNIFORM(1, 100, RANDOM())) FROM TABLE(GENERATOR(ROWCOUNT => 1000));
    SELECT MAX(TIMESTAMP) FROM DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS;

    RETURN 'Load generated at ' || :run_ts;
END;
$$;

-- ---- STEP 7: Task — runs the procedure every 30 minutes -------------------
CREATE OR REPLACE TASK DSOA_TEST_DB.BUDGETS_FINOPS.T_GENERATE_LOAD
    WAREHOUSE = DSOA_TEST_FINOPS_WH
    SCHEDULE  = '30 MINUTE'
AS
    CALL DSOA_TEST_DB.BUDGETS_FINOPS.SP_GENERATE_LOAD();

ALTER TASK DSOA_TEST_DB.BUDGETS_FINOPS.T_GENERATE_LOAD RESUME;

-- Run the procedure once immediately so data is available right away
-- (uses the test warehouse, which will auto-resume).
CALL DSOA_TEST_DB.BUDGETS_FINOPS.SP_GENERATE_LOAD();

-- ---- STEP 8: Grants to DSOA viewer role ------------------------------------
GRANT USAGE  ON DATABASE DSOA_TEST_DB                            TO ROLE DTAGENT_QA_VIEWER;
GRANT USAGE  ON SCHEMA   DSOA_TEST_DB.BUDGETS_FINOPS             TO ROLE DTAGENT_QA_VIEWER;
GRANT SELECT ON TABLE    DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS   TO ROLE DTAGENT_QA_VIEWER;

-- The budgets plugin calls SYSTEM$SHOW_BUDGETS_IN_ACCOUNT() via the owner role
-- (EXECUTE AS CALLER). Access to spending history uses SNOWFLAKE.BUDGET_VIEWER
-- app role granted in Step 5.
-- plugins.budgets.monitored_budgets must list the budget FQNs in config-test-qa.yml.

-- ---- STEP 9: Enable DSOA plugins in conf/config-test-qa.yml ----------------
-- Add the following to conf/config-test-qa.yml:
--
-- plugins:
--   disabled_by_default: true
--   deploy_disabled_plugins: false
--   budgets:
--     is_enabled: true
--     monitored_budgets:
--       - "SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET"
--   event_usage:
--     is_enabled: true
--   warehouse_usage:
--     is_enabled: true
--   resource_monitors:
--     is_enabled: true
--
-- Then rebuild and redeploy:
--   ./scripts/dev/build.sh
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm

-- ---- STEP 10: Trigger a manual DSOA run to get telemetry immediately -------
-- After deploying run:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('budgets','event_usage','warehouse_usage','resource_monitors'))"
--
-- Then spot-check:
--   fetch logs
--   | filter db.system == "snowflake"
--   | filter dsoa.run.plugin in ("budgets","event_usage","warehouse_usage","resource_monitors")
--   | limit 20

-- ---- STEP 11: Verify setup -------------------------------------------------
SHOW WAREHOUSES LIKE 'DSOA_TEST_FINOPS_WH';
SHOW RESOURCE MONITORS LIKE 'DSOA_TEST_RM';
SHOW TASKS   IN SCHEMA DSOA_TEST_DB.BUDGETS_FINOPS;
SELECT COUNT(*) AS event_rows FROM DSOA_TEST_DB.BUDGETS_FINOPS.DT_EVENTS;

-- ============================================================================
-- CLEANUP (run when done testing — suspend task BEFORE dropping database):
--
--   USE ROLE ACCOUNTADMIN;
--   DROP BUDGET  IF EXISTS DSOA_TEST_DB.BUDGETS_FINOPS.DSOA_TEST_BUDGET;
--   USE ROLE DTAGENT_QA_OWNER;
--   ALTER TASK DSOA_TEST_DB.BUDGETS_FINOPS.T_GENERATE_LOAD SUSPEND;
--   DROP DATABASE IF EXISTS DSOA_TEST_DB;
--   USE ROLE ACCOUNTADMIN;
--   DROP WAREHOUSE IF EXISTS DSOA_TEST_FINOPS_WH;
--   DROP RESOURCE MONITOR IF EXISTS DSOA_TEST_RM;
--
-- Also revert conf/config-test-qa.yml and redeploy:
--   ./scripts/dev/build.sh
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm
-- ============================================================================

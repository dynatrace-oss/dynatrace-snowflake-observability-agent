# Skill: Snowflake Synthetic Test Setup

Use this skill whenever you need to create, update, or verify synthetic test data
pipelines in Snowflake for validating DSOA telemetry and dashboards.

## Connection

Always use the Snowflake CLI with the dev test connection:

```bash
snow sql --connection snow_agent_test-qa -f <file>
```

For quick inline checks:

```bash
snow sql --connection snow_agent_test-qa -q "<SQL statement>"
```

## File Location

All synthetic setup SQL scripts live in `test/tools/`. Naming convention:

```
test/tools/setup_test_<plugin-name>.sql
```

Examples:

- `test/tools/setup_test_snowpipes.sql`
- `test/tools/setup_test_tasks.sql`
- `test/tools/setup_test_dynamic_tables.sql`

## Database Convention

Each plugin uses its **own dedicated test database** with a descriptive name:

```sql
DSOA_<PLUGIN>_TEST_DB   -- e.g., DSOA_PIPE_TEST_DB for the snowpipes plugin
```

Use a single schema inside that database to keep objects organised:

```sql
DSOA_<PLUGIN>_TEST_DB.<SCHEMA>   -- e.g., DSOA_PIPE_TEST_DB.INGEST
```

This mirrors the real `test/tools/setup_test_snowpipes.sql` pattern and keeps
ownership grants simple (one DB per plugin, owned end-to-end by `OWNER_ROLE`).

## Script Structure

Every `setup_test_<plugin>.sql` must follow this structure, which mirrors
`test/tools/setup_test_snowpipes.sql`:

```sql
-- ============================================================================
-- <Plugin> test setup for DSOA telemetry validation
-- Database: DSOA_<PLUGIN>_TEST_DB   Schema: DSOA_<PLUGIN>_TEST_DB.<SCHEMA>
-- Cost: near-zero  (describe approach)
--
-- Ownership model:
--   All objects are created directly by OWNER_ROLE so no post-hoc ownership
--   transfers are needed. ACCOUNTADMIN is used only for the two account-level
--   grants that cannot be issued by a lower-privileged role.
--
-- Before running:
--   1. Set OWNER_ROLE to the role that should own all objects.
--   2. Set TASK_WAREHOUSE to a warehouse that OWNER_ROLE can use.
-- ============================================================================

-- ---- CONFIGURATION ---------------------------------------------------------
SET owner_role     = 'OWNER_ROLE';      -- role that will own all objects
SET task_warehouse = 'TASK_WAREHOUSE';  -- warehouse used by tasks (if any)
-- ----------------------------------------------------------------------------

-- 1. Account-level grants that require ACCOUNTADMIN (only what is necessary).
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK  ON ACCOUNT                               TO ROLE IDENTIFIER($owner_role);
GRANT USAGE         ON WAREHOUSE IDENTIFIER($task_warehouse) TO ROLE IDENTIFIER($owner_role);

-- 2. Create the database as SYSADMIN, then grant ownership to OWNER_ROLE
--    before any objects exist (safe because no running pipes/tasks yet).
USE ROLE SYSADMIN;
CREATE DATABASE IF NOT EXISTS DSOA_<PLUGIN>_TEST_DB;
USE ROLE ACCOUNTADMIN;
GRANT OWNERSHIP ON DATABASE DSOA_<PLUGIN>_TEST_DB
    TO ROLE IDENTIFIER($owner_role) COPY CURRENT GRANTS;

-- 3. Switch to OWNER_ROLE for everything else. All objects are owned from birth.
USE ROLE IDENTIFIER($owner_role);
USE DATABASE DSOA_<PLUGIN>_TEST_DB;

CREATE SCHEMA IF NOT EXISTS DSOA_<PLUGIN>_TEST_DB.<SCHEMA>;

-- 4. Create test objects (tables, stages, pipes, tasks, etc.)
-- ...

-- 5. Load or generate sample data that exercises all dashboard use cases
-- ...

-- 6. Grant access to the DSOA viewer role
--    Adjust role name to match your deployment tag (e.g. DTAGENT_094_VIEWER)
GRANT USAGE ON DATABASE DSOA_<PLUGIN>_TEST_DB TO ROLE DTAGENT_094_VIEWER;
GRANT USAGE ON SCHEMA   DSOA_<PLUGIN>_TEST_DB.<SCHEMA> TO ROLE DTAGENT_094_VIEWER;
-- <object-level grants>

-- 7. Verify setup
-- <SHOW / SELECT verification queries>

-- ============================================================================
-- CLEANUP (run when done testing):
-- DROP DATABASE IF EXISTS DSOA_<PLUGIN>_TEST_DB;
-- ============================================================================
```

Omit the `EXECUTE TASK` / `TASK_WAREHOUSE` grants if the plugin does not use
Snowflake Tasks in its synthetic setup.

## Execution Workflow

### 1. Write the SQL file

Design the synthetic setup to cover **every use case** listed in the dashboard
plan or implementation spec. Each tile on the target dashboard should have
corresponding synthetic data that will produce a visible, non-trivial result.

### 2. Apply to Snowflake

```bash
snow sql --connection snow_agent_test-qa -f test/tools/setup_test_<plugin>.sql
```

### 3. Verify objects exist

```bash
snow sql --connection snow_agent_test-qa -q "SHOW <OBJECTS> IN SCHEMA DSOA_<PLUGIN>_TEST_DB.<SCHEMA>;"
```

### 4. Verify grants

```bash
snow sql --connection snow_agent_test-qa -q \
  "SHOW GRANTS TO ROLE DTAGENT_094_VIEWER;" | grep DSOA_
```

### 5. Wait for DSOA collection

- **Fast-mode plugins** (e.g. snowpipes, active_queries): data appears within ~5 min
- **Deep/hourly plugins** (e.g. copy_history, usage_history): data appears within ~1–2 h
  (ACCOUNT_USAGE propagation delay)

Check the DSOA task last run time if data is not appearing:

```bash
snow sql --connection snow_agent_test-qa -q \
  "SELECT * FROM DTAGENT_094_DB.STATUS.LAST_PROCESSED ORDER BY UPDATED_AT DESC LIMIT 20;"
```

## Rebuilding and Redeploying DSOA

If the synthetic setup requires changes to the DSOA plugin code itself
(SQL views, Python plugin, config), rebuild and redeploy before re-testing:

```bash
# 1. Rebuild the agent (lint + compile + SQL assembly)
./scripts/dev/build.sh

# 2. Redeploy to the dev-094 Snowflake instance
./scripts/deploy/deploy.sh test-qa --scope=plugins,config,agents --options=skip_confirm
```

Scope guidance:

- `plugins` — redeploy SQL views and procedures
- `config` — push updated configuration values
- `agents` — redeploy task schedules
- `setup,plugins,config,agents` — full redeploy without reinitialising roles/DB

## Idempotency

All setup scripts must use `CREATE OR REPLACE` or `CREATE … IF NOT EXISTS`
so they can be re-run safely without manual cleanup.

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

**All synthetic test objects must be created in the same shared test database:**
```sql
DSOA_TEST_DB
```

Use a dedicated schema per plugin to keep objects isolated:
```sql
DSOA_TEST_DB.<PLUGIN_NAME>   -- e.g., DSOA_TEST_DB.SNOWPIPES
```

This avoids proliferating test databases and keeps grants centralised.

## Script Structure

Every `setup_test_<plugin>.sql` must follow this structure:
```sql
-- ============================================================================
-- <Plugin> test setup for DSOA telemetry validation
-- Database: DSOA_TEST_DB   Schema: DSOA_TEST_DB.<PLUGIN>
-- Cost: near-zero  (describe approach)
-- ============================================================================

USE ROLE SYSADMIN;

-- 1. Ensure shared test database and plugin schema exist
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.<PLUGIN>;

-- 2. Create test objects (tables, stages, pipes, tasks, etc.)
-- ...

-- 3. Load or generate sample data that exercises all dashboard use cases
-- ...

-- 4. Grant access to the DSOA viewer role
--    Adjust role name if your deployment uses a tag (e.g. DTAGENT_094_VIEWER)
GRANT USAGE ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_094_VIEWER;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.<PLUGIN> TO ROLE DTAGENT_094_VIEWER;
-- <object-level grants>

-- 5. Verify setup
-- <SHOW / SELECT verification queries>

-- ============================================================================
-- CLEANUP (run when done testing):
-- DROP SCHEMA IF EXISTS DSOA_TEST_DB.<PLUGIN>;
-- ============================================================================
```

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
snow sql --connection snow_agent_test-qa -q "SHOW <OBJECTS> IN SCHEMA DSOA_TEST_DB.<PLUGIN>;"
```

### 4. Verify grants
```bash
snow sql --connection snow_agent_test-qa -q \
  "SHOW GRANTS TO ROLE DTAGENT_094_VIEWER;" | grep DSOA_TEST_DB
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

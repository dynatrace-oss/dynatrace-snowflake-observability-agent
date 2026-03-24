---
name: snowflake-synthetic
description: Create and update Snowflake synthetic test setups for DSOA telemetry validation
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

# Skill: Snowflake Synthetic Test Setup

Use this skill whenever you need to create, update, or verify synthetic test data
pipelines in Snowflake for validating DSOA telemetry and dashboards.

## Prerequisites

This skill assumes the following are already in place:

1. **Snowflake CLI connection** `snow_agent_test-qa` is configured in
   Snowflake CLI configuration. The connection
   must point at the shared QA Snowflake account used for dashboard and workflow
   development.

2. **Agent configuration** `conf/config-test-qa.yml` exists with **all plugins
   disabled and not deployable by default**:

    ```yaml
    plugins:
      disabled_by_default: true
      deploy_disabled_plugins: false
    ```

   This ensures the QA agent only collects telemetry for plugins you explicitly
   enable — keeping costs low and data clean.

If either prerequisite is missing, set them up before proceeding (see
[CONTRIBUTING.md](../../docs/CONTRIBUTING.md#ai-assisted-dashboard--workflow-development)).

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

```text
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

## Enabling Plugins for a Dashboard or Workflow

Because `conf/config-test-qa.yml` disables all plugins by default, you **must**
explicitly enable every plugin whose telemetry your dashboard or workflow
requires. Add the plugin entries directly to `conf/config-test-qa.yml` under
`plugins:`.

### Rules

1. **Enable only what you need.** If a dashboard uses three plugins, enable
   exactly those three — nothing more.
2. **Scope collection with `include`/`exclude`.** Restrict each plugin to only
   the synthetic test objects so the agent doesn't collect unrelated data.
   Some plugins use the `DB.SCHEMA.OBJECT` format with `%` wildcards, other might not allow for scoping at all.
   Always check the plugin's config documentation to determine the correct format and available options —
   consult `src/dtagent/plugins/$PLUGIN.conf/$PLUGIN-config.yml` and `src/dtagent/plugins/$PLUGIN.conf/config.md` for details.
3. **After editing the config, redeploy** so the changes reach Snowflake
   (see [Rebuilding and Redeploying DSOA](#rebuilding-and-redeploying-dsoa)).

### Example

A dashboard that depends on the `snowpipes`, `tasks`, and `query_history`
plugins:

```yaml
plugins:
  disabled_by_default: true
  deploy_disabled_plugins: false
  snowpipes:
    is_enabled: true
    include:
      - "DSOA_TEST_DB.SNOWPIPES.%"
  tasks:
    is_enabled: true
  query_history:
    is_enabled: true
```

> **Tip:** The `include` patterns should match the schema/objects created by
> your `setup_test_<plugin>.sql` script inside `DSOA_TEST_DB`.

After updating the config, rebuild and redeploy plugins and config.

```bash
./scripts/dev/build.sh
./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm
```

> **Note:** You don't need to redeploy `agents` scope unless you are modifying the python agent code.

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
- `agents` — redeploy agent Snowpark Python code (if you made changes to the plugin code)
- `setup,plugins,config,agents` — full redeploy without reinitialising roles/DB

## Idempotency

All setup scripts must use `CREATE OR REPLACE` or `CREATE … IF NOT EXISTS`
so they can be re-run safely without manual cleanup.

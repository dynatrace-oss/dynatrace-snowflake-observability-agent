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

## Environment Reference (test-qa)

Validated on: **test-qa** (`DYNATRACEDIGITALBUSINESSDW`, `AWS_US_EAST_1`)

| Item                 | Value                        |
|----------------------|------------------------------|
| CLI connection       | `snow_agent_test-qa`         |
| Snowflake account    | `DYNATRACEDIGITALBUSINESSDW` |
| Region               | `AWS_US_EAST_1`              |
| DSOA database        | `DTAGENT_QA_DB`              |
| Owner role           | `DTAGENT_QA_OWNER`           |
| Viewer role          | `DTAGENT_QA_VIEWER`          |
| Default warehouse    | `DTAGENT_WH`                 |
| Synthetic warehouse  | `DSOA_TEST_WH` (XSMALL, created by setup scripts) |
| Synthetic database   | `DSOA_TEST_DB` (created by setup scripts)         |

> **Note:** The connection's default role (`SEBASTIAN_KRUK_ROLE`) cannot see
> DTAGENT databases. Always use `USE ROLE DTAGENT_QA_OWNER` explicitly when
> checking for agent objects.

## Design Principle: DSOA-Independence

**Synthetic setup scripts must be fully independent of DSOA.** They create test
data that DSOA *will eventually observe*, but they must not assume DSOA is
already deployed — the whole point is that the environment can be set up *before*
DSOA is deployed for the first time.

Concretely:

- **Never reference `DTAGENT_*` roles, databases, or objects** in a setup script.
  Those objects may not exist yet.
- **Do not grant to `DTAGENT_QA_VIEWER`** in the setup script. DSOA's own deploy
  (`--scope=admin,config`) handles grants to its viewer role as part of installation.
- Run everything as `SYSADMIN` (for object creation) and `ACCOUNTADMIN` (for
  account-level grants only, e.g. `EXECUTE TASK`). All created objects are owned
  by `SYSADMIN` or transferred to it — no DSOA-specific roles needed.

The DSOA viewer role gains access to `DSOA_TEST_DB` automatically when DSOA is
deployed (its admin SQL grants `USAGE` on all databases the agent needs to read).
No manual grants to `DTAGENT_*` roles are needed in the setup script.

If plugin that was deployed requires access to telemetry to be granted to the agent there is _GRANTS_TASK.sql file in the $plugin.sql folder. You will need to trigger that task to ensure the viewer role has access to the synthetic test data.

## Prerequisites

This skill assumes the following are already in place:

1. **DSOA is installed** on the target environment — `DTAGENT_QA_DB` exists
   and `DTAGENT_QA_OWNER` / `DTAGENT_QA_VIEWER` roles are present. Verify with:

   ```bash
   snow sql -c snow_agent_test-qa -q "USE ROLE DTAGENT_QA_OWNER; SHOW DATABASES LIKE 'DTAGENT%'"
   ```

   If the result is empty, DSOA has never been deployed there. A **human** must
   run `--scope=all` first (AI agents are never permitted to run privileged
   scopes — see `dynatrace-dashboard` skill).

2. **Snowflake CLI connection** `snow_agent_test-qa` is configured in
   Snowflake CLI configuration. The connection must point at the shared QA
   Snowflake account used for dashboard and workflow development.

3. **Agent configuration** `conf/config-test-qa.yml` exists with **all plugins
   disabled and not deployable by default**:

    ```yaml
    plugins:
      disabled_by_default: true
      deploy_disabled_plugins: false
    ```

   This ensures the QA agent only collects telemetry for plugins you explicitly
   enable — keeping costs low and data clean.

If any prerequisite is missing, set them up before proceeding (see
[CONTRIBUTING.md](../../../docs/CONTRIBUTING.md#ai-assisted-dashboard--workflow-development)).

## Connection

Always use the Snowflake CLI with the dev test connection:

```bash
snow sql --connection snow_agent_test-qa -f <file>
```

For quick inline checks:

```bash
snow sql --connection snow_agent_test-qa -q "<SQL statement>"
```

## Known Pitfalls (Lessons Learned)

These issues were discovered during real setup sessions — follow the patterns
below to avoid them:

### 1. `GRANT OWNERSHIP ... COPY CURRENT GRANTS` may fail

Some connection roles lack the `WITH COPY CURRENT GRANTS` privilege for
ownership transfers. Use `REVOKE CURRENT GRANTS` instead:

```sql
-- ✗ May fail with "Insufficient privileges to operate on grant ownership"
GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER COPY CURRENT GRANTS;

-- ✓ Use this instead
GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER REVOKE CURRENT GRANTS;
```

### 2. `UNIFORM()` cannot be used inline in VALUES inside `$$` procedure bodies

Snowflake does not allow `UNIFORM()` (or other non-deterministic functions)
directly in a VALUES clause when they are mixed with string concatenation
inside a `$$`-delimited stored procedure body. Capture them into `DECLARE`
variables first:

```sql
-- ✗ Fails: "Invalid expression [...UNIFORM()...] in VALUES clause"
INSERT INTO t (a, b) VALUES ('prefix ' || UNIFORM(1, 9, RANDOM()), 'x');

-- ✓ Declare the variable, then reference it with :var
DECLARE
    rnd NUMBER DEFAULT UNIFORM(1, 9, RANDOM());
BEGIN
    INSERT INTO t (a, b) VALUES ('prefix ' || :rnd, 'x');
END;
```

### 3. Tasks require `EXECUTE TASK` account-level privilege

For the `tasks` plugin, the owner role needs `EXECUTE TASK ON ACCOUNT` before
it can `ALTER TASK ... RESUME` tasks it owns. This must be granted by
`ACCOUNTADMIN`:

```sql
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE DTAGENT_QA_OWNER;
```

Without this, `ALTER TASK ... RESUME` will fail with an access control error.

### 4. Viewer role name varies by environment tag

The viewer role follows the pattern `DTAGENT_<TAG>_VIEWER`. For the QA
environment the tag is `QA`, so the role is `DTAGENT_QA_VIEWER`. Do **not**
hardcode `DTAGENT_094_VIEWER` — that belongs to a different environment.

### 5. `DT_DOWNSTREAM` (or any dynamic table using `CURRENT_TIMESTAMP()`) will use FULL refresh

Snowflake automatically selects FULL refresh mode for dynamic tables whose
query contains non-deterministic functions (`CURRENT_TIMESTAMP()`, `RANDOM()`,
etc.) because change tracking is not supported on such queries. This is
expected behaviour — the warning in the `CREATE` response can be ignored for
synthetic test purposes.

### 6. Setup scripts must not reference DTAGENT_* roles

Synthetic setup scripts run independently of DSOA — they may be applied to an
environment where DSOA has never been deployed. **Never reference `DTAGENT_*`
roles, databases, or schemas** in a setup script.

- Run all DDL as `SYSADMIN`. Objects are owned by `SYSADMIN`.
- Do **not** grant to `DTAGENT_QA_VIEWER` in the setup script. DSOA's own
  `--scope=admin` deploy handles those grants as part of installation.
- If a prior partial run transferred ownership away from `SYSADMIN` (e.g.
  via `GRANT OWNERSHIP … TO ROLE DTAGENT_QA_OWNER`), recover with:

  ```sql
  USE ROLE ACCOUNTADMIN;
  GRANT OWNERSHIP ON WAREHOUSE DSOA_TEST_WH TO ROLE SYSADMIN REVOKE CURRENT GRANTS;
  GRANT OWNERSHIP ON DATABASE  DSOA_TEST_DB  TO ROLE SYSADMIN REVOKE CURRENT GRANTS;
  GRANT OWNERSHIP ON SCHEMA    DSOA_TEST_DB.<PLUGIN> TO ROLE SYSADMIN REVOKE CURRENT GRANTS;
  ```

  Then drop and recreate the schema so `SYSADMIN`-owned objects can be
  replaced cleanly by `CREATE OR REPLACE`.

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
--
-- NOTE: This script is DSOA-independent. It creates test data that DSOA
-- will observe once deployed. No DTAGENT_* roles or objects are referenced.
-- DSOA's own deploy grants its viewer role access to DSOA_TEST_DB.
-- ============================================================================

USE ROLE SYSADMIN;

-- 1. Ensure shared test warehouse exists
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

-- 2. Ensure shared test database and plugin schema exist
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.<PLUGIN>;

USE WAREHOUSE DSOA_TEST_WH;
USE DATABASE DSOA_TEST_DB;
USE SCHEMA DSOA_TEST_DB.<PLUGIN>;

-- 3. Create test objects (tables, stages, pipes, tasks, etc.)
-- ...

-- 4. Load or generate sample data that exercises all dashboard use cases
-- ...

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

After updating the config, rebuild and redeploy plugins, agents, and config.

```bash
./scripts/dev/build.sh
./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm
```

> **Important:** Always include `agents` scope whenever you enable or disable plugins
> in `deploy_disabled_plugins: false` mode. Parts of the agent Python code are
> conditionally compiled based on which plugins are active, so the agent stored
> procedure must be redeployed to match. Omitting `agents` leaves a stale procedure
> in Snowflake that may reference objects that no longer exist (or vice versa).

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
  "SHOW GRANTS TO ROLE DTAGENT_QA_VIEWER;" | grep DSOA_TEST_DB
```

### 5. Wait for DSOA collection

- **Fast-mode plugins** (e.g. snowpipes, active_queries): data appears within ~5 min
- **Deep/hourly plugins** (e.g. copy_history, usage_history): data appears within ~1–2 h
  (ACCOUNT_USAGE propagation delay)

Check the DSOA task last run time if data is not appearing:

```bash
snow sql --connection snow_agent_test-qa -q \
  "USE ROLE DTAGENT_QA_OWNER; SELECT * FROM DTAGENT_QA_DB.STATUS.LAST_PROCESSED ORDER BY UPDATED_AT DESC LIMIT 20;"
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

## Post-Approval Cleanup

Once the human has **fully approved** the dashboard or workflow (Phase 4 complete),
the QA environment must be restored to a clean baseline — no plugins enabled, no
synthetic-scoped config leftover — so it is ready for the next development cycle.

### Steps

1. **Tear down synthetic Snowflake objects** — suspend tasks before dropping the
   database. Failing to suspend tasks first will cause `DROP DATABASE` to fail.
   Also note that dropping the warehouse requires `ACCOUNTADMIN`, not `SYSADMIN`:

   ```bash
   snow sql -c snow_agent_test-qa -q "
   USE ROLE DTAGENT_QA_OWNER;
   ALTER TASK DSOA_TEST_DB.<SCHEMA>.T_<TASK_1> SUSPEND;
   ALTER TASK DSOA_TEST_DB.<SCHEMA>.T_<TASK_2> SUSPEND;
   DROP DATABASE IF EXISTS DSOA_TEST_DB;
   USE ROLE ACCOUNTADMIN;
   DROP WAREHOUSE IF EXISTS DSOA_TEST_WH;"
   ```

   > **Known issue:** Disabling plugins in `conf/config-test-qa.yml` and
   > redeploying with `--scope=plugins,agents,config` does **not** automatically
   > suspend Snowflake tasks created by those plugins. The DSOA agent tasks
   > (`_MEASUREMENT_TASK`, `_FINALIZER_TASK`) for those plugins remain in
   > `started` state in Snowflake even after the config is updated. You must
   > manually suspend them (or drop the database) after the redeploy. This is a
   > known DSOA limitation — see `TELEMETRY-ISSUES.md` / findings doc.

2. **Edit `conf/config-test-qa.yml`** — remove all plugin `is_enabled: true` entries
   and any `include`/`exclude` blocks added for testing. The plugins block must return
   to the clean base:

   ```yaml
   plugins:
     disabled_by_default: true
     deploy_disabled_plugins: false
   ```

   Do **not** leave any `plugin_name: { is_enabled: true }` stanzas — they will cause
   those plugins to be deployed and run on every agent tick, wasting credits.

3. **Rebuild and redeploy** with `plugins`, `agents`, and `config` scopes:

   ```bash
   ./scripts/dev/build.sh
   ./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm
   ```

   `agents` is required because disabling plugins changes the compiled agent code.
   `plugins` removes the SQL views/procedures for the now-disabled plugins.
   `config` pushes the cleaned-up configuration rows to Snowflake.

4. **Verify** the agent runs clean with no plugins active:

   ```bash
   snow sql -c snow_agent_test-qa -q \
     "USE ROLE DTAGENT_QA_OWNER; USE DATABASE DTAGENT_QA_DB; USE WAREHOUSE DTAGENT_WH; CALL DTAGENT_QA_DB.APP.DTAGENT([]);"
   ```

   The call should succeed with zero entries processed.

> **Never** leave plugins enabled in the QA config after the dashboard/workflow is
> approved. Enabled plugins collect real data continuously, increase DSOA run time,
> and make it harder to validate future dashboards against a clean dataset.

## Idempotency

All setup scripts must use `CREATE OR REPLACE` or `CREATE … IF NOT EXISTS`
so they can be re-run safely without manual cleanup.

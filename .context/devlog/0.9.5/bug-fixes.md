# Bug Fixes — 0.9.5

## BCR Bundle 2026\_02: Adapt to New `LOG_EVENT_LEVEL` Parameter

- **Background**: Snowflake BCR Bundle 2026\_02 (enabled week of April 6 2026) introduces a new `LOG_EVENT_LEVEL`
  parameter that decouples event table ingestion control from the existing `LOG_LEVEL` parameter. Previously,
  `LOG_LEVEL` controlled both diagnostic output and what severity of events was ingested into the event table.
  After the BCR, `LOG_EVENT_LEVEL` must also be set to ensure events reach the event table. Without this change,
  DSOA deployments on BCR-active accounts would silently lose event log telemetry for everything below the
  account-default `LOG_EVENT_LEVEL` value.
- **Detection pattern**: Both `SETUP_EVENT_TABLE()` and `002_init_db.sql` probe for the parameter using
  `SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL'` before attempting to set it. A `count(*) > 0` on `result_scan()`
  determines whether the parameter exists. The probe itself is wrapped in `EXCEPTION WHEN OTHER` so that any
  unexpected error on pre-BCR accounts is also handled gracefully.
- **`009_event_log_init.sql`** (`SETUP_EVENT_TABLE()`): When DSOA creates its own event table (the DSOA-owned
  branch), after setting `LOG_LEVEL = WARN` the procedure now also: (1) sets `ALTER ACCOUNT SET LOG_EVENT_LEVEL = INFO`
  and (2) grants `MODIFY LOG EVENT LEVEL ON ACCOUNT TO ROLE DTAGENT_VIEWER`. Both operations are guarded by the
  BCR detection flag `b_has_log_event_level`. The custom-event-table branch is intentionally left unchanged —
  when DSOA uses a pre-existing event table, the account operator controls ingestion levels.
- **`002_init_db.sql`**: A top-level `BEGIN … END` scripting block probes `SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL'
  IN DATABASE DTAGENT_DB` and, if the parameter exists, sets `ALTER DATABASE DTAGENT_DB SET LOG_EVENT_LEVEL = INFO`.
  This mirrors the existing `ALTER DATABASE DTAGENT_DB SET LOG_LEVEL = INFO` and ensures that procedures inside
  `DTAGENT_DB` emit events at INFO+ into the event table.
- **Why `INFO`, not `DEBUG`**: `LOG_LEVEL = INFO` (set in `002_init_db.sql`) controls what DSOA procedures emit.
  `LOG_EVENT_LEVEL = INFO` ensures those INFO+ emissions land in the event table. Setting `DEBUG` would flood the
  event table with internal Snowflake framework noise. The `V_EVENT_LOG` view already applies an additional filter
  (`severity_text not in ('DEBUG', 'INFO')` for DTAGENT-family DBs) to suppress DSOA self-noise from the telemetry
  pipeline, so there is no telemetry loss with `INFO`.
- **`bom.yml`**: Added `MODIFY LOG EVENT LEVEL` privilege reference with a comment noting it is only granted on
  BCR-active accounts.
- **No upgrade script needed**: `SETUP_EVENT_TABLE()` signature is unchanged; no Snowflake overload conflict.
- **Files changed**: `src/dtagent/plugins/event_log.sql/init/009_event_log_init.sql`,
  `src/dtagent.sql/init/002_init_db.sql`, `src/dtagent/plugins/event_log.config/bom.yml`

## Deploy Pipeline: Cleanup Option for Disabled and Removed Plugins (`--options=cleanup_disabled`)

- **Background**: `inject_suspend_for_excluded_plugins()` already suspends tasks for disabled plugins. This extends the deploy pipeline with a full object cleanup option for operators who want to actively drop stale views, procedures, and tasks — not just suspend them.
- **New option**: `--options=cleanup_disabled` passed to `deploy.sh` is forwarded to `prepare_deploy_script.sh` (via a new 6th positional argument `OPTIONS_STR`). `prepare_deploy_script.sh` exposes a `has_option()` helper (mirrors the one in `deploy.sh`) to parse the options string.
- **`inject_cleanup_for_excluded_plugins()`** (new function in `prepare_deploy_script.sh`):
  - **Part 1 — disabled plugins**: For each plugin in `EXCLUDED_PLUGINS`, parses `build/30_plugins/<plugin>.sql` and emits `DROP TASK/PROCEDURE/VIEW IF EXISTS` for all objects defined there. Tasks are suspended before being dropped.
  - **Part 2 — removed plugins**: Reads `conf/removed_plugins.yml`. For each entry, emits `ALTER TASK ... SUSPEND` + `DROP TASK IF EXISTS` for every listed task name. This covers plugins fully deleted from the codebase that no longer appear in `EXCLUDED_PLUGINS`.
  - **Part 3 — orphan detection**: Injects a Snowflake `EXECUTE IMMEDIATE` block that queries `INFORMATION_SCHEMA.TASKS WHERE task_name ILIKE 'TASK_DTAGENT_%'`, filters out known active plugin tasks (enumerated from all current build artifacts), and suspends + drops any unrecognised tasks. Runs only when `cleanup_disabled` is set — avoids adding Snowflake round-trips to normal deploys where config scope speed matters.
- **`conf/removed_plugins.yml`** (new file): Tracks plugins permanently removed from the codebase. Committed in git (not gitignored — it's universal, not env-specific). Format: `removed_plugins: [{name, removed_in_version, tasks: [...]}]`. Initially empty. Agents and the plugin-development skill are updated to reference this file as a mandatory step during plugin removal.
- **Procedure extraction**: Uses `grep -oi 'PROCEDURE[[:space:]]\+...' | sed` rather than `awk` capture groups — macOS `awk` does not support `match()` with capture arrays.
- **Files changed**: `scripts/deploy/deploy.sh`, `scripts/deploy/prepare_deploy_script.sh`, `conf/removed_plugins.yml` (new), `.github/copilot-instructions.md`, `.opencode/skills/plugin-development/SKILL.md`

## Deploy Pipeline: Expanded Tests for Task Suspension and Cleanup

- Added 3 new test cases to `test/bash/test_suspend_disabled_plugins.bats`: `disabled_by_default` mode, `--scope=config` only, and multiple plugins disabled simultaneously.
- Added new `test/bash/test_cleanup_disabled_plugins.bats` (16 test cases) covering: no-op without flag, single/multi-task drop, view/procedure drop, `removed_plugins.yml` parsing, orphan detection block, TAG support, teardown exclusion, combined options.
- **Files changed**: `test/bash/test_suspend_disabled_plugins.bats`, `test/bash/test_cleanup_disabled_plugins.bats` (new)

## Config Upload: MERGE → DELETE + INSERT (Full Replace)

- **Root cause**: `040_update_config.sql` used `MERGE INTO CONFIG.CONFIGURATIONS` which is additive — rows present in a previous deploy but absent from the new YAML were never deleted. This meant that a plugin's `is_enabled: true` entry persisted even after the user removed it from their config YAML or switched to `disabled_by_default: true`. The stale entry overrode the new global setting, leaving the plugin enabled.
- **Fix**: Replaced the `MERGE` with a `BEGIN … DELETE FROM … INSERT INTO … END` block. The full YAML is always flattened and uploaded by `prepare_config.sh` (default + env merge), so a full table replace is safe. The `BEGIN/END` wrapper ensures atomicity — no window where the config table is empty.
- **Files changed**: `src/dtagent.sql/config/040_update_config.sql`
- **Backward compatibility**: First deploy with new code performs a full replace. If the user's YAML is complete (guaranteed by `prepare_config.sh`), no data loss. Manual edits to `CONFIG.CONFIGURATIONS` outside the deploy pipeline are not supported and will be lost on next deploy.

## Deploy Pipeline: Automatic Task Suspension for Disabled Plugins

- **Root cause**: When a plugin is disabled, `prepare_deploy_script.sh` strips its SQL via `filter_plugin_code()`. This means the `CREATE OR REPLACE TASK` statement (which would reset the task to Snowflake's default `suspended` state) is never executed. The existing task from a prior deploy remains in `started` state, consuming warehouse credits and potentially logging errors if underlying views were dropped.
- **Fix**: Added `inject_suspend_for_excluded_plugins()` to `prepare_deploy_script.sh`. After `filter_plugin_code()` runs, this function iterates `EXCLUDED_PLUGINS`, finds each plugin's `*_task.sql` files under `src/dtagent/plugins/<name>.sql/` (recursively, to cover `admin/` subdirectories), extracts the fully-qualified task name from the `CREATE OR REPLACE TASK` statement, and appends `ALTER TASK IF EXISTS <name> SUSPEND;` to the deploy script. The function is called for all scopes except `apikey` and `teardown`.
- **Design decisions**:
  - Task names are extracted from source SQL files rather than hardcoded, so multi-task plugins (e.g. `snowpipes` with `TASK_DTAGENT_SNOWPIPES` + `TASK_DTAGENT_SNOWPIPES_HISTORY`) and admin tasks (e.g. `event_log` with `TASK_DTAGENT_EVENT_LOG_CLEANUP`) are handled automatically.
  - `ALTER TASK IF EXISTS` is used for fresh-deploy safety (task doesn't exist yet → no-op).
  - The injected SQL uses `use role DTAGENT_OWNER` context, consistent with the rest of the deploy script. Custom name / TAG substitution (applied later in the script via `sed`) correctly replaces `DTAGENT_OWNER`, `DTAGENT_DB`, and `DTAGENT_WH` in the injected block.
  - Suspension runs regardless of deploy scope — even `--scope=plugins,agents` (no config scope) will suspend disabled plugin tasks.
- **Files changed**: `scripts/deploy/prepare_deploy_script.sh`

## Documentation: UPDATE_ALL_PLUGINS_SCHEDULE Scope Clarification

- Added a comment to `037_update_all_plugins_schedule.sql` explaining that the procedure only iterates plugins with a schedule entry in config, and that plugins absent from config are handled by `inject_suspend_for_excluded_plugins()` at deploy time.
- **Files changed**: `src/dtagent.sql/setup/037_update_all_plugins_schedule.sql`

## Tests Added

- `test/bash/test_config_full_replace.bats` — 5 tests verifying DELETE+INSERT pattern in `040_update_config.sql`.
- `test/bash/test_suspend_disabled_plugins.bats` — 8 tests covering: no exclusions → no suspend SQL; single-task plugin; multi-task plugin (snowpipes); admin-task plugin (event_log); role context; scope independence (`plugins,agents`); deploy log output; teardown scope exclusion.

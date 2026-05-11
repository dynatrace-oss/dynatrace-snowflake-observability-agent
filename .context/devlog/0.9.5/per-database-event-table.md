# [0.9.5] — BDX-716: Per-Database Event Table Support

## Problem

Snowflake's `ALTER DATABASE X SET EVENT_TABLE = ...` feature routes a database's telemetry to a DB-scoped event table, bypassing the account-level `EVENT_TABLE`. DSOA read only the account-level parameter, leaving per-DB override tables invisible. Gap grows as customers adopt DB-scoped tables for tenant isolation and regulated workloads.

## Approach

Opt-in config flag `plugins.event_log.discover_db_event_tables: false` (default off). When enabled, `SETUP_EVENT_TABLE()` (called at install and on agent restart via `UPDATE_EVENT_LOG_CONF`) does the following:

1. **DB enumeration**: queries `INFORMATION_SCHEMA.DATABASES` filtered by the existing `plugins.event_log.databases` allow-list (or all visible DBs if list is empty).
2. **Override detection**: for each DB, executes `SHOW PARAMETERS LIKE 'EVENT_TABLE' IN DATABASE "<db>"` and checks for a row where `"level" = 'DATABASE'`. Uses `COALESCE(MAX(...), '')` pattern to avoid `NO_DATA_FOUND` errors. Per-DB errors caught and logged as warnings — other DBs continue.
3. **UNION ALL view**: builds `STATUS.EVENT_LOG` dynamically via `EXECUTE IMMEDIATE`:
   - Account-table branch: all rows with `RESOURCE_ATTRIBUTES['snow.database.name']` NOT IN override-DB list, tagged `_dsoa_source_table = <account_table_fqn>` via `OBJECT_INSERT`.
   - One branch per override DB: rows from that DB's event table, tagged with its FQN.
   - If no overrides found: simple `SELECT * FROM <account_table>` (no UNION ALL overhead).
4. **Permission handling**: `GRANT SELECT` attempted on each override table; failures silently warned, not rethrown (matches existing pattern for `SNOWFLAKE.TELEMETRY.EVENTS`).
5. **Rebuild on config change**: `UPDATE_EVENT_LOG_CONF()` now calls `SETUP_EVENT_TABLE()` in a try/catch, so toggling the flag or updating `databases` automatically rebuilds the view on next agent restart.

## Source attribution

`_dsoa_source_table` is injected into `RESOURCE_ATTRIBUTES` using `OBJECT_INSERT(RESOURCE_ATTRIBUTES, '_dsoa_source_table', '<fqn>'::VARIANT)`. `V_EVENT_LOG` already passes `_RESOURCE_ATTRIBUTES` through; `_process_log_line` unpacks it via `_unpack_json_dict`, so the attribute surfaces in Dynatrace logs without any Python changes.

## No-op invariant

When `discover_db_event_tables = false` (default), the ELSE branch behaves identically to the pre-BDX-716 code. Zero behavioral change for existing deployments on upgrade.

## Files changed

- `src/dtagent/plugins/event_log.config/event_log-config.yml` — new key
- `src/dtagent/plugins/event_log.sql/init/009_event_log_init.sql` — `SETUP_EVENT_TABLE()` rewrite
- `src/dtagent/plugins/event_log.sql/901_update_event_log_config.sql` — call `SETUP_EVENT_TABLE()`
- `test/test_data/event_log_multi_source.ndjson` — new 4-row fixture
- `test/plugins/test_event_log.py` — `test_event_log_multi_source`
- `src/dtagent/plugins/event_log.config/config.md` + `readme.md` — docs

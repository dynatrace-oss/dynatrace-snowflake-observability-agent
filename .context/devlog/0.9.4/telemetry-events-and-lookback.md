# SNOWFLAKE.TELEMETRY.EVENTS Support and Configurable Lookback Time

## SNOWFLAKE.TELEMETRY.EVENTS Support

- **Issue**: When a customer account had `EVENT_TABLE = snowflake.telemetry.events` (the Snowflake-managed shared event table), `SETUP_EVENT_TABLE()` listed it in `a_no_custom_event_t` — the "not a real custom table" array — and took the `IF` branch, creating DSOA's own `DTAGENT_DB.STATUS.EVENT_LOG` table and **ignoring** the Snowflake-managed table entirely.
- **Root cause**: `'snowflake.telemetry.events'` was excluded from the view-creation path because the original `ELSE` branch attempted `GRANT SELECT ON TABLE snowflake.telemetry.events TO ROLE DTAGENT_VIEWER`, which Snowflake rejects — privileges cannot be granted on Snowflake-managed objects.
- **Fix**: Two-part change in `src/dtagent/plugins/event_log.sql/init/009_event_log_init.sql`:
  1. Removed `'snowflake.telemetry.events'` from `a_no_custom_event_t` so it falls through to the `ELSE` branch
  2. Wrapped the `GRANT SELECT` in a `BEGIN/EXCEPTION WHEN OTHER THEN SYSTEM$LOG_WARN()` block — attempts the grant and logs warnings, ignoring failures for any read-only or Snowflake-managed table; more robust than a string comparison
- **Behaviour after fix**: When `EVENT_TABLE = snowflake.telemetry.events`, DSOA creates `DTAGENT_DB.STATUS.EVENT_LOG` as a **view** over it, exactly as for any other pre-existing customer event table. All three `event_log` SQL views continue to query `DTAGENT_DB.STATUS.EVENT_LOG` unchanged — no Python changes needed.

## Configurable Lookback Time

- **Motivation**: Lookback windows were hardcoded across SQL views in every plugin that uses `F_LAST_PROCESSED_TS`. This could not be tuned per deployment without modifying SQL files.
- **Approach**: Replace each literal with `CONFIG.F_GET_CONFIG_VALUE('plugins.<plugin>.lookback_hours', <default>)` and add `lookback_hours` to each plugin's config YAML — consistent with how `retention_hours` is already handled in `P_CLEANUP_EVENT_LOG`.
- **Pattern**: `timeadd(hour, -1*F_GET_CONFIG_VALUE('plugins.<plugin>.lookback_hours', <N>), current_timestamp)` — the `-1*` multiplier converts the positive config value to a negative offset.
- **Note**: The `F_LAST_PROCESSED_TS` guard in each view's `GREATEST(...)` clause ensures normal incremental runs are unaffected; `lookback_hours` only bounds the fallback window when no prior timestamp exists.
- **Files changed** (SQL views + config YAMLs):

| Plugin            | SQL view(s)                                                                                                                      | Default                                    |
|-------------------|----------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| `event_log`       | `051_v_event_log.sql`, `051_v_event_log_metrics_instrumented.sql`, `051_v_event_log_spans_instrumented.sql`                      | `24`h                                      |
| `login_history`   | `061_v_login_history.sql`, `061_v_sessions.sql`                                                                                  | `24`h                                      |
| `warehouse_usage` | `070_v_warehouse_event_history.sql`, `071_v_warehouse_load_history.sql`, `072_v_warehouse_metering_history.sql`                  | `24`h                                      |
| `tasks`           | `061_v_serverless_tasks.sql` → `lookback_hours` (`4`h); `063_v_task_versions.sql` → `lookback_hours_versions` (`720`h = 1 month) | separate keys, original defaults preserved |
| `event_usage`     | `051_v_event_usage.sql`                                                                                                          | `6`h                                       |
| `data_schemas`    | `051_v_data_schemas.sql`                                                                                                         | `4`h                                       |

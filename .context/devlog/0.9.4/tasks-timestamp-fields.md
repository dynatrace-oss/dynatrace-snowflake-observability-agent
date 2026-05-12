# Tasks Plugin — Timestamp Fields and Dynamic Tables Scheduling State

## Timestamp Fields Converted to Epoch Nanoseconds (TI-001)

- **Root cause**: `V_TASK_HISTORY` passed `th.SCHEDULED_TIME` and `th.COMPLETED_TIME` directly into the `ATTRIBUTES` OBJECT_CONSTRUCT without any conversion. Snowflake serialises `TIMESTAMP_LTZ` values as ISO 8601 datetime strings (e.g. `"2025-04-29 00:00:00.000 Z"`) inside a VARIANT/OBJECT. Every other timestamp attribute across all plugins uses `extract(epoch_nanosecond from ...)` — these two fields were the only exceptions. The `instruments-def.yml` `__example` values had been written to match the broken output rather than the intended contract.
- **Additional scope**: `V_TASK_VERSIONS` had the same bug for `LAST_COMMITTED_ON` and `LAST_SUSPENDED_ON` — passed raw into ATTRIBUTES despite the `instruments-def.yml` already documenting them with epoch-nanos examples (`"1633046400000000000"`).
- **Fix**:
  - `062_v_task_history.sql`: `th.SCHEDULED_TIME` → `CASE WHEN th.SCHEDULED_TIME IS NOT NULL THEN extract(epoch_nanosecond from th.SCHEDULED_TIME) ELSE -1 END`; same for `COMPLETED_TIME`. Sentinel `-1` is consistent with the `QUERY_START_TIME` NULL-guard already in this view.
  - `063_v_task_versions.sql`: `tv.LAST_COMMITTED_ON` / `tv.LAST_SUSPENDED_ON` → `extract(epoch_nanosecond from ...)`. No sentinel needed — these are nullable attributes, `extract()` of NULL produces NULL which is dropped from the OBJECT_CONSTRUCT.
  - `tasks.config/instruments-def.yml`: updated `__example` for `snowflake.task.run.scheduled_time` and `snowflake.task.run.completed_time` to epoch nanos strings.
- **Test fixtures updated**:
  - `test/test_data/tasks_history.ndjson`: converted `scheduled_time` values to epoch nanos integers; added `completed_time: -1` (fixtures represent SCHEDULED-state tasks with no completion yet).
  - `test/test_results/test_tasks/logs.json`: golden output updated to match.
- **Dashboard impact** (`tasks-pipelines.yml`, bumped to v26):
  - Tile 3 (Task Run Duration Trend): removed `toTimestamp()` workaround; now uses direct `toLong()` integer subtraction. Added `> 0` guards to exclude `-1` sentinel values from duration calculation.

## Dynamic Tables — Scheduling State Empty String (TI-004)

- **Root cause**: Extracting a path from a Snowflake VARIANT column via `:path` notation returns an empty string `""` (not `NULL`) when the key exists in the JSON object but its value is an empty string or absent. `SCHEDULING_STATE` is a VARIANT column; when a dynamic table has no active reason code or message, Snowflake populates those keys with empty strings. The extracted values flowed into the `ATTRIBUTES` object and then into Dynatrace logs as `""` — causing DQL `isNull()` checks to miss them and forcing callers to add `!= ""` workaround filters.
- **Fix**: `053_v_dynamic_tables_instrumented.sql` CTE `cte_dynamic_tables` — wrapped all three VARIANT path extractions with `NULLIF(...::VARCHAR, '')`:

  ```sql
  NULLIF(SCHEDULING_STATE:state::VARCHAR, '')          as SCHEDULING_STATE_STATE,
  NULLIF(SCHEDULING_STATE:reason_code::VARCHAR, '')    as SCHEDULING_STATE_REASON_CODE,
  NULLIF(SCHEDULING_STATE:reason_message::VARCHAR, '') as SCHEDULING_STATE_REASON_MESSAGE,
  ```

  The explicit `::VARCHAR` cast is required before `NULLIF` to ensure consistent comparison — without it the VARIANT type would be compared against a VARCHAR literal which behaves inconsistently across Snowflake versions.
- **Dashboard impact** (`tasks-pipelines.yml`):
  - Tile 10 (Scheduling State Heatmap): removed `| filter snowflake.table.dynamic.scheduling.state != ""` — now redundant since `NULL` is the canonical absence value.

**Files changed:**

- `src/dtagent/plugins/tasks.sql/062_v_task_history.sql`
- `src/dtagent/plugins/tasks.sql/063_v_task_versions.sql`
- `src/dtagent/plugins/tasks.config/instruments-def.yml`
- `src/dtagent/plugins/dynamic_tables.sql/053_v_dynamic_tables_instrumented.sql`
- `test/test_data/tasks_history.ndjson`
- `test/test_results/test_tasks/logs.json`
- `docs/dashboards/tasks-pipelines/tasks-pipelines.yml`

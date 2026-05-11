# Fix task_history attempt stored as string

## Root Cause

`ATTEMPT_NUMBER` in Snowflake's `INFORMATION_SCHEMA.TASK_HISTORY` is `NUMBER(38,0)`. When passed directly into `OBJECT_CONSTRUCT` without a type cast, Snowflake serialises it as a JSON string in some contexts. Python `json.loads` then deserialises it as `str`, which `_cleanup_data` preserves, and OTEL sends as `stringValue` in the log attribute payload — rather than `intValue`.

## Fix

Added `::INTEGER` cast at `src/dtagent/plugins/tasks.sql/062_v_task_history.sql:57`:

```sql
'snowflake.task.run.attempt',   th.ATTEMPT_NUMBER::INTEGER,
```

`::INTEGER` forces an integer-valued numeric representation in the `OBJECT_CONSTRUCT` JSON output (in Snowflake, `INTEGER` is effectively a synonym for `NUMBER(38,0)`, not a 32-bit type). Python `json.loads` parses it as `int`; `_cleanup_data` preserves it; OTEL sends it as `intValue`. Downstream Dynatrace Grail stores it as `LONG`.

## Downstream updates

- `src/dtagent/plugins/tasks.config/instruments-def.yml`: `__example` changed from `"1"` (string) to `1` (integer) for semantic accuracy.
- `docs/dashboards/tasks-pipelines/tasks-pipelines.yml`: "Task Retry Patterns" tile DQL updated from `toLong(snowflake.task.run.attempt) > 1` to `snowflake.task.run.attempt > 1`.

## Test impact

None. `test/test_data/tasks_history.ndjson` already stored attempt as bare integer `1`, and the existing mock-test baselines already expected an integer here, so no fixture or `test/test_results/*` updates were needed.

## Deployment

`--scope=plugins,config` — SQL view change requires plugin redeployment; no Python changes.

# [0.9.5] — Fix serverless_tasks empty namespace for account-level records

## Root cause

`SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY` is an account-level billing view. DSOA's own
scheduler tasks (`_MEASUREMENT_TASK`, `_FINALIZER_TASK`) run at account scope, so `database_name`
and `schema_name` are empty strings (not NULL) in the source view. `V_SERVERLESS_TASKS` passed
these directly into `OBJECT_CONSTRUCT`, causing `db.namespace = ""` and `snowflake.schema.name = ""`
in Dynatrace. Dashboard `$Database`/`$Schema` variable filters silently excluded all internal records.
Customer serverless tasks (warehouse-based, non-DSOA) do have populated `database_name`/`schema_name`
and were unaffected. Discovered during dashboard work (TI-003).

## Fix — `061_v_serverless_tasks.sql`

Three changes in the `select` projection of `V_SERVERLESS_TASKS`:

1. **NULLIF guards**: `NULLIF(sth.database_name, '')` and `NULLIF(sth.schema_name, '')` in
   `OBJECT_CONSTRUCT`. `OBJECT_CONSTRUCT` omits keys with NULL values, so empty strings become absent
   keys downstream. Python plugin, OtelManager, and Grail never see the empty string.

2. **`snowflake.task.is_internal` flag**: `IFF(task_name LIKE '%\_MEASUREMENT\_TASK' ESCAPE '\' OR
   task_name LIKE '%\_FINALIZER\_TASK' ESCAPE '\', true, false)`. The `ESCAPE` clause is required
   because `_` is a single-character wildcard in Snowflake LIKE patterns without an escape. Without it,
   `%_MEASUREMENT_TASK` would match any task ending in any character followed by `MEASUREMENT_TASK`,
   giving false positives. Pattern covers all plugin-specific variants
   (e.g. `TASKS_MEASUREMENT_TASK`, `DYNAMIC_TABLES_MEASUREMENT_TASK`).

3. **`_MESSAGE` fallback**: `COALESCE(NULLIF(database_name, ''), task_name)` replaces bare
   `database_name` concatenation. Internal tasks now log `"New Serverless Tasks entry for
   TASKS_MEASUREMENT_TASK"` instead of `"New Serverless Tasks entry for "`.

## instruments-def.yml

Added `snowflake.task.is_internal` under `dimensions:`. Example value: `false`. Context: `serverless_tasks`.

## Testing

Mock fixture `tasks_serverless.ndjson` updated: row 1 = user task (db.namespace populated, is_internal=false),
row 2 = internal task (db.namespace/snowflake.schema.name absent, is_internal=true). Stored test results
regenerated. `make lint` (sqlfluff, pylint 10.00/10) passes. No Python plugin changes required.

## Edge case noted

A customer could name their own task ending in `_MEASUREMENT_TASK` and get a false-positive `is_internal = true`.
Acceptable risk — extremely unlikely naming collision. Can be tightened to a DTAGENT-specific prefix in a
future release if needed.

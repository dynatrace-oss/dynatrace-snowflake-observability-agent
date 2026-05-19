# BIZOBS-193: `snowflake.table.full_name` Missing + OTel v1.28 `db.collection.name` Compliance

## Problem

The 0.9.4 refactoring introduced `snowflake.table.full_name` (fully-qualified `DB.SCHEMA.TABLE`)
as a new DIMENSIONS field for `data_volume` and `dynamic_tables` plugins, but three plugins
were missed:

- `query_history` — emitted FQN in `db.collection.name` **and** was violating OTel Semantic
  Conventions v1.28+ (which requires `db.collection.name` to be the bare table name only)
- `shares` (inbound) — emitted only short `TABLE_NAME` in `db.collection.name`, no FQN anywhere
- `snowpipes` — both the function and copy history view emitted only short table names, no FQN

This caused dashboards and workflows referencing `snowflake.table.full_name` to break or
produce empty joins when filtering across plugin sources.

## Changes

### `query_history` — `080_v_query_history_instrumented.sql`

`db.collection.name` previously held the full FQN from `ACCESS_HISTORY.base_objects_accessed`
(`DB.SCHEMA.TABLE`). This violates OpenTelemetry Semantic Conventions v1.28+ which specifies
`db.collection.name` as the bare collection/table name without namespace prefix.

Fixed by stripping to bare name with `SPLIT_PART(qh.table_name, '.', -1)` for `db.collection.name`,
while `snowflake.table.full_name` retains the original FQN (`qh.table_name`). `SPLIT_PART` on
NULL returns NULL in Snowflake, so the NULL case (no tables accessed by the query) is safe.

### OTel v1.28+ compliance audit (all plugins)

All other plugins were already compliant — `db.collection.name` values verified:

| Plugin | Source column | Type |
|---|---|---|
| `data_volume` | `TABLES.TABLE_NAME` | Short name ✅ |
| `cold_tables` | `SPLIT_PART(objectName, '.', 3)` | Short name ✅ |
| `dynamic_tables` (×3) | `DYNAMIC_TABLES().NAME` | Short name ✅ |
| `shares` inbound | `DETAILS:"TABLE_NAME"` (JSON) | Short name ✅ |
| `snowpipes` function | `SPLIT_PART(target, '.', -1)` | Short name ✅ |
| `snowpipes` copy history | `COPY_HISTORY.TABLE_NAME` | Short name ✅ |
| `table_health` (×3) | `TABLES.TABLE_NAME` / `SPLIT_PART` | Short name ✅ |

### `shares` — `061_v_inbound_shares.sql`

`db.collection.name` held only `ins.DETAILS:"TABLE_NAME"` (short name from `SHOW TERSE OBJECTS`
on imported databases). The database and schema parts were already emitted separately in
`db.namespace` and `snowflake.schema.name`. Added:

```sql
'snowflake.table.full_name', concat(s.database_name, '.', ins.DETAILS:"TABLE_SCHEMA"::STRING, '.', ins.DETAILS:"TABLE_NAME"::STRING)
```

### `snowpipes` copy history — `054_v_snowpipes_copy_history_instrumented.sql`

`COPY_HISTORY.TABLE_NAME` is a short name; catalog and schema already present as
`TABLE_CATALOG_NAME` / `TABLE_SCHEMA_NAME`. Added:

```sql
'snowflake.table.full_name', concat(TABLE_CATALOG_NAME, '.', TABLE_SCHEMA_NAME, '.', TABLE_NAME)
```

### `snowpipes` function — `053_f_snowpipes_instrumented.sql`

`SHOW PIPES` returns the pipe DDL's `COPY INTO <target>` clause which may be fully qualified,
partially qualified, or bare. Cannot assume FQN. Added a new `target_table_full_name` LET
variable with 3-way resolution:

```sql
target_table_full_name := CASE
    WHEN ARRAY_SIZE(SPLIT(:target_table, '.')) = 3 THEN :target_table
    WHEN ARRAY_SIZE(SPLIT(:target_table, '.')) = 2 THEN :pipe_db_name || '.' || :target_table
    ELSE :pipe_db_name || '.' || :pipe_schema_name || '.' || :target_table
END;
```

`pipe_db_name` and `pipe_schema_name` from the pipe's own `DATABASE_NAME`/`SCHEMA_NAME` columns
serve as fallback context. This means the resolved FQN is in the pipe's catalog — correct for
Snowpipes since they must target a table in their owning account.

## instruments-def.yml Updates

Added `snowflake.table.full_name` dimension entry to:

- `query_history.config/instruments-def.yml` (no `__context_names` filter — applies to all contexts)
- `shares.config/instruments-def.yml` (`inbound_shares` context only)
- `snowpipes.config/instruments-def.yml` (`snowpipes` and `snowpipes_copy_history` contexts)

## Test Fixture Updates

Updated NDJSON fixtures to include `snowflake.table.full_name` in DIMENSIONS:

- `test/test_data/query_history.ndjson` — duplicated FQN value from `db.collection.name`
- `test/test_data/snowpipes.ndjson` — constructed FQN from DB + schema + bare name
- `test/test_data/snowpipes_copy_history.ndjson` — same construction

Regenerated golden result files for:
- `test/test_results/test_query_history/`
- `test/test_results/test_query_history_backward_compat/`
- `test/test_results/test_query_history_max_entries/`
- `test/test_results/test_snowpipes/`

`shares` tests passed unchanged — the inbound_shares fixture rows are all share-level
(no `db.collection.name`), so no fixture changes were needed.

## Scope of Impact

Note: this fix addresses the **source data** (SQL views). The dashboard and workflow DQL
queries that use `db.collection.name` without `snowflake.table.full_name` (BIZOBS-193 scope)
are tracked separately for a follow-up pass.

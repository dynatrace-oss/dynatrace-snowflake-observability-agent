# Hardening — BCR-2275: Explicit Column Lists for ACCOUNT_USAGE Views

Snowflake BCR-2275 changed their policy so new columns in `ACCOUNT_USAGE` views are no longer announced as breaking changes. DSOA SQL views that used `SELECT *` from these system views would silently ingest unexpected columns, risking memory bloat, telemetry corruption, and test fixture drift.

## Views changed

- `data_schemas/051_v_data_schemas.sql` — replaced `SELECT *` from `ACCESS_HISTORY` with explicit 7-column list (`QUERY_ID`, `QUERY_START_TIME`, `USER_NAME`, `PARENT_QUERY_ID`, `ROOT_QUERY_ID`, `OBJECT_MODIFIED_BY_DDL`, `OBJECTS_MODIFIED`)
- `snowpipes/054_v_snowpipes_copy_history_instrumented.sql` — replaced `SELECT *` from `COPY_HISTORY` with explicit 22-column list
- `snowpipes/055_v_snowpipes_usage_history_instrumented.sql` — replaced `SELECT h.*` from `PIPE_USAGE_HISTORY` with explicit 7-column list (`PIPE_ID`, `PIPE_NAME`, `START_TIME`, `END_TIME`, `CREDITS_USED`, `BYTES_BILLED`, `FILES_INSERTED`)

## CI gate added

`test_views_structure.py::test_no_select_star_from_snowflake_views` — detects `SELECT *` / `SELECT alias.*` from any `SNOWFLAKE.*` source in active (non-commented) SQL code. Uses comment-stripping to avoid flagging debug queries. Precision-scoped to avoid false positives from files that reference `SNOWFLAKE.*` in separate statements.

## Existing test bug fixed

`test_timestamp_columns` had its assertion outside the `for` loop (only checked the last file). Fixed indentation so all instrumented views are validated.

## Doc update

Added "Never use `SELECT *` when querying Snowflake system views" rule to `PLUGIN_DEVELOPMENT.md` SQL conventions and updated the canonical view template example.

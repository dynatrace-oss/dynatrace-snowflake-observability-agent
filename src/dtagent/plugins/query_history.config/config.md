The plugin can be configured to retrieve query plan and acceleration estimates for the slowest queries. This analysis uses telemetry from the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

The following options control this behavior:

- `plugins.query_history.slow_queries_threshold`: The execution time threshold in milliseconds. Queries running longer than this are considered slow and eligible for analysis. Default: `10000` (10 seconds).
- `plugins.query_history.max_slowest_queries`: The maximum number of slowest queries to analyze. Default: `50`.

## Signal Protection Framework Configuration

The plugin supports signal protection to prevent overload on high-volume Snowflake accounts. The following options control this behavior:

- `plugins.query_history.max_entries`: Maximum number of query entries to process per run. Set to `0` for unlimited (default). When set, the view applies a `QUALIFY` filter keeping the top-N queries by execution time (descending). The pre-filter count is carried via `_TOTAL_AVAILABLE` for self-monitoring.
- `plugins.query_history.max_lookback_minutes`: Maximum lookback window in minutes for catching up on unprocessed queries. Default: `120`. The plugin uses the last-processed watermark from `STATUS.LOG_PROCESSED_MEASUREMENTS` but never looks back further than this value.
- `plugins.query_history.include_warehouses`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `plugins.query_history.exclude_warehouses`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include. Default: `["DTAGENT_WH"]`.
- `plugins.query_history.include_databases`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `plugins.query_history.exclude_databases`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `plugins.query_history.include_users`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `plugins.query_history.exclude_users`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.

> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be granted `MONITOR` privileges on all warehouses.
> By default, when the `admin` scope is installed, this is ensured through the periodic execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task.
> The schedule for this special task can be configured using the `plugins.query_history.schedule_grants` configuration option.
> Since this procedure runs with the elevated privileges of the `DTAGENT_ADMIN` role (which is only created when the `admin` scope is installed), you may choose to:
>
> - Skip the `admin` scope entirely and manually grant `MONITOR` privileges on warehouses to `DTAGENT_VIEWER`
> - Install the `admin` scope and disable the automated grant task, then manually manage `MONITOR` privileges

## Query Text Obfuscation Configuration

- `plugins.query_history.obfuscation_mode`: Controls query text obfuscation before data is sent to Dynatrace. Applies to `db.query.text` on spans and `snowflake.error.message` on failed queries. Valid values:
  - `off` (default) — no obfuscation, full query text is forwarded unchanged.
  - `literals` — replaces single-quoted string literals and standalone numeric literals with `?`. SQL structure and identifiers are preserved.
  - `full` — replaces the entire query text (and error message) with `[OBFUSCATED]`.
  Invalid values fall back to `off`.

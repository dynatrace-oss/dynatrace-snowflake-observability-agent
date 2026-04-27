The plugin can be configured to retrieve query plan and acceleration estimates for the slowest queries. This analysis uses telemetry from the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

The following options control this behavior:

- `PLUGINS.QUERY_HISTORY.SLOW_QUERIES_THRESHOLD`: The execution time threshold in milliseconds. Queries running longer than this are considered slow and eligible for analysis. Default: `10000` (10 seconds).
- `PLUGINS.QUERY_HISTORY.MAX_SLOWEST_QUERIES`: The maximum number of slowest queries to analyze. Default: `50`.

## Signal Protection Framework Configuration

The plugin supports signal protection to prevent overload on high-volume Snowflake accounts. The following options control this behavior:

- `PLUGINS.QUERY_HISTORY.MAX_ENTRIES`: Maximum number of query entries to process per run. Set to `0` for unlimited (default). When set, the view applies a `QUALIFY` filter keeping the top-N queries by execution time (descending). The pre-filter count is carried via `_TOTAL_AVAILABLE` for self-monitoring.
- `PLUGINS.QUERY_HISTORY.MAX_LOOKBACK_MINUTES`: Maximum lookback window in minutes for catching up on unprocessed queries. Default: `120`. The plugin uses the last-processed watermark from `STATUS.LOG_PROCESSED_MEASUREMENTS` but never looks back further than this value.
- `PLUGINS.QUERY_HISTORY.INCLUDE_WAREHOUSES`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `PLUGINS.QUERY_HISTORY.EXCLUDE_WAREHOUSES`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include. Default: `["DTAGENT_WH"]`.
- `PLUGINS.QUERY_HISTORY.INCLUDE_DATABASES`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `PLUGINS.QUERY_HISTORY.EXCLUDE_DATABASES`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `PLUGINS.QUERY_HISTORY.INCLUDE_USERS`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.
- `PLUGINS.QUERY_HISTORY.EXCLUDE_USERS`: Array of LIKE patterns (e.g. `PROD_%`, `MY_WH`). Empty array means no filter applied. Supports `%` and `_` wildcards. Exclude always takes precedence over include.

> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be granted `MONITOR` privileges on all warehouses.
> By default, when the `admin` scope is installed, this is ensured through the periodic execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task.
> The schedule for this special task can be configured using the `PLUGINS.QUERY_HISTORY.SCHEDULE_GRANTS` configuration option.
> Since this procedure runs with the elevated privileges of the `DTAGENT_ADMIN` role (which is only created when the `admin` scope is installed), you may choose to:
>
> - Skip the `admin` scope entirely and manually grant `MONITOR` privileges on warehouses to `DTAGENT_VIEWER`
> - Install the `admin` scope and disable the automated grant task, then manually manage `MONITOR` privileges

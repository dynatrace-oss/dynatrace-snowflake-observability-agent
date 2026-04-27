This plugin provides information on what SQL queries were run, by whom, when, and their performance. This information is extracted from the `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` view, combined with details such as related objects or estimated costs from `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY`. For the slowest queries, additional information is retrieved from the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

By default, this plugin executes every 30 minutes and analyzes queries that finished within the last 2 hours and have not already been processed.

Among the information it provides are:

- the IDs of processed queries,
- runtimes of processed queries,
- numbers of credits used by processed queries,
- number of bytes scanned during the completion of a query, and
- number of partitions scanned during the completion of a query.

Each query execution is reported as a log line and span, with a hierarchy of spans made from the relation to parent queries. If the query profile was retrieved with `QUERY_OPERATOR_STATS`, it is delivered as span events and additional log lines. This plugin also delivers many metrics based on telemetry information provided by Snowflake.

## Signal Protection Framework

On high-volume Snowflake accounts, the plugin supports signal protection to prevent overload and timeout issues. Three complementary mechanisms are available:

1. **Top-N Limiting** — Set `max_entries` to cap the number of queries processed per run. Queries are prioritized by `max_entries_sort` (default: execution time, descending) so the most expensive queries are always captured. When the cap is hit, a self-monitoring warning log and bizevent are emitted with the count of dropped rows.

2. **Include/Exclude Filters** — Use `include_warehouses`, `exclude_warehouses`, `include_databases`, `exclude_databases`, `include_users`, and `exclude_users` to filter queries at the SQL view level, reducing Snowflake compute cost. Exclude filters always take precedence over include filters.

3. **Watermark-Based Lookback** — The plugin uses the last-processed timestamp from `STATUS.LOG_PROCESSED_MEASUREMENTS` to avoid reprocessing queries. The `max_lookback_minutes` parameter caps the maximum catch-up window (default: 120 minutes), ensuring the plugin catches up incrementally if the agent was down for an extended period.

All defaults preserve backward compatibility: `max_entries=0` (unlimited), `max_lookback_minutes=120`, and `exclude_warehouses=DTAGENT_WH` (exclude the agent's own warehouse only).

**Note:** To correlate query spans with Snowflake's Snowtrail trace_id and span_id, the `event_log` plugin must be enabled. When enabled, this plugin will automatically extract trace context from the `STATUS.EVENT_LOG` table and include it in the span telemetry, allowing for distributed tracing correlation between your application and Snowflake queries.

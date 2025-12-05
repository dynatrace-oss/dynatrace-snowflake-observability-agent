This plugin provides information on what SQL queries were run, by whom, when, and their performance. This information is extracted from the `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` view, combined with details such as related objects or estimated costs from `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY`. For the slowest queries, additional information is retrieved from the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

By default, this plugin executes every 30 minutes and analyzes queries that finished within the last 2 hours and have not already been processed.

Among the information it provides are:

- the IDs of processed queries,
- runtimes of processed queries,
- numbers of credits used by processed queries,
- number of bytes scanned during the completion of a query, and
- number of partitions scanned during the completion of a query.

Each query execution is reported as a log line and span, with a hierarchy of spans made from the relation to parent queries. If the query profile was retrieved with `QUERY_OPERATOR_STATS`, it is delivered as span events and additional log lines. This plugin also delivers many metrics based on telemetry information provided by Snowflake.

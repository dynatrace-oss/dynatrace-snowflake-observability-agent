This plugin enables tracking availability and performance of running Snowflake dynamic table refreshes, via logs and a set of metrics.
Additionally, there are events sent when dynamic tables refresh tasks are executed.

The telemetry is based on checking 3 functions:

- `INFORMATION_SCHEMA.DYNAMIC_TABLES()`,
- `INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY()`, and
- `INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY()`.

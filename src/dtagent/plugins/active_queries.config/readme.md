This plugin lists currently running queries and tracks the status of queries that have finished since the last check.
It reports finding from `INFORMATION_SCHEMA.QUERY_HISTORY()` function.

Provides details on compilation and running (until now) time of the currently running query or recently finished ones.

By default information on all queries is reported as logs and metrics.

Active queries can be reported in two different modes:

- Fast mode - only reports currently active queries. Chosen with `PLUGINS.ACTIVE_QUERIES.FAST_MODE` set to `true`.
- Normal mode - reports queries with start timestamp up to 15 minutes from the current time. Chosen with `PLUGINS.ACTIVE_QUERIES.FAST_MODE` set to `false`.

Additionally, you can decide to monitor details for queries only with selected execution status, by using the `PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` configuration parameter; by default: no additional filters are applied with `PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` set to empty (`[]`).
Multiple statuses can be chosen (for example: `["RUNNING", "QUEUED"]`). This filtering will be applied on top of the chosen mode.

> **HINT:** Please note that Snowflake's `INFORMATION_SCHEMA.QUERY_HISTORY()` function can return up to 10000 most recent queries. Therefore, if you decide to monitor queries other than just those currently `RUNNING` or being `QUEUED`, on a heavily loaded Snowflake account, there might be more than 10000 queries reported within the default 10-min interval between executing the `active_queries` plugin. Hence, if you see that the following query returns 10000 at any point, you may want to adjust the schedule of the `active_queries` plugin to avoid data loss.

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "active_queries"
| filter deployment.environment == "YOUR_ENV"
| sort timestamp asc
| summarize {
  timestamp = takeFirst(timestamp),
  start = takeFirst(timestamp),
  end = takeLast(timestamp),
  timeframe = timeframe(from: takeFirst(timestamp), to:takeLast(timestamp)),
  count = count()
}, by: {
  dsoa.run.id
}
```

If you have any concerns about getting correct results reported by this plugin, please refer to [Root Cause Analysis: Missing Long-Running Queries](docs/debug/active-queries-faq/readme.md).

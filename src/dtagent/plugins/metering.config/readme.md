This plugin reports credit consumption across all Snowflake service types using the `METERING_HISTORY` view. It replaces the narrower `event_usage` plugin which only covered `EVENT_USAGE_HISTORY` (telemetry data ingest).

What data is collected:

- credits consumed (total, compute, and cloud services) per service type and entity,
- bytes, rows, and files processed per service type,
- start and end timestamps for each metering window.

`WAREHOUSE_METERING` rows are excluded to avoid duplication with the `warehouse_usage` plugin.

Key use cases:

- FinOps cost attribution across all Snowflake service types (auto-clustering, pipes, serverless tasks, AI services, replication, etc.),
- trend analysis and anomaly detection on credit consumption,
- capacity planning based on historical metering data.

## Configuration

| Key                               | Type   | Default                             | Description                                                                                                                                                |
|-----------------------------------|--------|-------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `plugins.metering.lookback_hours` | int    | `6`                                 | How far back (in hours) the plugin looks for metering history on each run. Default is `6`h to account for up-to-3-hour data latency in `METERING_HISTORY`. |
| `plugins.metering.schedule`       | string | `USING CRON 0 * * * * UTC`          | Cron schedule for the metering collection task.                                                                                                            |
| `plugins.metering.is_disabled`    | bool   | `false`                             | Set to `true` to disable this plugin entirely.                                                                                                             |
| `plugins.metering.telemetry`      | list   | `["metrics", "logs", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                   |

## Querying in Dynatrace

```dql
// All metering logs
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "metering"
| sort timestamp desc | limit 50

// Credits by service type
timeseries sum(snowflake.credits.used), by: {snowflake.service.type}
| filter db.system == "snowflake" and dsoa.run.context == "metering"

// Event table ingest only (backward compat with event_usage)
timeseries sum(snowflake.credits.used)
| filter db.system == "snowflake" and dsoa.run.context == "metering"
| filter snowflake.service.type == "TELEMETRY_DATA_INGEST"
```

## Migration from event_usage

The `event_usage` plugin is deprecated as of 0.9.5. To migrate:

1. Enable `metering` plugin (enabled by default).
1. Disable `event_usage` plugin (disabled by default as of 0.9.5).
1. Update any DQL queries that filter by `dsoa.run.plugin == "event_usage"` to use `dsoa.run.plugin == "metering"`.
1. To reproduce the exact same data as `event_usage`, add `snowflake.service.type == "TELEMETRY_DATA_INGEST"` filter.

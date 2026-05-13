This plugin enables identification of "cold" tables — tables that have not been accessed by queries for a configurable period (default: 90 days). It helps FinOps teams and Snowflake administrators identify candidates for archiving, dropping, or tiering to lower-cost storage.

The following information is reported:

- table access frequency (total count within lookback window),
- timestamp of the most recent query that accessed the table,
- number of days since last access,
- cold/warm classification based on access recency.

### Configuration

Default schedule: daily at 6 AM UTC (access patterns don't change hourly).

Configurable parameters:

- `lookback_days` (default: 365) — number of days to look back in ACCESS_HISTORY
- `cold_threshold_days` (default: 90) — tables with no access in this many days are flagged as "cold"

Example configuration:

```yaml
plugins:
  cold_tables:
    schedule: USING CRON 0 6 * * * UTC
    lookback_days: 365
    cold_threshold_days: 90
    is_disabled: false
    telemetry:
      - metrics
      - logs
```

### Known Limitations

- **Never-accessed tables not included:** ACCESS_HISTORY only contains tables that have been accessed. Tables that have never been accessed will not appear in the results. To identify truly never-accessed tables, a follow-up enhancement would join with `INFORMATION_SCHEMA.TABLES` or `ACCOUNT_USAGE.TABLES`.
- **ACCESS_HISTORY latency:** Up to 2 hours. Daily schedule is appropriate for this latency.

### Querying in Dynatrace

#### Logs — per-table detail

```dql
fetch logs
| filter db.system == "snowflake" and dsoa.run.plugin == "cold_tables"
| filter snowflake.table.cold_status == "cold"
| sort timestamp desc
| limit 50
```

#### Metrics — access count by table

```dql
timeseries avg(snowflake.table.access.count),
  by: {db.namespace, db.collection.name, snowflake.table.cold_status}
| filter db.system == "snowflake"
```

#### Metrics — days since last access

```dql
timeseries avg(snowflake.table.days_since_last_access),
  by: {db.namespace, db.collection.name}
| filter db.system == "snowflake"
| filter snowflake.table.days_since_last_access > 90
```

#### Self-monitoring — plugin performance

```dql
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "cold_tables"
| fields timestamp, dsoa.run.id, cold_tables.entries, cold_tables.log_lines, cold_tables.metrics
| sort timestamp desc
```

# Workflow: DSOA — Security Anomaly Detection

Monitors Snowflake user login activity, session counts, query volumes, and data scan sizes using
Davis AI Seasonal Baseline anomaly detection. Six parallel analyzers alert when any user or table
deviates significantly from its learned behavioral baseline — detecting compromised accounts,
runaway service accounts, or abnormal data exfiltration patterns. Requires the `login_history`
and `query_history` plugins.

## Overview

| Property         | Value                                                                               |
|------------------|-------------------------------------------------------------------------------------|
| DPO Theme        | Security                                                                            |
| Required Plugins | `login_history`, `query_history`                                                    |
| Trigger          | Every 6 hours (interval)                                                            |
| Analyzer         | `SeasonalBaselineAnomalyDetectionAnalyzer`                                          |
| Training window  | 30 days                                                                             |
| Detection window | 1 day                                                                               |

## Detection Categories

| # | Analyzer Task             | Dimension            | Metric                 | Plugin Source                  |
|---|---------------------------|----------------------|------------------------|--------------------------------|
| 1 | `ad_user_logins`          | `db.user`            | Login count            | `login_history`                |
| 2 | `ad_user_sessions`        | `db.user`            | Session count          | `login_history` (sessions ctx) |
| 3 | `ad_queries_by_user`      | `db.user`            | Query count            | `query_history`                |
| 4 | `ad_queries_by_table`     | `db.collection.name` | Query count            | `query_history`                |
| 5 | `ad_scanned_bytes_user`   | `db.user`            | Scanned bytes (KB sum) | `query_history`                |
| 6 | `ad_scanned_bytes_table`  | `db.collection.name` | Scanned bytes (KB sum) | `query_history`                |

## How It Works

1. **Six Davis AI analyzer tasks** run in parallel. Each queries the last 24 hours of logs,
   trains on the last 30 days of history, and raises alerts when the current signal exceeds
   the learned seasonal baseline by the configured tolerance factor.

2. **`extract_anomaly_events`** — Runs after all six analyzers complete. Collects raised alerts
   from each analyzer result, builds Dynatrace event objects with standard properties including
   `ad.direction`, `ad.category`, and `ad.source`, and returns them as a list.

3. **`ingest_anomaly_events`** — Ingests the event list into Dynatrace via the Environment V2
   Events API.

## Prerequisites

- DSOA deployed and collecting telemetry from your Snowflake account
- `login_history` plugin enabled (provides login and session log records)
- `query_history` plugin enabled (provides query records with `db.user`, `db.collection.name`,
  `snowflake.data.scanned`)
- At least 30 days of historical data recommended for accurate baseline training

## Configuration

### Scope Customization

Each analyzer task contains commented-out filter examples. Uncomment and adjust as needed:

Filter by specific users (user-level tasks):

```dql
// | filter db.user IN ("SVC_ETL", "SVC_ANALYTICS")
```

Filter by environment:

```dql
// | filter deployment.environment == "PROD"
```

Filter by database or schema (table-level tasks):

```dql
// | filter startsWith(db.collection.name, "PROD_DB.")
// | filter contains(db.collection.name, ".ETL.")
```

### Tunable Parameters

At the top of each analyzer task body, these parameters control sensitivity:

| Parameter            | Default (user tasks)           | Default (table tasks) | Description                                        |
|----------------------|--------------------------------|-----------------------|----------------------------------------------------|
| `tolerance`          | 1.5 (login/session), 4 (query) | 4–5                   | Multiplier above baseline before alerting          |
| `slidingWindow`      | 2                              | 2–3                   | Number of consecutive intervals evaluated          |
| `violatingSamples`   | 1                              | 1–2                   | Samples exceeding threshold before alert fires     |
| `dealertingSamples`  | 2                              | 2–3                   | Samples below threshold before alert clears        |
| `alertOnMissingData` | `true`                         | `false`               | Alert when a user/table stops reporting entirely   |
| `intervalMinutes`    | 360 (trigger)                  | —                     | How often the workflow runs                        |

### Event Type

At the top of the `extract_anomaly_events` task, the `CONFIG` block controls event behavior:

```javascript
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,  // Change to CustomAlert to trigger Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.security_anomaly'
};
```

- **`CustomInfo`** (default) — informational events visible in the Events feed; no Davis problem created
- **`CustomAlert`** — triggers Davis AI problem correlation; recommended for production security monitoring

## Event Properties

| Property                    | Example Value                                      | Description                                   |
|-----------------------------|----------------------------------------------------|-----------------------------------------------|
| `event.type`                | `CustomInfo`                                       | Event type (configurable)                     |
| `ad.source`                 | `dsoa.security_anomaly`                            | Identifies the DSOA security anomaly workflow |
| `ad.source_metric`          | `snowflake.login.count`                            | Metric that triggered the anomaly             |
| `ad.direction`              | `above`                                            | Direction of anomaly relative to baseline     |
| `ad.category`               | `login` / `session` / `query_count` / `data_scan`  | Category of security anomaly detected         |
| `db.user`                   | `SVC_ETL`                                          | Snowflake user (user-level events)            |
| `db.collection.name`        | `PROD_DB.ETL.ORDERS`                               | Table name (table-level events)               |
| `deployment.environment`    | `PROD`                                             | Snowflake account environment tag             |
| `metric_name`               | `snowflake.data.scanned`                           | Metric name from the analyzer                 |
| `event.start`               | ISO timestamp                                      | Start of the anomalous timeframe              |
| `event.end`                 | ISO timestamp                                      | End of the anomalous timeframe                |
| `event.description`         | Human-readable description                         | Full event description with context           |

## Troubleshooting

### No events generated

- Confirm `login_history` and `query_history` plugins are active and producing logs
- Verify at least 30 days of baseline data exist; Davis cannot train on insufficient history
- Check the analyzer task result in the Workflow execution log for `analysisStatus != OK` entries
- Try reducing `tolerance` (e.g., from 4 to 2) for more sensitive detection

### Too many alerts / false positives

- Increase `tolerance` on noisy tasks (e.g., from 1.5 to 3 for `ad_user_logins`)
- Increase `violatingSamples` (e.g., to 2 or 3) to require sustained anomalies
- Add user or table scope filters to exclude high-volume service accounts or system tables

### DQL errors in analyzer tasks

- Verify the `dsoa.run.context` attribute is present on log records — check with
  `fetch logs | filter isNotNull(dsoa.run.context) | limit 5`
- For table-level tasks, confirm `db.snowflake.tables` or `db.collection.name` attributes
  exist on query_history log records

### `ad_scanned_bytes_user` produces no results

- This task requires `snowflake.data.scanned` to be non-null; confirm the query_history plugin
  version supports this attribute
- Check `fetch logs | filter dsoa.run.context == "query_history" | filter isNotNull(snowflake.data.scanned) | limit 1`

## Screenshots

<!-- Add screenshots after deployment -->

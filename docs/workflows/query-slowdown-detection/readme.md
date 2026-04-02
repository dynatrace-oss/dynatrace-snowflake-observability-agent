# Workflow: Query Slowdown Detection

Monitors average query execution time per warehouse and database combination using Davis AI
anomaly detection. Fires an event when execution time significantly exceeds the learned baseline,
detecting warehouse-level degradation, resource contention, or regressions from poorly optimized
queries. Only successful queries are analyzed to avoid noise from failed executions.

## Overview

| Property        | Value                                  |
|-----------------|----------------------------------------|
| DPO Theme       | Performance                            |
| Required Plugin | `query_history`                        |
| Trigger         | Every 6 hours (interval)               |
| Alert condition | ABOVE baseline (rising execution time) |
| Training window | 14 days                                |
| Event source    | `dsoa.query_slowdown`                  |

## How It Works

1. **`detect_slowdown`** — Davis AI (`AutoAdaptiveAnomalyDetectionAnalyzer`) runs against a
   time-series of average execution time per warehouse / database pair. It learns the typical
   execution time pattern over 14 days and raises an alert when average time rises significantly
   above that baseline. Only `SUCCESS` queries are included to prevent error spikes from
   skewing the signal.

1. **`extract_anomaly_events`** — Processes Davis results and builds Dynatrace event payloads,
   one per raised alert. Dimensions from the analyzer (warehouse name, database, environment) are
   attached as event properties.

1. **`ingest_anomaly_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

Queries the `snowflake.time.execution` metric from the `query_history` plugin via native `timeseries`:

| Field                              | Role                                |
|------------------------------------|-------------------------------------|
| `snowflake.warehouse.name`         | Dimension (per-warehouse series)    |
| `db.namespace`                     | Dimension (per-database series)     |
| `snowflake.time.execution`         | Metric (query execution time in ms) |
| `snowflake.query.execution_status` | Filter (`SUCCESS` queries only)     |
| `deployment.environment`           | Dimension (environment scope)       |

## Event Properties

Each ingested event carries:

| Property                   | Value                                |
|----------------------------|--------------------------------------|
| `event.type`               | `CustomInfo` (default)               |
| `ad.source`                | `dsoa.query_slowdown`                |
| `ad.source_metric`         | `snowflake.query.execution_time.avg` |
| `event.start/end`          | Anomaly timeframe from Davis         |
| `snowflake.warehouse.name` | Affected warehouse                   |
| `db.namespace`             | Affected database                    |
| `deployment.environment`   | Snowflake environment                |

## Customization

At the top of the `extract_anomaly_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.query_slowdown'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.
- **`numberOfSignalFluctuations`**: Set to `2` (higher than other workflows) to reduce false
  positives — query times naturally have higher variance.

## Prerequisites

- `query_history` plugin enabled and collecting telemetry.
- At least 7 days of history for meaningful baselines (14 days recommended).

## Screenshots

<!-- Add screenshots after deployment -->

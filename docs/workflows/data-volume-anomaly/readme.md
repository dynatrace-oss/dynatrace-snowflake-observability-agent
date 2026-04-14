# Workflow: Data Volume Anomaly Detection

Monitors row count changes per Snowflake table using Davis AI seasonal anomaly detection. Fires
an event when any of the top-10 most actively growing tables shows an abnormal spike in row count
compared to its learned seasonal baseline — catching unexpected bulk loads, runaway ingestion, or
data duplication events.

## Overview

| Property        | Value                                             |
|-----------------|---------------------------------------------------|
| DPO Theme       | Quality                                           |
| Required Plugin | `data_volume`                                     |
| Trigger         | Every 12 hours (interval)                         |
| Analyzer        | `SeasonalBaselineAnomalyDetectionAnalyzer`        |
| Alert condition | ABOVE baseline (unexpected row count increase)    |
| Training window | 30 days                                           |
| Scope           | Top 10 tables by largest positive row-count delta |
| Event source    | `dsoa.data_volume_anomaly`                        |

## How It Works

1. **`detect_volume_anomaly`** — Queries the native `timeseries` metric `snowflake.data.rows`
   per table and environment at daily intervals over 30 days. Computes a rolling average and
   subtracts it from the series to produce a mean-adjusted delta. Only tables with a positive
   delta (growing) are retained; the top 10 by largest delta are passed to Davis AI
   (`SeasonalBaselineAnomalyDetectionAnalyzer`) which detects spikes above the seasonal baseline.

1. **`extract_anomaly_events`** — Processes Davis results and builds Dynatrace event payloads,
   one per raised alert. Dimensions from the analyzer (table name, environment) are attached as
   event properties.

1. **`ingest_anomaly_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

Queries the `snowflake.data.rows` metric from the `data_volume` plugin:

| Field                    | Role                          |
|--------------------------|-------------------------------|
| `snowflake.data.rows`    | Metric (row count snapshot)   |
| `db.collection.name`     | Dimension (per-table series)  |
| `deployment.environment` | Dimension (environment scope) |

## Event Properties

Each ingested event carries:

| Property                 | Value                        |
|--------------------------|------------------------------|
| `event.type`             | `CustomInfo` (default)       |
| `ad.source`              | `dsoa.data_volume_anomaly`   |
| `ad.source_metric`       | `snowflake.data.rows`        |
| `event.start/end`        | Anomaly timeframe from Davis |
| `db.collection.name`     | Affected table               |
| `deployment.environment` | Snowflake environment        |

## Customization

At the top of the `extract_anomaly_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.data_volume_anomaly'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.

## Prerequisites

- `data_volume` plugin enabled and collecting telemetry.
- At least 7 days of metric history for meaningful baselines (30 days recommended).

## Screenshots

<!-- Add screenshots after deployment -->

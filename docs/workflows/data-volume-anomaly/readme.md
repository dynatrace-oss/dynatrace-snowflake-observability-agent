# Workflow: Data Volume Anomaly Detection

Monitors row count changes per Snowflake table using Davis AI seasonal anomaly detection. Fires
an event when any table shows an abnormal spike or drop in row count compared to its learned
seasonal baseline — catching unexpected bulk loads, failed pipelines, accidental deletes, and
disappeared tables. Tables that stop reporting entirely are also flagged as potential drop
anomalies.

## Overview

| Property         | Value                                                       |
|------------------|-------------------------------------------------------------|
| DPO Theme        | Quality                                                     |
| Required Plugin  | `data_volume`                                               |
| Trigger          | Every 12 hours (interval)                                   |
| Analyzer         | `SeasonalBaselineAnomalyDetectionAnalyzer`                  |
| Alert conditions | ABOVE baseline (spike) and BELOW baseline (drop)            |
| Training window  | 30 days                                                     |
| Scope            | All tables reported by `data_volume` plugin (configurable)  |
| Event source     | `dsoa.data_volume_anomaly`                                  |

## How It Works

The workflow runs two analyzer tasks in parallel, then merges results into a single event stream:

1. **`detect_volume_spike`** — Queries `snowflake.data.rows` per table and environment at daily
   intervals over 30 days. Passes all tables to Davis AI (`SeasonalBaselineAnomalyDetectionAnalyzer`)
   with `alertCondition: ABOVE` to detect unexpected row count growth relative to the seasonal
   baseline (bulk loads, runaway ingestion, data duplication).

1. **`detect_volume_drop`** — Runs the same DQL query with `alertCondition: BELOW` and a tighter
   sensitivity (`tolerance: 3`, `slidingWindow: 3`). Also sets `alertOnMissingData: true` so tables
   that stop reporting entirely — a strong signal of pipeline failure or dropped tables — generate
   an alert immediately.

1. **`extract_anomaly_events`** — Waits for both analyzers to complete, then merges their results
   into a single list of Dynatrace event payloads. Each event carries an `ad.direction` property
   (`above` or `below`) to distinguish spike from drop anomalies.

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

| Property                 | Value                             |
|--------------------------|-----------------------------------|
| `event.type`             | `CustomInfo` (default)            |
| `ad.source`              | `dsoa.data_volume_anomaly`        |
| `ad.source_metric`       | `snowflake.data.rows`             |
| `ad.direction`           | `above` (spike) or `below` (drop) |
| `event.start/end`        | Anomaly timeframe from Davis      |
| `db.collection.name`     | Affected table                    |
| `deployment.environment` | Snowflake environment             |

## Customization

### Scope by database, schema, or table pattern

By default, all tables reported by the `data_volume` plugin are analyzed. To narrow the scope,
uncomment and adapt one of the filter examples in the DQL of either analyzer task:

```dql
// Scope to a specific database:
| filter db.collection.name startsWith "PROD_DB"

// Scope to tables in a specific schema:
| filter contains(db.collection.name, ".ETL.")

// Scope to tables matching a name pattern:
| filter matchesPhrase(db.collection.name, "FACT_")
```

Apply the same filter to both `detect_volume_spike` and `detect_volume_drop` to keep detection
symmetric.

### Event type and alert behavior

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

### Tunable analyzer parameters

Both analyzer tasks expose the following parameters that can be adjusted in the workflow YAML:

| Parameter           | Spike task | Drop task | Effect                                                         |
|---------------------|------------|-----------|----------------------------------------------------------------|
| `tolerance`         | `4`        | `3`       | Sensitivity multiplier; lower = more alerts, higher = fewer    |
| `slidingWindow`     | `5`        | `3`       | Evaluation window in data points (daily intervals)             |
| `violatingSamples`  | `3`        | `2`       | Consecutive violations needed to raise an alert                |
| `dealertingSamples` | `5`        | `3`       | Consecutive recoveries needed to close an alert                |
| `alertOnMissingData` | `false`    | `true`    | Whether missing data points count as a violation               |

Drop detection uses tighter defaults because unexpected table shrinkage is a higher-severity
signal than growth spikes.

## Prerequisites

- `data_volume` plugin enabled and collecting telemetry.
- At least 7 days of metric history for meaningful baselines (30 days recommended).

## Troubleshooting

### No events generated after deployment

- Confirm the `data_volume` plugin is active and `snowflake.data.rows` appears in metrics.
- Davis AI needs at least 7 days of baseline data before it can raise anomalies; allow time
  for the model to warm up.
- Check workflow execution logs for DQL errors in the analyzer tasks.

### Drop alerts firing immediately after enabling

- If the `data_volume` plugin was recently enabled, there is no baseline yet. Davis will
  stabilize after 7–14 days. Temporarily raise `tolerance` on `detect_volume_drop` to reduce
  noise during warmup.

### Too many spike alerts / alert fatigue

- Raise `tolerance` on `detect_volume_spike` (e.g., from `4` to `6`).
- Switch `eventType` to `CustomAlert` only for drops (requires splitting the CONFIG into two
  separate `extract_anomaly_events` tasks).

### Tables with bursty load patterns generate false positives

- Scope the analyzers to exclude high-variance staging tables using the filter examples above.

## Screenshots

<!-- Add screenshots after deployment -->

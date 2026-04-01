# Workflow: Table Performance Degradation Detection

Monitors partition scan ratios per table using Davis AI anomaly detection. A rising scan ratio
(partitions scanned / total partitions) indicates a table may need re-clustering, leading to
increasingly expensive full or near-full table scans and degraded query performance.

## Overview

| Property        | Value                                        |
|-----------------|----------------------------------------------|
| DPO Theme       | Performance                                  |
| Required Plugin | `query_history`                              |
| Trigger         | Every 12 hours (interval)                    |
| Alert condition | ABOVE baseline (rising partition scan ratio) |
| Training window | 14 days                                      |
| Event source    | `dsoa.table_perf_degradation`                |

## How It Works

1. **`detect_degradation`** — Davis AI (`AutoAdaptiveAnomalyDetectionAnalyzer`) runs against a
   time-series of partition scan ratio per table, computed as `scanned_max / total_max` from the
   native `timeseries` metrics `snowflake.partitions.scanned` and `snowflake.partitions.total`.
   It learns the normal scan ratio over 14 days and raises an alert when the ratio consistently
   exceeds the baseline, signalling clustering drift. Only `SUCCESS` queries are included via
   the metric `filter:` block.

1. **`extract_anomaly_events`** — Processes Davis results and builds Dynatrace event payloads,
   one per raised alert. Dimensions from the analyzer (table name, environment) are attached as
   event properties.

1. **`ingest_anomaly_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

Queries the `snowflake.partitions.*` metrics from the `query_history` plugin via native `timeseries`:

| Field                              | Role                                     |
|------------------------------------|------------------------------------------|
| `db.collection.name`               | Dimension (per-table series)             |
| `snowflake.partitions.scanned`     | Metric (partitions scanned by the query) |
| `snowflake.partitions.total`       | Metric (total partitions in the table)   |
| `snowflake.query.execution_status` | Filter (`SUCCESS` queries only)          |
| `deployment.environment`           | Dimension (environment scope)            |

## Event Properties

Each ingested event carries:

| Property                 | Value                                  |
|--------------------------|----------------------------------------|
| `event.type`             | `CustomInfo` (default)                 |
| `ad.source`              | `dsoa.table_perf_degradation`          |
| `ad.source_metric`       | `snowflake.table.partition_scan_ratio` |
| `event.start/end`        | Anomaly timeframe from Davis           |
| `db.collection.name`     | Affected table                         |
| `deployment.environment` | Snowflake environment                  |

## Customization

At the top of the `extract_anomaly_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.table_perf_degradation'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.

## Recommended Action

When this workflow fires, investigate the flagged table:

1. Check clustering depth: `SYSTEM$CLUSTERING_INFORMATION('<table>')`
1. If clustering depth is high (> 1.2), consider running `ALTER TABLE <table> RECLUSTER`
1. Review automatic clustering configuration if the table grows continuously

## Prerequisites

- `query_history` plugin enabled and collecting telemetry.
- At least 7 days of history for meaningful baselines (14 days recommended).

## Screenshots

<!-- Add screenshots after deployment -->

# Workflow: Dynamic Table Refresh Drift Detection

Monitors scheduling lag versus target lag for Snowflake dynamic tables using Davis AI anomaly
detection. Fires an event when excess lag (actual mean lag minus target lag) grows beyond the
learned baseline, indicating a table is drifting behind its freshness SLA. Tables that stop
reporting (suspended or failing) are also flagged.

## Overview

| Property        | Value                                           |
|-----------------|-------------------------------------------------|
| DPO Theme       | Quality / Performance                           |
| Required Plugin | `dynamic_tables`                                |
| Trigger         | Every 6 hours (interval)                        |
| Alert condition | ABOVE baseline (excess lag growing)             |
| Training window | 14 days                                         |
| Event source    | `dsoa.dynamic_table_drift`                      |

## How It Works

1. **`detect_lag_drift`** — Davis AI (`AutoAdaptiveAnomalyDetectionAnalyzer`) runs against a
   time-series of excess lag per dynamic table (`mean_lag - target_lag`). It learns normal drift
   over 14 days and raises an alert when excess lag consistently exceeds the baseline.
   Missing data (table no longer refreshing) is also flagged (`alertOnMissingData: true`).

1. **`extract_anomaly_events`** — Processes Davis results and builds Dynatrace event payloads,
   one per raised alert. Dimensions from the analyzer (table name, environment) are attached as
   event properties.

1. **`ingest_anomaly_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

Queries `timeseries` metrics directly from the `dynamic_tables` plugin:

| Metric / Field                               | Role                              |
|----------------------------------------------|-----------------------------------|
| `snowflake.table.dynamic.lag.mean`           | Metric (measured scheduling lag)  |
| `snowflake.table.dynamic.lag.target.value`   | Metric (SLA target lag)           |
| `snowflake.table.full_name`                  | Dimension (per-table series)      |
| `deployment.environment`                     | Dimension (environment scope)     |

The analyzer computes `lag_excess = lag_mean - target_lag` in the timeseries query, feeding the
derived metric directly to Davis without requiring a `fetch events` → `makeTimeseries` round-trip.

## Event Properties

Each ingested event carries:

| Property                       | Value                                           |
|--------------------------------|-------------------------------------------------|
| `event.type`                   | `CustomInfo` (default)                          |
| `ad.source`                    | `dsoa.dynamic_table_drift`                      |
| `ad.source_metric`             | `snowflake.table.dynamic.lag.excess`            |
| `event.start/end`              | Anomaly timeframe from Davis                    |
| `snowflake.table.full_name`    | Affected dynamic table                          |
| `deployment.environment`       | Snowflake environment                           |

## Customization

At the top of the `extract_anomaly_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.dynamic_table_drift'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.

## Prerequisites

- `dynamic_tables` plugin enabled and collecting telemetry.
- At least 7 days of history for meaningful baselines (14 days recommended).

## Screenshots

<!-- Add screenshots after deployment -->

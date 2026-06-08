# Workflow: Long-Running Queries Detection

Monitors maximum query execution time per warehouse and per user using Davis AI anomaly detection.
Fires an event when max execution time significantly exceeds the learned seasonal baseline,
detecting individual long-running queries that would be invisible to average-based detectors.
Only successful queries are analyzed to avoid noise from failed executions.

## Overview

| Property        | Value                                        |
|-----------------|----------------------------------------------|
| DPO Theme       | Performance                                  |
| Required Plugin | `query_history`                              |
| Trigger         | Every 6 hours (interval)                     |
| Alert condition | ABOVE baseline (rising max execution time)   |
| Tolerance       | 3 (higher than avg-based; max() is spikier)  |
| Event source    | `dsoa.long_running_queries`                  |

## Relationship to Other Approaches

DSOA provides three complementary approaches to long-running query detection. Use all three
together for complete coverage:

| Approach                              | Timing     | Detection scope              | Metric                   |
|---------------------------------------|------------|------------------------------|--------------------------|
| `active_queries` plugin               | Real-time  | Individual running queries   | Configurable threshold   |
| `query-slowdown-detection` workflow   | Post-hoc   | Per-warehouse + per-database | `avg(execution_time)`    |
| **This workflow** (long-running)      | Post-hoc   | Per-warehouse + per-user     | `max(execution_time)`    |

- **`active_queries`**: catches queries _while they run_ but requires Snowflake API access and
  may miss short spikes.
- **`query-slowdown-detection`**: detects warehouse-level degradation trends; `avg()` suppresses
  individual outliers by design.
- **This workflow**: detects outlier queries _after_ completion; `max()` surfaces a single
  anomalous query even when the warehouse average looks healthy.

## How It Works

```text
ad_long_running_by_warehouse ─┐
                               ├─> extract_anomaly_events ──> ingest_anomaly_events
ad_long_running_by_user      ─┘
```

1. **`ad_long_running_by_warehouse`** — Davis AI (`SeasonalBaselineAnomalyDetectionAnalyzer`) runs
   against a time-series of max execution time per warehouse. It learns the typical max-duration
   pattern (including weekly seasonality) and raises an alert when the max rises significantly above
   that baseline. Only `SUCCESS` queries are included.

1. **`ad_long_running_by_user`** — Identical analysis grouped by `db.user` instead of warehouse,
   catching users whose queries suddenly run much longer than their personal baseline.

1. **`extract_anomaly_events`** — Fan-in task: collects raised alerts from both analyzers, builds
   Dynatrace event payloads with all relevant dimensions attached as event properties. Waits for
   both predecessors via `predecessors`, then JS try/catch skips any failed task so partial results
   are never lost.

1. **`ingest_anomaly_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

Queries the `snowflake.time.execution` metric from the `query_history` plugin:

| Field                              | Role                                    |
|------------------------------------|-----------------------------------------|
| `snowflake.warehouse.name`         | Dimension (per-warehouse series)        |
| `db.user`                          | Dimension (per-user series)             |
| `snowflake.time.execution`         | Metric (query execution time in ms)     |
| `snowflake.query.execution_status` | Filter (`SUCCESS` queries only)         |
| `deployment.environment`           | Dimension (environment scope)           |

## Event Properties

Each ingested event carries:

| Property                   | Value                                        |
|----------------------------|----------------------------------------------|
| `event.type`               | `CustomInfo` (default)                       |
| `ad.source`                | `dsoa.long_running_queries`                  |
| `ad.source_metric`         | `snowflake.query.execution_time.max`         |
| `ad.direction`             | `above`                                      |
| `event.start/end`          | Anomaly timeframe from Davis                 |
| `snowflake.warehouse.name` | Affected warehouse (warehouse analyzer only) |
| `db.user`                  | Affected user (user analyzer only)           |
| `deployment.environment`   | Snowflake environment                        |

## Customization

At the top of the `extract_anomaly_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.long_running_queries'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close (default: 360 = 6 h).

The Davis analyzer tasks also expose tunable parameters:

| Parameter          | Default | Effect                                                          |
|--------------------|---------|-----------------------------------------------------------------|
| `tolerance`        | `3`     | Sensitivity — lower catches more anomalies, higher reduces FPs  |
| `slidingWindow`    | `3`     | Number of consecutive intervals evaluated as a window           |
| `violatingSamples` | `2`     | Intervals within the window that must violate to raise an alert |
| `dealertingSamples`| `3`     | Intervals that must recover before closing an alert             |
| `intervalMinutes`  | `360`   | Workflow trigger frequency; increase to reduce API load         |

### Scoping Analyzers

Both analyzer tasks include commented-out `| filter` lines for scoping:

```dql
// Warehouse analyzer — restrict to specific warehouses:
| filter in(snowflake.warehouse.name, "COMPUTE_WH", "ANALYTICS_WH")

// User analyzer — restrict to specific users:
| filter in(db.user, "ANALYST", "ETL_USER")

// Either analyzer — restrict to a specific environment:
| filter deployment.environment == "prod"
```

Uncomment and adjust these filters directly in the workflow YAML before deploying.

## Prerequisites

- `query_history` plugin enabled and collecting telemetry.
- At least 7 days of history for meaningful baselines (14 days recommended for seasonal learning).

## Screenshots

<!-- Add screenshots after deployment -->

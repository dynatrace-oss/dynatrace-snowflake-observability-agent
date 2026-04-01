# Workflow: Credits Exhaustion Prediction

Forecasts credit consumption per Snowflake resource monitor over the next 14 days using Davis AI.
Fires an event when the forecast predicts any active monitor will exceed 100% of its credit quota
before the period resets.

## Overview

| Property         | Value                                   |
|------------------|-----------------------------------------|
| DPO Theme        | Costs                                   |
| Required Plugin  | `resource_monitors`                     |
| Trigger          | Every 4 hours (interval)                |
| Analyzer         | `dt.statistics.GenericForecastAnalyzer` |
| Forecast horizon | 14 days                                 |
| Threshold        | 100% credit quota usage                 |
| Event source     | `dsoa.credits_exhaustion`               |

## How It Works

1. **`detect_exhaustion`** — Davis AI (`GenericForecastAnalyzer`) runs a 14-day forecast of
   `snowflake.credits.quota.used_pct` per resource monitor. The metric is queried via `timeseries`
   with `by: { snowflake.resource_monitor.name, deployment.environment }` — only dimensions are
   allowed in `by:`, not attributes. The analyzer result is accessed as `result.output[]`: one
   element per monitor×environment with `timeSeriesDataWithPredictions.records[0]` containing
   `dt.davis.forecast:upper/point/lower` arrays (14 daily values each).

1. **`check_prediction`** — JavaScript task that iterates `analyzerResult.result.output`. For each
   monitor it reads `dt.davis.forecast:upper` (the 90th-percentile upper bound) and checks if
   any value exceeds `thresholdPct` (default 100). Also captures the point-forecast peak and the
   first day of crossing. Returns `{ violation: bool, violations: [] }`. Skips entries with
   `forecastQualityAssessment == 'NO_DATA'`.

1. **`ingest_prediction_events`** — Sends one Dynatrace event per violating monitor via the
   Environment V2 Events API. Only executes when `check_prediction` returns `violation == true`,
   avoiding unnecessary API calls when no threshold is breached.

## Telemetry Source

Queries `timeseries` metrics from the `resource_monitors` plugin:

| Metric / Field                     | Role                           |
|------------------------------------|--------------------------------|
| `snowflake.credits.quota.used_pct` | Metric (% of quota consumed)   |
| `snowflake.resource_monitor.name`  | Dimension (per-monitor series) |
| `deployment.environment`           | Dimension (environment scope)  |

> **Note:** `snowflake.resource_monitor.is_active` is an attribute (not a dimension) and cannot
> be used as a `timeseries` filter. All monitors with data are included; inactive monitors will
> naturally produce flat/zero forecasts that won't exceed the threshold.

## Event Properties

Each ingested event carries:

| Property                          | Value                                      |
|-----------------------------------|--------------------------------------------|
| `event.type`                      | `CUSTOM_INFO` (default)                    |
| `ad.source`                       | `dsoa.credits_exhaustion`                  |
| `ad.source_metric`                | `snowflake.credits.quota.used_pct`         |
| `snowflake.resource_monitor.name` | Affected monitor                           |
| `deployment.environment`          | Snowflake environment                      |
| `forecast.max_upper_pct`          | 90th-percentile peak forecast (%)          |
| `forecast.max_point_pct`          | Median (point) peak forecast (%)           |
| `forecast.day_of_crossing`        | First day (1-indexed) upper bound > 100%   |
| `forecast.quality`                | Forecast quality (`VALID` / `LOW_QUALITY`) |

## Customization

At the top of the `check_prediction` task there is a `CONFIG` block:

```js
const CONFIG = {
  thresholdPct: 100,       // alert when forecast exceeds this credit usage %
  eventType: 'CUSTOM_INFO', // use 'CUSTOM_ALERT' to trigger Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.credits_exhaustion'
};
```

- **`thresholdPct`**: Adjust the alert threshold (e.g. `80` for early warning at 80% quota).
- **`eventType`**: Switch to `CUSTOM_ALERT` to enable Davis problem correlation and receive
  problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.

## Prerequisites

- `resource_monitors` plugin enabled and collecting telemetry.
- At least 7 days of metric history for a useful forecast (30 days recommended).

## Screenshots

<!-- Add screenshots after deployment -->

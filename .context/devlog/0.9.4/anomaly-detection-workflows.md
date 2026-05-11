# Five Anomaly Detection Workflows

Five Davis AI anomaly detection workflows covering core Snowflake observability themes:

| Workflow | Plugin | Analyzer | Interval | Alert Condition |
|----------|--------|----------|----------|-----------------|
| Credits Exhaustion Prediction | `resource_monitors` | `GenericForecastAnalyzer` | 4 h | upper-bound forecast > 100% |
| Query Slowdown Detection | `query_history` | `AutoAdaptiveAnomalyDetectionAnalyzer` | 6 h | ABOVE (avg exec time) |
| Data Volume Anomaly Detection | `data_volume` | `SeasonalBaselineAnomalyDetectionAnalyzer` | 12 h | ABOVE (row count spike, top 10 tables) |
| Table Performance Degradation Detection | `query_history` | `AutoAdaptiveAnomalyDetectionAnalyzer` | 12 h | ABOVE (partition scan ratio) |
| Dynamic Table Refresh Drift Detection | `dynamic_tables` | `AutoAdaptiveAnomalyDetectionAnalyzer` | 6 h | ABOVE (excess lag) |

**All workflows use native `timeseries` DQL** — not `fetch logs/events | makeTimeseries`. This
is required because Davis analyzers expect metric dimensions in `by:` clauses; attributes
(non-dimension fields) cannot be used in `timeseries` filters or `by:` and would cause a
`FIELD_DOES_NOT_EXIST` error at runtime.

**3-task pattern (anomaly detection workflows):**

1. `davis-analyze` task — runs a Davis analyzer against a native `timeseries` DQL query. The
   time-series appends `metric_name`, `_event_name_template`, and `_event_description_template`
   fields via `fieldsAdd` so the JS tasks have access to per-series metadata.
1. `extract_anomaly_events` JS — iterates `analyzerResult.output[]`, builds one Dynatrace event
   object per raised alert, templates dimension values into title/description via
   `{dims:field.name}` placeholders.
1. `ingest_anomaly_events` JS — calls `eventsClient.createEvent()` per event, logs success/fail
   counts.

**Credits exhaustion uses a different 3-task pattern** (forecast, not anomaly detection):

1. `detect_exhaustion` — `GenericForecastAnalyzer` forecasts `snowflake.credits.quota.used_pct`
   14 days ahead with `coverageProbability: 0.9`. Result is accessed as
   `analyzerResult.result.output[]` — each entry has `timeSeriesDataWithPredictions.records[0]`
   with `dt.davis.forecast:upper/point/lower` arrays (14 daily values) and dimension values as
   flat properties on the record.
1. `check_prediction` JS — iterates `result.output`, checks if `dt.davis.forecast:upper` exceeds
   100% anywhere in the 14-day window. Returns `{ violation: bool, violations: [] }`. Skips
   entries with `forecastQualityAssessment == 'NO_DATA'`.
1. `ingest_prediction_events` JS — fires only when `violation == true` (custom condition);
   ingests one event per violating monitor with `forecast.max_upper_pct`,
   `forecast.max_point_pct`, `forecast.day_of_crossing`, and `forecast.quality` properties.

**Event type design decision:** Defaults to `EventIngestEventType.CustomInfo` rather than
`CustomAlert`. `CustomInfo` events appear in the Dynatrace event feed and can be correlated in
notebooks/dashboards without triggering Davis problems and on-call noise. Customers who want
Davis problem correlation switch to `CustomAlert` in the `CONFIG` block at the top of
`extract_anomaly_events` (or `check_prediction` for credits exhaustion).

**Data volume — top-10 scoping:** Rather than monitoring all tables, the query computes a
mean-adjusted row-count delta (`row_count[] - arrayAvg(row_count)`), filters for tables with a
positive delta, sorts descending, and limits to 10. This focuses the seasonal detector on the
most actively changing tables and avoids training degradation from hundreds of near-static series.

**Training windows:** Credits exhaustion and data volume use 30-day windows (slower-moving
cost/quality signals); query slowdown and table degradation use 14 days (performance signals
fluctuate faster); dynamic table drift uses the default window.

**Files:**

- `docs/workflows/credits-exhaustion-prediction/credits-exhaustion-prediction.yml`
- `docs/workflows/data-volume-anomaly/data-volume-anomaly.yml`
- `docs/workflows/dynamic-table-drift/dynamic-table-drift.yml`
- `docs/workflows/query-slowdown-detection/query-slowdown-detection.yml`
- `docs/workflows/table-perf-degradation/table-perf-degradation.yml`
- Each workflow has a `readme.md` and `img/.gitkeep`
- `docs/workflows/README.md` — Available Workflows table updated with all 5 entries
- `test/tools/setup_test_workflows.sql` — synthetic Snowflake objects for end-to-end validation

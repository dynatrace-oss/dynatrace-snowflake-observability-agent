# Dashboard: Snowflake Performance Explorer

Consolidated performance investigation flow for Snowflake environments — from fleet-level KPIs
through warehouse breakdown and grouped query pattern analysis to individual long-running query
drill-down. Designed for DBAs, platform engineers, and on-call responders who need a single
starting point for performance triage.

## Purpose

The dashboard empowers teams to:

- Assess fleet health at a glance with total query count, total elapsed time, error rate, and
  average execution time KPIs
- Identify which warehouses are spending the most time in compilation, execution, or queue states
- Surface the most expensive repeated query patterns using hash-based grouping with p50/p90/p99
  percentile latencies
- Track query success and failure trends over time and pinpoint warehouses with elevated error rates
- Detect long-running active queries in real time before they exhaust warehouse credits or block
  other workloads

## Dashboard Variables

| Variable        | Dimension                  | Default   | Description                                                                 |
|-----------------|----------------------------|-----------|-----------------------------------------------------------------------------|
| `$Account`      | `deployment.environment`   | `*` (all) | Filter to one or more Snowflake accounts                                    |
| `$Warehouse`    | `snowflake.warehouse.name` | `*` (all) | Filter by warehouse name                                                    |
| `$Database`     | `db.namespace`             | `*` (all) | Filter by database context                                                  |
| `$User`         | `db.user`                  | `*` (all) | Filter by Snowflake user                                                    |
| `$TopN`         | n/a                        | `10`      | Controls how many items ranked tiles display (5 / 10 / 20 / 50 / 100)       |
| `$SlowQueryMin` | n/a                        | `60`      | Minimum elapsed time in minutes for the long-running queries table (hidden) |

All filter variables support multi-select. `$Warehouse`, `$Database`, and `$User` cascade from
`$Account` — only values present in the selected account(s) are offered. `$TopN` and
`$SlowQueryMin` are hidden display-control variables.

![Snowflake Performance Explorer Overview](./img/performance-explorer-overview.png)

## Section 1 — Fleet Overview

Four KPI tiles provide an instant health snapshot for the selected timeframe and filters.

**Total Queries** — count of all query history log records matching the current filters.
Use this as a baseline when comparing error rate or elapsed time across time windows.

**Total Elapsed Time** — sum of `snowflake.time.total_elapsed` across all matching queries.
A sudden spike here indicates a burst of slow or blocked queries even if the count is stable.

**Error Rate** — percentage of queries where `snowflake.query.execution_status != "SUCCESS"`.
Includes `FAILED_WITH_ERROR` and `FAILED_WITH_INCIDENT` statuses. Threshold: investigate when
above 1–2% for production warehouses.

**Avg Execution Time** — mean of `snowflake.time.execution` (pure CPU/IO execution, excluding
compilation and queue wait). Compare against historical baselines to detect regression.

## Section 2 — Warehouse Performance

**Compilation vs execution vs queued time** (stacked area chart)
Plots the average of four time-phase metrics over the selected timeframe using `timeseries`:
`snowflake.time.compilation`, `snowflake.time.execution`, `snowflake.time.queued.overload`,
and `snowflake.time.queued.provisioning`. A growing queued-overload band signals warehouse
saturation; a growing compilation band may indicate plan cache pressure or schema changes.

**Time phase distribution by top $TopN warehouses** (categorical bar chart)
Aggregates the same four time phases per warehouse and ranks by total execution time.
Log-scale axis makes it easy to compare warehouses with very different workload volumes.
Adjust `$TopN` to show more or fewer warehouses.

## Section 3 — Grouped Query Analysis

Groups query history records by `snowflake.query.hash` to surface repeated query patterns
regardless of parameter values.

**Top $TopN query hashes by total elapsed time** (table)
Each row represents a unique query pattern. Columns:

| Column          | Description                                                           |
|-----------------|-----------------------------------------------------------------------|
| `exec_count`    | Number of times this pattern was executed                             |
| `p50`           | Median elapsed time across all executions                             |
| `p90`           | 90th-percentile elapsed time                                          |
| `p99`           | 99th-percentile elapsed time — reveals worst-case outliers            |
| `avg_elapsed`   | Mean elapsed time                                                     |
| `total_elapsed` | Sum of elapsed time — the primary sort key                            |
| `warehouse`     | Warehouse most commonly used for this pattern                         |
| `database`      | Database context                                                      |
| `query_hash`    | Hash identifier for the pattern                                       |
| `query_text`    | Representative query text (hidden by default — expand to view)        |

A large gap between p50 and p99 indicates high variance — investigate whether specific
parameter values or data skew cause occasional extreme runtimes.

**Top $TopN query hashes — avg elapsed time over time** (line chart)
Trends the average elapsed time for the top-N most expensive query patterns over the selected
timeframe. Use this to detect when a previously stable pattern starts degrading — a sign of
data growth, plan regression, or warehouse contention.

## Section 4 — Query Health

**Query success vs failure over time** (stacked area chart)
Splits query history into `success` and `failed` groups using `snowflake.query.execution_status`
and plots counts over time. Green = success, red = failed. A sudden increase in the failed band
warrants immediate investigation of `snowflake.error.code` and `snowflake.error.message` in the
Query Deep Dive dashboard.

**Error rate by warehouse** (categorical bar chart)
Ranks warehouses by error rate (failed / total × 100). Warehouses with consistently high error
rates may have misconfigured resource limits, permission issues, or problematic workloads.

## Section 5 — Long-Running Queries

Data in this section comes from the `active_queries` plugin, which reads
`INFORMATION_SCHEMA.QUERY_HISTORY` in real time — there is no ACCOUNT_USAGE ingestion lag.

**Active query summary per warehouse** (table)
Aggregates currently active queries by warehouse, showing count, fastest, slowest, and average
elapsed time. Use this to quickly identify which warehouse is under the most load right now.

**Long-running queries in progress** (table)
Lists individual queries that have been running longer than `$SlowQueryMin` minutes (default: 60).
Columns include start time, duration, user, warehouse, execution status, and a truncated query
preview. Sorted by duration descending. Increase `$SlowQueryMin` to narrow to the most extreme
outliers; decrease it to catch moderately slow queries earlier.

## Section 6 — Related Dashboards

Navigation tiles linking to complementary dashboards:

- **[Query Performance](../query-performance/)** — execution time trends by database, table, and
  user; top-N resource consumer donut charts; AI-powered anomaly detection
- **[Query Deep Dive](../query-deep-dive/)** — costly repeated queries by bytes scanned and spill,
  table performance degradation, query acceleration, external functions, cost attribution
- **[Costs Monitoring](../costs-monitoring/)** — credit usage, resource monitor quota utilization,
  warehouse costs, and slow query credit drain

## Required Plugins

- `query_history` — provides historical query telemetry from `ACCOUNT_USAGE.QUERY_HISTORY`
  (approximately 45-minute ingestion lag in Snowflake)
- `active_queries` — provides real-time active query data from `INFORMATION_SCHEMA` (no lag)

## DPO Theme

Performance

## Technical Notes

- **ACCOUNT_USAGE lag**: Sections 1–4 use `query_history` data which has a ~45-minute lag.
  Data for queries run in the last hour may not yet appear.
- **Real-time section**: Section 5 uses `active_queries` (INFORMATION_SCHEMA) — always current.
- **Percentile calculation**: p50/p90/p99 use `fetch logs | summarize percentile()` — not
  `timeseries` — because `percentile()` does not support iterative timeseries expressions.
- **Null-or-match filtering**: Optional dimension filters use `(isNull(dim) or in(dim, array($Var)))`
  to preserve records where the dimension is unpopulated while still allowing targeted filtering.
- **Default timeframe**: 24 hours with 5-minute auto-refresh.

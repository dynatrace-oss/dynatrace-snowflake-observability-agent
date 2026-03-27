# Budgets & FinOps Dashboard

## Overview

The **Budgets & FinOps Dashboard** provides a unified view of Snowflake budget
consumption, event-table ingest costs, warehouse sizing optimisation, and
warehouse load patterns. It is designed for FinOps practitioners, platform
engineers, and Snowflake account owners who need to track credit spend,
understand where costs originate, and right-size compute resources.

The dashboard covers four observable dimensions:

| Section                    | Observable Dimension                        | DSOA Plugins        |
|----------------------------|---------------------------------------------|---------------------|
| 1 — Budget Analysis        | Budget credit spend vs. limit               | `budgets`           |
| 2 — Event Table Ingest     | Event-table ingestion credits and bytes     | `event_usage`       |
| 3 — Warehouse Optimization | Warehouse sizing, compute %, cluster config | `resource_monitors` |
| 4 — Warehouse Load         | Running / queued / blocked query counts     | `warehouse_usage`   |

## Prerequisites

### Required DSOA Plugins

All four plugins must be enabled and collecting telemetry:

| Plugin              | Telemetry             | Default Schedule              | Notes                                                                      |
|---------------------|-----------------------|-------------------------------|----------------------------------------------------------------------------|
| `budgets`           | logs, metrics, events | `USING CRON 30 0 * * * UTC`   | Disabled by default — requires `is_enabled: true` and `is_disabled: false` |
| `event_usage`       | logs                  | `USING CRON 0 * * * * UTC`    | ACCOUNT_USAGE lag: 45–180 min                                              |
| `warehouse_usage`   | logs, metrics         | `USING CRON */30 * * * * UTC` | ACCOUNT_USAGE lag: 45–180 min                                              |
| `resource_monitors` | logs, metrics, events | `USING CRON */30 * * * * UTC` | Reads live `SHOW WAREHOUSES`                                               |

To enable all four plugins, add the following to your DSOA configuration file
(`conf/config-<env>.yml`):

```yaml
plugins:
  budgets:
    is_enabled: true
    is_disabled: false
    monitored_budgets:
      - "SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET"   # or your custom budget FQNs
  event_usage:
    is_enabled: true
  warehouse_usage:
    is_enabled: true
  resource_monitors:
    is_enabled: true
```

Then rebuild and redeploy:

```bash
./scripts/dev/build.sh
./scripts/deploy/deploy.sh <env> --scope=plugins,agents,config --options=skip_confirm
```

### Dynatrace Permissions

- `SNOWFLAKE.BUDGET_VIEWER` application role must be granted to the DSOA viewer
  role (`GRANT APPLICATION ROLE SNOWFLAKE.BUDGET_VIEWER TO ROLE <viewer_role>`).
- Each monitored budget must have its `VIEWER` instance role granted to the
  DSOA viewer role (handled automatically by `APP.P_GRANT_BUDGET_MONITORING()`
  in the `admin` deployment scope).

## Dashboard Variables

| Variable     | Type               | Description                                                                                           |
|--------------|--------------------|-------------------------------------------------------------------------------------------------------|
| `$Accounts`  | Multi-select query | Filters all tiles to specific `deployment.environment` values (Snowflake accounts monitored by DSOA). |
| `$Budget`    | Multi-select query | Filters Budget Analysis tiles to specific budget names.                                               |
| `$Warehouse` | Multi-select query | Filters Warehouse Optimization and Load tiles to specific warehouses.                                 |

All three variables support multi-select. Leave blank to show all values.

## Sections and Tiles

### Section 1 — Budget Analysis

Tracks credit spend against configured budget limits.

| Tile                   | Type         | Description                                                                 |
|------------------------|--------------|-----------------------------------------------------------------------------|
| Budget Spend (Credits) | Single Value | Total credits spent across all monitored budgets in the selected timeframe. |
| Budget Utilisation (%) | Single Value | Average credit spend as a percentage of the configured spending limit.      |
| Credit Spend by Budget | Bar Chart    | Side-by-side comparison of credits spent per budget.                        |
| Credit Spend Trend     | Line Chart   | Credit spend over time per budget — useful for spotting sudden cost spikes. |

**Data source**: `fetch logs` on `dsoa.run.context == "spendings"` and
`dsoa.run.context == "budgets"`.

### Section 2 — Event Table Ingest

Monitors ingestion credit consumption and data volume flowing through Snowflake
event tables.

| Tile                 | Type         | Description                                                             |
|----------------------|--------------|-------------------------------------------------------------------------|
| Event Ingest Credits | Single Value | Total credits used for event-table ingestion in the selected timeframe. |
| Event Ingest Bytes   | Single Value | Total bytes ingested into event tables.                                 |
| Ingest Credits Trend | Line Chart   | Credit consumption for event-table ingestion over time.                 |
| Ingest Bytes Trend   | Line Chart   | Byte ingestion volume over time — correlated with credits.              |

**Data source**: `fetch logs` on `dsoa.run.context == "event_usage"`.

**Note**: `ACCOUNT_USAGE.EVENT_USAGE_HISTORY` has a 45–180 minute ingestion
lag. Tiles in this section will not show data immediately after the first DSOA
run — allow up to 3 hours for initial population.

### Section 3 — Warehouse Optimization

Provides per-warehouse sizing and compute utilisation metrics to support
right-sizing decisions.

| Tile                   | Type         | Description                                                                                            |
|------------------------|--------------|--------------------------------------------------------------------------------------------------------|
| Unmonitored Warehouses | Single Value | Count of warehouses with no resource monitor assigned — a FinOps risk indicator.                       |
| Compute Available (%)  | Line Chart   | Percentage of warehouse compute actively available vs. provisioning or quiescing.                      |
| Cluster Count Trend    | Line Chart   | Started cluster count over time for multi-cluster warehouses.                                          |
| Warehouse Sizing Table | Data Table   | Last-seen per-warehouse details: size, type, auto-suspend, min/max clusters, resource monitor, budget. |

**Data source**: `fetch logs` on `dsoa.run.context == "warehouses"` and
`timeseries` on `snowflake.compute.available`, `snowflake.warehouse.clusters.started`.

### Section 4 — Warehouse Load

Shows query execution load on each warehouse — running, queued, and blocked
query counts.

| Tile            | Type       | Description                                                                                        |
|-----------------|------------|----------------------------------------------------------------------------------------------------|
| Running Queries | Line Chart | Concurrent running queries per warehouse over time.                                                |
| Queued Queries  | Line Chart | Queued query count per warehouse — elevated values indicate warehouse saturation.                  |
| Blocked Queries | Line Chart | Blocked query count — may indicate transaction contention.                                         |
| Load Heatmap    | Honeycomb  | Per-warehouse colour-coded load summary (running + queued + blocked) for at-a-glance fleet health. |

**Data source**: `timeseries` on `snowflake.queries.running`,
`snowflake.queries.queued`, `snowflake.queries.blocked`.

**Note**: `ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY` has a 45–180 minute
ingestion lag. The load tiles reflect a delayed view of warehouse activity.

## Default Settings

| Setting               | Value                                       |
|-----------------------|---------------------------------------------|
| Default time range    | 7 days                                      |
| Auto-refresh interval | 5 minutes                                   |
| Default variables     | All accounts / all budgets / all warehouses |

## Related Dashboards

- [Costs Monitoring](../costs-monitoring/readme.md) — credit quota utilisation
  and resource monitor alerts (overlaps with Section 3 of this dashboard on
  warehouse sizing; this dashboard focuses on FinOps spend tracking and budgets)
- [DSOA Self-Monitoring](../self-monitoring/readme.md) — plugin execution health

## Related Documentation

- [`budgets` plugin](../../PLUGINS.md)
- [`event_usage` plugin](../../PLUGINS.md)
- [`warehouse_usage` plugin](../../PLUGINS.md)
- [`resource_monitors` plugin](../../PLUGINS.md)
- [Telemetry Semantics](../../SEMANTICS.md) — field definitions for all metrics
  used in this dashboard

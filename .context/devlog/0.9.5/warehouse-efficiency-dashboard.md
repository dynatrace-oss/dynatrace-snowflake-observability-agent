# Dashboard: Warehouse Efficiency Section in Costs Monitoring

- **Purpose**: Surface idle-time waste and auto-suspend misconfiguration in the existing Costs Monitoring dashboard.
  Customers waste 20–40% of warehouse spend on idle time and suboptimal auto-suspend timeouts; these tiles make
  that waste visible and actionable without requiring any agent code changes.
- **Approach**: Dashboard-only change. Eight new tiles (keys `"22"`–`"29"`) appended after the existing Resource
  Monitor Health section. One new variable `$Idle_Threshold_Pct` (text, default `"50"`) added for threshold coloring.
  Dashboard version bumped from 20 to 21.
- **Data sources** (all pre-existing telemetry):
  - `snowflake.load.running` metric (warehouse\_usage plugin, `warehouse_usage_load` context) — 5-minute load
    history intervals. `avg ≤ 0` used as idle indicator.
  - `snowflake.warehouse.clusters.started/max/min` metrics (resource\_monitors plugin) — multi-cluster utilization.
  - `snowflake.warehouse.is_auto_suspend`, `snowflake.warehouse.size`, `snowflake.warehouse.type`,
    `snowflake.warehouse.scaling_policy` attributes (resource\_monitors plugin) — configuration audit.
  - `snowflake.warehouse.event.name` / `snowflake.warehouse.event.state` dimensions (warehouse\_usage plugin) —
    RESUME\_WAREHOUSE / SUSPEND\_WAREHOUSE events for thrashing detection.
- **DQL patterns**:
  - Idle ratio (tiles 23, 26): `timeseries` over `snowflake.load.running` at 5m interval → `arrayFilter(running[], {it <= 0.0})` to count idle intervals → `idle_pct = 100 * idle_intervals / total_intervals`.
  - Credit waste (tile 26): `idle_hours = idle_intervals * 5 / 60` joined with inline `lookup` table for credits/hour by warehouse size (XS=1, S=2, M=4, L=8, XL=16, 2XL=32, 3XL=64, 4XL=128). Same lookup pattern as tile `"14"`.
  - Suggested timeout heuristic: `idle_pct > 50% → "60s"`, `> 20% → "300s"`, else `"Keep current"`. 60 s is the Snowflake minimum billing floor.
  - Multi-cluster (tiles 27, 28): `fetch events` from resource\_monitors plugin filtered to `clusters.max > 1`; `makeTimeseries` for trend, `summarize` for table.
  - Thrashing (tile 29): `fetch logs` from warehouse\_usage plugin, filter `event.state == "STARTED"` to count only initiating events (not completions), `makeTimeseries count()` by event name + warehouse.
  - All tiles use `dsoa.run.plugin` (not `dsoa.run.context`) for plugin-level filtering, consistent with multi-context plugins.
  - Serverless warehouses excluded via `filterOut snowflake.warehouse.type == "SNOWPARK-OPTIMIZED"` in tiles 25 and 26.
- **Variable filters**: All new tiles apply the standard three-filter pattern: `in(deployment.environment, array($Accounts))` + `iAny(startsWith(..., concat(array($Prefix)[], "_")))` + `in(snowflake.warehouse.name, array($Warehouses))`.
- **Layout**: New section occupies y=78–107 (rows 78–107). Tiles 23/24 share a row (idle table + trend chart). Tiles 27/28 share a row (multi-cluster trend + idle clusters table).
- **Known limitations**:
  - `snowflake.load.running = 0` means no active queries but the warehouse may still be in a provisioning or quiescing state; idle estimate is conservative (may slightly overcount).
  - Credit waste estimates assume uniform 5-minute billing intervals; actual billing uses 60-second minimum floor.
  - `$Idle_Threshold_Pct` threshold in tile 23 uses a string variable in a numeric comparator — verify rendering on tenant (DQL may require `toDouble($Idle_Threshold_Pct)`).
- **Files changed**: `docs/dashboards/costs-monitoring/costs-monitoring.yml`, `docs/dashboards/costs-monitoring/readme.md`, `docs/CHANGELOG.md`.

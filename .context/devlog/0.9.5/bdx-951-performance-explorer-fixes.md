# BDX-951 — Snowflake Performance Explorer Dashboard Fixes

**Branch:** `fix/0.9.5/bdx-951-performance-explorer-fixes`
**PR:** #118 (post-merge fixes)
**Date:** 2026-05-19

## Issues Found and Fixed

### Issue 1 — Tile 6: Invalid `timeseries` query for log attributes (CRITICAL)

**File:** `docs/dashboards/performance-explorer/performance-explorer.yml`, tile `"6"`

**Problem:** The tile used the `timeseries` DQL command with `snowflake.time.compilation`,
`snowflake.time.execution`, `snowflake.time.queued.overload`, and `snowflake.time.queued.provisioning`
as if they were pre-ingested metric keys. These fields are **log attributes** (defined under
`attributes:` in `query_history.config/instruments-def.yml`), not metric keys. The `timeseries`
command only works with actual Dynatrace metric keys. This caused the tile to return no data.

Additional sub-problems in the same tile:
- `union: true` is not a valid parameter for the `timeseries` command.
- Post-pipe `| filter dsoa.run.plugin == "query_history"` after `timeseries` is invalid —
  `dsoa.run.plugin` is a log attribute, not a metric dimension, so it cannot be filtered
  after a `timeseries` step.
- Post-pipe `| filter (isNull(db.namespace) or ...)` and `| filter (isNull(db.user) or ...)`
  after `timeseries` are similarly invalid for the same reason.
- Field names with spaces (`queued overload`, `queued provisioning`) in `fieldMapping` and
  `unitsOverrides` were inconsistent with the backtick-quoted DQL aliases.

**Fix:** Rewrote the tile query using `fetch logs | makeTimeseries` — the correct pattern for
building a time-bucketed series from log attributes. All filters are applied before `makeTimeseries`.
Field names changed to underscore-separated (`queued_overload`, `queued_provisioning`) for
consistency across DQL, `fieldMapping`, `dataMapping`, and `unitsOverrides`.

### Issue 2 — Tile 16: Legacy `coalesce(db.statement, db.query.text)` (LOW)

**File:** `docs/dashboards/performance-explorer/performance-explorer.yml`, tile `"16"`

**Problem:** The `Query` field used `coalesce(db.statement, db.query.text)`. Per dashboard
skill rule 22, `db.statement` is a legacy field from early DSOA versions. All current agents
emit `db.query.text` exclusively. The coalesce was unnecessary and added noise.

**Fix:** Replaced with `db.query.text` directly.

## Issues Investigated but Not Changed

- **Variable queries**: The `Account`, `Warehouse`, `Database`, `User` variables use `dedup` +
  `sort` pattern (correct per skill rule 21). No `defaultValue: "*"` set (correct). No
  `dsoa.run.plugin` filter in the `Account` variable (correct per skill rule 19 — broad filter
  ensures the variable populates as long as any Snowflake data exists).
- **Cross-link tile IDs**: Verified all three navigation tile IDs match deployed dashboards:
  - Query Performance: `f245f73a-35f5-4298-8158-2a8aa4611a23` ✅
  - Query Deep Dive: `9dbac33a-25ba-4192-b748-c8b6fe561c3b` ✅
  - Costs Monitoring: `e446e588-b917-4a63-867c-643ca783c79e` ✅
- **DQL field names**: All fields (`snowflake.query.hash`, `snowflake.time.*`, `db.namespace`,
  `db.user`, `db.query.text`, `snowflake.warehouse.name`, `snowflake.query.execution_status`)
  confirmed present in `instruments-def.yml` for both `query_history` and `active_queries`.
- **`$SlowQueryMin` usage**: Tile 16 uses `toLong($SlowQueryMin)` correctly in numeric comparison.
- **`unitsOverrides`**: All time fields have proper `unitCategory: time, baseUnit: millisecond` overrides.
- **`davis` block structure**: All data tiles use `enabled: false` + `davisVisualization`, all
  markdown tiles use `componentState`. No cross-contamination.

## Validation

- `yamllint`: clean
- `pylint src/dtagent/`: 10.00/10
- YAML → JSON conversion: OK (21 tiles)
- `deploy_dt_assets.sh --dry-run`: performance-explorer passes without errors

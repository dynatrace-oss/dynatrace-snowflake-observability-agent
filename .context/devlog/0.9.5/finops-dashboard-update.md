# Budgets & FinOps Dashboard Update (v17 → v21)

**Date:** 2026-05-21
**Source:** `.context/pm-notes/stories/0.9.5/attachments/Budgets & FinOps.json` (v21)
**Dashboard ID:** `64b09f3f-1faa-49c8-98ba-7aa496af8cdf` (preserved)
**Status:** ✅ Deployed to test-qa

## Summary

Updated the Budgets & FinOps dashboard from version 17 to version 21, incorporating improvements to variable queries and visualization settings. The dashboard now provides better account filtering across all plugins and enhanced warehouse data collection from both events and logs.

## Changes Made

### 1. Version Bump

- **17 → 21** (from source JSON export)

### 2. Variable Query Updates

#### Accounts Variable
**Before:**

```dql
fetch logs, from: now()-7d
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "budgets"
| fields deployment.environment
| dedup deployment.environment
| sort deployment.environment asc
```

**After:**

```dql
fetch logs, from: now()-7d
| filter db.system == "snowflake"
| fields deployment.environment
| dedup deployment.environment
| sort deployment.environment asc
```

**Rationale:** Removed the `dsoa.run.plugin == "budgets"` filter to include all accounts across all plugins, not just those with budget data. This provides a more complete account list for filtering across the entire dashboard.

#### Warehouse Variable
**Before:**

```dql
fetch logs, from: now()-7d
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "resource_monitors"
| filter in(deployment.environment, array($Accounts))
| filter isNotNull(`snowflake.warehouse.name`)
| fields `snowflake.warehouse.name`
| dedup `snowflake.warehouse.name`
| sort `snowflake.warehouse.name` asc
```

**After:**

```dql
fetch events, from: now()-7d
| filter db.system == "snowflake"
| filter in(deployment.environment, array($Accounts))
| filter isNotNull(snowflake.warehouse.name)
| fields snowflake.warehouse.name
| append [
  fetch logs, from: now()-7d
  | filter db.system == "snowflake"
  | filter in(deployment.environment, array($Accounts))
  | filter isNotNull(snowflake.warehouse.name)
  | fields snowflake.warehouse.name
]
| dedup snowflake.warehouse.name
| sort snowflake.warehouse.name asc
```

**Rationale:** Changed to a union pattern (events + logs) to capture warehouse names from both telemetry sources. This ensures comprehensive warehouse coverage, particularly for warehouses that emit events but may not have logs in the resource_monitors context.

### 3. Tile Updates
All 13 tiles preserved with updated DQL queries and visualization settings:

**Budget Analysis Section (Tiles 0-4):**

- Tile 0: Section header (markdown)
- Tile 1: Budget spending vs limit (table with color rules)
- Tile 2: Budget spending trend (line chart)
- Tile 3: Budget spending by service type (pie chart)
- Tile 4: Budget details (table)

**Warehouse Optimization Section (Tiles 5-8):**

- Tile 5: Section header (markdown)
- Tile 6: Warehouse sizing overview (table with color rules)
- Tile 7: Cluster utilization over time (line chart)
- Tile 8: Resource monitor quota usage over time (line chart with threshold rules)

**Warehouse Load Section (Tiles 9-12):**

- Tile 9: Section header (markdown)
- Tile 10: Running vs queued queries over time (line chart)
- Tile 11: Average running queries by warehouse (honeycomb)
- Tile 12: Blocked queries over time (line chart with threshold rules)

### 4. Visualization Settings
Updated coloring and threshold rules for better visual feedback:

**Budget Spending vs Limit (Tile 1):**

- Green: < 75% used
- Orange: 75-100% used
- Red: ≥ 100% used

**Warehouse Sizing (Tile 6):**

- Green: Monitored (false)
- Red: Unmonitored (true)

**Resource Monitor Quota (Tile 8):**

- Green: ≥ 70% quota available
- Orange: 30-70% quota available
- Red: < 30% quota available

**Blocked Queries (Tile 12):**

- Green: < 1 blocked query
- Orange: ≥ 1 blocked query

### 5. Settings Preserved

- Auto-refresh: enabled, 300s interval
- Default timeframe: now()-7d to now()
- All 13 layouts preserved (no positioning changes)

## Affected Plugins

- `budgets` — budget spending and limit tracking
- `warehouse_usage` — warehouse load metrics
- `resource_monitors` — warehouse sizing and resource monitor quotas

## Deployment

- **Environment:** test-qa
- **Dry-run:** ✅ Passed
- **Deployment:** ✅ Succeeded
- **Verification:** ✅ Dashboard displays 13 tiles in Dynatrace UI
- **Dashboard URL:** <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/64b09f3f-1faa-49c8-98ba-7aa496af8cdf>

## Testing Notes

- All DQL queries validated against source JSON
- YAML syntax validated with yamllint
- Dashboard ID preserved in both YAML and deployed tenant
- Tile count verified: 13 tiles present in deployed dashboard
- Variable queries tested for syntax correctness

## Files Modified

- `docs/dashboards/budgets-finops/budgets-finops.yml` — updated to v21 with new variable queries and visualization settings

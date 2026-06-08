# BDX-951 — Snowflake Performance Explorer Dashboard Fixes

**Branch:** `fix/0.9.5/bdx-951-performance-explorer-fixes`
**PR:** #118 (post-merge fixes)
**Date:** 2026-05-19
**Source of truth:** `.context/pm-notes/stories/0.9.5/attachments/Snowflake Performance Explorer.json`
(working dashboard exported from Dynatrace UI after human QA and manual corrections)

## Background

During 0.9.5 QA (D4 visual check), the Snowflake Performance Explorer dashboard was found to have
multiple issues. The human tester manually corrected the dashboard in the Dynatrace UI and exported
the fixed JSON. This devlog documents what was wrong and what the correct state is, derived by
diffing the original YAML against the exported JSON.

The initial AI-generated fix attempt (commit `4daeb85`) misdiagnosed the root cause of tile 6 and
applied incorrect corrections. Those were reverted and the correct fixes were applied by syncing
from the exported JSON.

---

## Issues Fixed

### Issue 1 — Variable queries were shallow and did not match data model (CRITICAL)

**Variables affected:** `Warehouse`, `Database`, `User`

**Problem:** The original variable queries were minimal — they only checked `isNotNull(field)` with
no qualification against actual `query_history` data shape. This caused the dropdowns to populate
with values from all log records (including agent self-monitoring, active_queries, etc.) rather than
records relevant to the performance explorer context. In practice, the dropdowns either showed
spurious values or appeared empty because the filters in the tiles used `db.namespace` but the
variable emitted raw `db.namespace` values which could be null or from unrelated plugins.

**Fix — Warehouse variable:**
Added multi-condition filter requiring `coalesce(db.name, db.namespace)` and
`coalesce(db.statement, db.query.text)` and `snowflake.time.execution` to be non-null — ensuring
the warehouse list only contains warehouses that have real `query_history` records with execution data.

**Fix — Database variable:**
Replaced `filter isNotNull(db.namespace) | fields db.namespace` with a richer filter and
`fields db_name = coalesce(db.name, db.namespace)` — matching the alias used in tile DQL queries
and ensuring only databases with real query data appear.

**Fix — User variable:**
Added `$Database` dependency (`filter in(db_name, array($Database))`) so the user list cascades
correctly from the selected database. Added the same multi-condition filter for data quality.

### Issue 2 — TopN variable used `csv` type instead of `text` (MEDIUM)

**Problem:** `TopN` was defined as `type: csv` with `input: "5,10,20,50,100"`. In the Dynatrace
dashboard variables UI, `csv` type renders as a multi-select picker from the listed values.
The `text` type renders as a free-entry text field. The exported fixed JSON uses `type: text`
with `defaultValue: 10` — a simple numeric input consistent with `SlowQueryMin`.

**Fix:** Changed `type: csv` → `type: text`, removed `input` and `multiple` fields, kept
`defaultValue: "10"`.

### Issue 3 — Tile 6: `timeseries` with metric names is correct — `makeTimeseries` was wrong (CRITICAL)

**Problem with the earlier AI fix (`4daeb85`):** The previous fix replaced the `timeseries` command
with `fetch logs | makeTimeseries`. This was incorrect. `snowflake.time.compilation`,
`snowflake.time.execution`, `snowflake.time.queued.overload`, and `snowflake.time.queued.provisioning`
**are** Dynatrace ingested metrics (emitted by the `query_history` plugin via `OtelManager` metrics
exporter) — not raw log attributes. The `timeseries` DQL command is the correct tool here.

**Correct fix (from exported JSON):** The tile uses:
```dql
timeseries
  {
  compilation = avg(snowflake.time.compilation),
  execution = avg(snowflake.time.execution),
  `queued overload` = avg(snowflake.time.queued.overload),
  `queued provisioning` = avg(snowflake.time.queued.provisioning)
  }
, filter: {
  db.system == "snowflake" and dsoa.run.plugin == "query_history"
  and in(deployment.environment, array($Account))
  and in(snowflake.warehouse.name, array($Warehouse))
  and isNull(db.namespace) or in(db.namespace, array($Database))
  and (isNull(db.user) or in(db.user, array($User)))
}
, union: true
```

The `filter:` clause on `timeseries` filters metric data points by dimension values. The `union: true`
parameter combines results across multiple matching metric series. Field names use backtick-quoted
spaces (`queued overload`, `queued provisioning`) consistently across DQL, `fieldMapping`,
`dataMapping`, and `unitsOverrides`.

### Issue 4 — Tile 6: `fieldMapping`/`dataMapping`/`unitsOverrides` used underscores (MEDIUM)

**Problem with the earlier AI fix:** After switching to `makeTimeseries`, field names were changed
to `queued_overload` / `queued_provisioning` (underscores). The correct Dynatrace metric dimension
names use spaces: `queued overload`, `queued provisioning` — as they appear in the raw metric key
suffixes and as the UI renders them.

**Fix:** Restored backtick-quoted space names in DQL and matching string keys in all settings blocks.

---

## What Was NOT Changed (Verified Correct)

- **Tile 16 `db.query.text`**: The earlier AI fix removed `coalesce(db.statement, db.query.text)`.
  The exported JSON confirms `db.query.text` only is correct for this tile.
- **Cross-link tile IDs**: All three navigation tiles confirmed correct against deployed dashboards:
  - Query Performance: `f245f73a-35f5-4298-8158-2a8aa4611a23` ✅
  - Query Deep Dive: `9dbac33a-25ba-4192-b748-c8b6fe561c3b` ✅
  - Costs Monitoring: `e446e588-b917-4a63-867c-643ca783c79e` ✅
- **`unitsOverrides`**: All time fields have correct `unitCategory: time, baseUnit: millisecond`.
- **All other tiles (1–5, 7–20)**: No changes — DQL and settings confirmed matching the exported JSON.

---

## Lesson Learned

`timeseries` in DQL operates on **pre-ingested Dynatrace metrics**, not on log record attributes.
DSOA emits both metrics (via `OtelManager` metrics exporter → `snowflake.time.*` metric keys) and
logs (via OTLP logs exporter → `snowflake.time.*` as log record attributes). The field names are
identical but the DQL command to use differs:

- Use `timeseries avg(snowflake.time.compilation)` → for metric data
- Use `fetch logs | makeTimeseries avg(toLong(snowflake.time.compilation))` → for log attribute data

Tile 6 correctly uses `timeseries` because these are metrics. The AI fix incorrectly assumed they
were log attributes and switched to `makeTimeseries`.

---

## Validation

- `yamllint`: clean (no output)
- YAML → JSON conversion: OK (6 variables, 21 tiles)
- `deploy_dt_assets.sh --dry-run`: authentication not available in session (expected); YAML
  conversion step passes, which is the only automated gate available without live credentials

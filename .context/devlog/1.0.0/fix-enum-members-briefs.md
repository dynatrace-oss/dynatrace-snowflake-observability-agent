# Fix: enum member values and briefs in instruments-def.yml files

**Date:** 2026-06-17
**Branch:** `feat/1.0.0/fix-enum-members-briefs`
**Affected files:** 6 plugin config files

---

## Summary

IA review and live Dynatrace data audit (`dtctl query`) revealed two categories of issues across
DSOA `instruments-def.yml` enum definitions:

1. **Fabricated enum values** — values invented and never present in live Snowflake data.
2. **Tautological briefs** — `brief:` fields that simply restate the value name without adding meaning.

Both categories were fixed across all affected plugins.

---

## Changes by file

### `query_history.config/instruments-def.yml`

- **`dimensions.snowflake.query.execution_status`** (Change 1): Replaced 3-member list
  (including fabricated `INCIDENT_QUEUE`) with 7 real values observed in live data:
  `SUCCESS`, `FAIL`, `FAILED_WITH_ERROR`, `INCIDENT`, `QUEUED`, `RESUMING_WAREHOUSE`, `RUNNING`.
- **`attributes.snowflake.object.type`** (Change 8): Brief improvements — all 5 members.
- **`attributes.snowflake.object.ddl.operation`** (Change 9): Brief improvements — all 5 members.
- **`attributes.snowflake.warehouse.size`** (Change 10): Brief improvements with credit/hour info
  and X-SMALL default note — all 10 members.
- **`attributes.snowflake.warehouse.type`** (Change 11): SNOWPARK_OPTIMIZED brief updated to
  include high-memory node specs and use cases.
- **`dimensions.db.operation.name`** (Change 12): Brief improvements — 11 of 14 members
  (CALL, PUT, GET unchanged).
- **`dimensions.snowflake.user.type`** (Change 13): Brief improvements — 3 of 4 members
  (PERSON unchanged).

### `resource_monitors.config/instruments-def.yml`

- **`attributes.snowflake.warehouse.execution_state`** (Change 2): Replaced 5-member list —
  removed `RUNNING` (not in live data), added `RESIZING` (Snowflake-documented), reordered
  to lifecycle sequence, improved all briefs.
- **`attributes.snowflake.warehouse.size`** (Change 10): Same brief improvements as query_history.
- **`attributes.snowflake.warehouse.type`** (Change 11): Same SNOWPARK_OPTIMIZED improvement.
- **`attributes.snowflake.resource_monitor.frequency`** (Change 14): Brief improvements — 4 of 5
  members (NEVER unchanged).
- **`attributes.snowflake.resource_monitor.level`** (Change 15): ACCOUNT brief updated.
- **`attributes.snowflake.warehouse.scaling_policy`** (Change 16): STANDARD brief updated.

### `warehouse_usage.config/instruments-def.yml`

- **`dimensions.snowflake.warehouse.event.state`** (Change 3): Removed fabricated `FAILED` member,
  improved STARTED and COMPLETED briefs.
- **`dimensions.snowflake.warehouse.event.name`** (Change 4): Replaced all 4 fabricated values
  (`WAREHOUSE_START`, `WAREHOUSE_SUSPEND`, `WAREHOUSE_RESUME`, `RESIZE_WAREHOUSE`) with 8 real
  values from live data: `ALTER_WAREHOUSE`, `CREATE_WAREHOUSE`, `DROP_WAREHOUSE`, `RESUME_CLUSTER`,
  `RESUME_WAREHOUSE`, `SUSPEND_CLUSTER`, `SUSPEND_WAREHOUSE`, `WAREHOUSE_CONSISTENT`.
- **`attributes.snowflake.warehouse.event.reason`** (Change 5): Replaced all 4 fabricated values
  (`USER_REQUEST`, `AUTO_SUSPEND`, `AUTO_RESUME`, `SCHEDULER`) with 5 real values from live data:
  `RESOURCE_MONITOR_SUSPEND`, `WAREHOUSE_AUTORESUME`, `WAREHOUSE_AUTOSUSPEND`, `WAREHOUSE_RESUME`,
  `WAREHOUSE_SUSPEND`.
- **`attributes.snowflake.warehouse.size`** (Change 10): Same brief improvements.

### `data_volume.config/instruments-def.yml`

- **`dimensions.snowflake.table.type`** (Change 6): Brief improvements — 4 of 5 members
  (TEMPORARY TABLE unchanged): BASE TABLE, EXTERNAL TABLE, VIEW, MATERIALIZED VIEW.

### `metering.config/instruments-def.yml`

- **`dimensions.snowflake.service.type`** (Change 7): Brief improvements — 9 of 11 members
  (WAREHOUSE_METERING, CLOUD_SERVICES unchanged): AUTO_CLUSTERING, PIPE, SERVERLESS_TASK,
  TELEMETRY_DATA_INGEST, REPLICATION, MATERIALIZED_VIEW, SEARCH_OPTIMIZATION, QUERY_ACCELERATION,
  STORAGE.

### `users.config/instruments-def.yml`

- **`attributes.snowflake.user.type`** (Change 13): Same brief improvements as query_history.

---

## Enum member delta

| Plugin            | Field                                | Added | Removed | Updated (brief only) |
|-------------------|--------------------------------------|-------|---------|----------------------|
| query_history     | snowflake.query.execution_status     | 5     | 1       | 0                    |
| query_history     | snowflake.object.type                | 0     | 0       | 5                    |
| query_history     | snowflake.object.ddl.operation       | 0     | 0       | 5                    |
| query_history     | snowflake.warehouse.size             | 0     | 0       | 10                   |
| query_history     | snowflake.warehouse.type             | 0     | 0       | 1                    |
| query_history     | db.operation.name                    | 0     | 0       | 11                   |
| query_history     | snowflake.user.type                  | 0     | 0       | 3                    |
| resource_monitors | snowflake.warehouse.execution_state  | 1     | 1       | 4                    |
| resource_monitors | snowflake.warehouse.size             | 0     | 0       | 10                   |
| resource_monitors | snowflake.warehouse.type             | 0     | 0       | 1                    |
| resource_monitors | snowflake.resource_monitor.frequency | 0     | 0       | 4                    |
| resource_monitors | snowflake.resource_monitor.level     | 0     | 0       | 1                    |
| resource_monitors | snowflake.warehouse.scaling_policy   | 0     | 0       | 1                    |
| warehouse_usage   | snowflake.warehouse.event.state      | 0     | 1       | 2                    |
| warehouse_usage   | snowflake.warehouse.event.name       | 8     | 4       | 0                    |
| warehouse_usage   | snowflake.warehouse.event.reason     | 5     | 4       | 0                    |
| warehouse_usage   | snowflake.warehouse.size             | 0     | 0       | 10                   |
| data_volume       | snowflake.table.type                 | 0     | 0       | 4                    |
| metering          | snowflake.service.type               | 0     | 0       | 9                    |
| users             | snowflake.user.type                  | 0     | 0       | 3                    |
| **TOTAL**         |                                      | **19**| **11**  | **84**               |

Net member count change: +8 members added (live values not previously present in definitions).

---

## Technical notes

### YAML line-length compliance

All new `brief:` text is long-form. The 140-char yamllint limit required using `>-` folded block
scalars for multi-sentence briefs. The folded scalar collapses internal newlines to spaces, so the
parsed string values remain single-line — verified by Python `yaml.safe_load()`.

Colon-containing brief text (e.g. `Prioritises query throughput: ...`) is wrapped in `>-` rather
than double-quoted to avoid quoting complexity while staying lint-clean.

### Intentionally out of scope

- `snowflake.warehouse.size`, `snowflake.warehouse.type`, `snowflake.user.type` are duplicated
  across multiple plugin files by design — each `instruments-def.yml` is plugin-scoped. Deduplication
  is handled at the semdict export output layer via global field refs, not at the source layer.
- `docs/CHANGELOG.md` not updated — this is internal metadata quality improvement, not a
  user-visible behaviour change.
- Dashboard YAML not modified — dashboards already use the correct live values.

---

## Validation

- `make lint`: passed (`pylint 10.00/10`)
- `yamllint`: clean (no errors)
- `yaml.safe_load()`: all 6 files parse without error
- `>-` block scalar check: no embedded newlines in parsed brief strings
- `.venv/bin/pytest test/plugins/test_{query_history,resource_monitors,warehouse_usage,data_volume,metering,users}.py`: 66 passed, 13 skipped
- `.venv/bin/pytest test/core/test_export_semantics.py test/core/test_documentation.py test/core/test_config_structure.py`: 92 passed
- `python src/build/export_semantics.py --verbose`: "✓ Export complete"
- `./scripts/dev/build.sh`: "Building Dynatrace Snowflake Observability Agent done"
- `./scripts/dev/build_docs.sh`: completed successfully

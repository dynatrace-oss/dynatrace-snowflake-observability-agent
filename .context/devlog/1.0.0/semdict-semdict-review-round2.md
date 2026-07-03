# BIZOBS-151: Semantic Dictionary Export — Review Round 2 Fixes

**Date:** 2026-06-19
**Branch:** `feat/1.0.0/bizobs-151-semantic-export`
**Scope:** Addresses all remaining TODO items from the IA review checklist appended to
`BIZOBS-151-dsoa-semdict-export-review.md` (Revision 2).

---

## Context

After the initial IA review produced 33 regression tests and resolved all 5 BLOCKERs,
the PO added 6 open items to the review document's TODO section. This devlog covers
their resolution in delivery order.

---

## TASK 5 (P5) — Numeric metric examples normalized

**Problem:** 145 metric entries had `__example: "120000"` (string) instead of `__example: 120000`
(numeric). The export's `_coerce_metric_example()` already handles the coercion, making this a
source hygiene issue only — but it misleads contributors about expected YAML types.

**Fix:** Python regex pass over all 21 `instruments-def.yml` files, replacing
`__example: "<number>"` → `__example: <number>` in all `metrics:` sections. 124 instances
fixed across 17 files; core instruments-def fixed separately (1 instance).

**Test added:** `TestMetricExamplesAreNumeric::test_metric_examples_are_numeric_types`

---

## TASK 6 (P6) — `ad.*` fields documented at core level

**Problem:** The 4 `ad.*` fields used by all 10 DSOA anomaly-detection workflows
(`ad.source`, `ad.source_metric`, `ad.direction`, `ad.category`) were either
undocumented or only partially documented (login_history `ad.source` with wrong description).

**Decision (as requested by PO):** Core-level definition, since all workflows share these fields
and they are not owned by any single Python plugin.

**Grail context:** These are Dynatrace Classic Environment V2 event properties emitted by
workflow JavaScript tasks via `eventsClient.createEvent()`. They are NOT OTLP log/span attributes
(except `ad.source` in `login_history.py` which uses value `"snowflake_security"`).

**Fix:**
- Added 4 fields to `src/dtagent.conf/instruments-def.yml` `attributes:` section.
- `ad.direction`: closed enum (`above`, `below`).
- `ad.category`: open enum with 7 members (login, session, query_count, data_scan, volume_drop,
  unavailable, disappeared).
- Updated `login_history.config/instruments-def.yml` `ad.source` description to cross-reference
  core definition.
- Fixed 4 stale entries in `test/workflows/test_workflow_execution.py::_WORKFLOW_AD_SOURCE`:
  - `dsoa.credits_exhaustion_prediction` → `dsoa.credits_exhaustion`
  - `dsoa.query_slowdown_detection` → `dsoa.query_slowdown`
  - `dsoa.security_anomaly_detection` → `dsoa.security_anomaly`
  - `dsoa.shares_broken` → `dsoa.shares_broken_detection`

**Tests added:** `TestAdFieldsAtCoreLevel` (4 tests: field existence, direction enum, category
enum, semdict annotation).

**Orphan count:** +4 (ad.* workflow fields are signal fields without a metric model reference,
which is expected for event-only workflow properties). `MAX_ORPHAN_SIGNAL_FIELDS` updated 9→13.

---

## TASK 4 (P4) — Interface `ref:` contextual notes (C2)

**Problem:** All 10 `ref:` entries in `i.dsoa_resource` lacked `note:` context explaining DSOA
usage (e.g. "Always 'snowflake' for all DSOA telemetry."). This was an outstanding IA suggestion.

**Fix:**
- Added `__interface_note` annotation to all 10 resource dimensions/attributes in
  `src/dtagent.conf/instruments-def.yml`.
- Updated `_build_interfaces_yaml(all_entries=None)` in `export_semantics.py`: added
  `_ref_entry()` inner function that looks up `__interface_note` from `all_entries` and adds it
  as `note:` on the ref dict if present. The method signature is backward-compatible (`all_entries`
  defaults to `None`; bare `{"ref": key}` is emitted when no note is found).
- Both call sites in `export()` (line 1436-1437) updated to pass `all_entries`.

**Test added:** `TestInterfaceRefNotes::test_all_resource_interface_refs_have_notes`

---

## TASK 3 (P3) — JSON/array field types + timestamp Grail reality

**Live verification (dtctl 0.25.2, 2026-06-19):**

| Field | dtctl result | Grail type confirmed |
|---|---|---|
| `snowflake.query.operator.stats` | `{"input_rows":2527,...}` (string) | **string** |
| `snowflake.query.operator.time` | `{"overall_percentage":0.0}` (string) | **string** |
| `snowflake.query.operator.parent_ids` | `["328"]` (string array) | **string[]** |
| `snowflake.table.dynamic.refresh.end` | no data (30d) | assumed string |
| `snowflake.warehouse.created_on` | no data (30d) | assumed string |
| All other JSON/array/timestamp fields | no data (30d) | assumed per IA guidance |

**Fields with no data in 30 days (assumed types applied as specified by IA):**
- JSON objects: `snowflake.query.operator.attributes`, `snowflake.query.accel_est.estimated_query_times`,
  `snowflake.object.ddl.properties`, `snowflake.object.ddl.modified` → `string`
- String arrays (no data): `snowflake.table.dynamic.graph.alter_trigger`,
  `snowflake.table.dynamic.graph.inputs`, `snowflake.budget.resource`,
  `snowflake.user.privilege.grants_on/granted_by`, `snowflake.user.roles.granted_by/direct` → `string[]`
- ISO-8601 timestamps (all no-data): all 17 fields in `_ISO8601_TIMESTAMP_FIELDS` → `string`

**IA ruling (from @information-architect):**
- JSON object fields: `type: record` would be correct IF Grail stores as structured data, but
  Grail stores as `string`. Use `type: string` + JSON note.
- Array fields: `string[]` for homogeneous string arrays (confirmed for `parent_ids`).
- ISO-8601 fields: `type: string` (Grail stores as plain string; native timestamp needs OpenPipeline).
- Epoch-nanosecond fields (`__type: long`): already correct, no change.

**Fixes applied:**
- 7 instruments-def files updated (32 fields total).
- `ATTR_TYPE_MAP` in `export_semantics.py` extended with `string[]`, `long[]`, `array`, `record`,
  `record[]`.
- Existing `TestTimestampTypeAnnotations::test_iso8601_timestamp_fields_have_type_annotation`
  updated: now requires `__type: string` (not just any annotation; `timestamp` is explicitly wrong).
- Removed `snowflake.grant.created_on` and `snowflake.table.created_on` from `_ISO8601_TIMESTAMP_FIELDS`
  — those are epoch-ns longs in the shares plugin (already correct).

**Tests added:**
- `TestJsonAndArrayFieldTypes` (3 tests): JSON fields → string, JSON note present, arrays → string[]
- `TestTimestampFieldsAreString` (2 tests): ISO-8601 fields → string, format note present
- `TestTypeMappings::test_attr_type_array_types`: string[], long[], array, record, record[]
- `TestTypeMappings::test_attr_type_timestamp_falls_through_to_string`: timestamp→string pass-through
- `TestArrayAndRecordTypesInOutput` (2 tests): output compliance for record/string[] types

---

## TASK 2 (T2) — Note, Stability, SD Status in SEMANTICS.md

**Problem:** `docs/SEMANTICS.md` tables showed only Identifier, Description, Example (and Name,
Unit for metrics). The richly annotated `__semdict_note`, `__stability`, `__semdict` fields were
invisible to documentation readers.

**Fix:** Updated `_generate_semantics_tables()` in `update_docs.py` to add 3 new columns:
- `Note` — from `__semdict_note` (whitespace-collapsed)
- `Stability` — from `__stability`
- `SD Status` — from `__semdict` (ref/new/otel-only/deprecated-alias)

Applies to all section types (dimensions, attributes, metrics, event_timestamps).

**Tests added:** `TestSemanticsTableColumns` (2 tests)

---

## TASK 1 (P1) — DQL examples in SD model YAML

**Problem:** All SD model YAML files lacked `dql_queries:` entries. The SD CI rule F015-F017
requires ≥3 queries per model container. The TODO requested generation based on examples already
present in dashboards and workflows.

**Fix:**
- Added `dql_queries:` top-level key to 10 plugin `instruments-def.yml` files (query_history,
  warehouse_usage, login_history, metering, users, event_log, tasks, resource_monitors, shares,
  budgets). Each has 3-5 queries covering: log fetch, metric timeseries, self-monitoring bizevents.
- `export_semantics.py`: reads `dql_queries:` from raw YAML in parse loop (stored in
  `plugin_dql_queries` dict). All 4 model builders (`_build_log_model_yaml`, `_build_span_model_yaml`,
  `_build_event_model_yaml`, `_build_metric_model_yaml`) emit `dql_queries:` in model envelope when
  present.
- `update_docs.py`: `_generate_semantics_section()` appends `### DQL query examples for the
  <plugin> plugin` fenced code section per plugin when `dql_queries:` is present.

**Tests added:** `TestDqlQueriesOnModels` (3 tests: log model coverage, metric model coverage,
required fields per entry)

---

## Regression test summary

| File | Total tests |
|---|---|
| `test_instruments_def_completeness.py` | 22 (was 14) |
| `test_semdict_output_compliance.py` | 18 (was 13) |
| `test_export_semantics.py` | ~120 (was ~110) |
| `test_semantics_quality.py` | 5 (unchanged) |
| `test_semdict_export_completeness.py` | 5 (unchanged) |

All 148 semdict-related tests pass. Full core suite: 278 passed, 2 skipped, 1 pre-existing fail
(`test_data_retention` — unrelated missing SQL file).

---

## Files changed (summary)

**instruments-def.yml** (21 files, various annotation additions):
`src/dtagent.conf/instruments-def.yml` (major: ad.* fields, interface notes, __interface_note),
`query_history.config`, `data_schemas.config`, `dynamic_tables.config`, `resource_monitors.config`,
`snowpipes.config`, `budgets.config`, `users.config`, `login_history.config` (type annotations),
+ 12 plugins (numeric example unquoting).

**export_semantics.py**: ATTR_TYPE_MAP extended; `_build_interfaces_yaml` accepts `all_entries`;
`plugin_dql_queries` collection; 4 model builders emit `dql_queries`.

**update_docs.py**: `_generate_semantics_tables` adds Note/Stability/SD Status columns;
`_generate_semantics_section` appends DQL examples.

**Tests**: 5 test files updated, ~18 new tests added.

**docs/CHANGELOG.md**: Updated unreleased section.

**test/workflows/test_workflow_execution.py**: 4 stale `_WORKFLOW_AD_SOURCE` entries corrected.

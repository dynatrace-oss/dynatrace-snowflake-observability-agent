# DQL Example Remediation & Per-Context Routing (BIZOBS-151)

## Summary

Reworked the example DQL queries (`dql_queries:`) defined in every plugin's
`src/dtagent/plugins/<plugin>.config/instruments-def.yml`. These examples are exported into the
Dynatrace Semantic Dictionary (SD) model YAML and rendered into `docs/SEMANTICS.md`. Four
defects were fixed:

1. Invalid `| filter db.system == "snowflake"` appended to `timeseries` queries.
2. Deprecated `deployment.environment` grouping key instead of canonical
   `deployment.environment.name`.
3. A single flat `dql_queries:` list was routed indiscriminately to every SD model type
   (metrics/logs/events/spans), so a `fetch logs` example landed on a metric model, a
   `timeseries` example on a log/event model, etc.
4. No structural validation of the example queries existed.

All 20 model-emitting plugins now ship **exactly 3 genuine, tenant-validated example queries
per model type they emit** (129 queries total), routed by a new `context:` field.

## Changes

### Schema — `scripts/tools/instruments-def.schema.json`

- Added a **required** `context` property to the `DqlQuery` `$def`: an array of
  `enum [metrics, logs, events, spans]`, `minItems: 1`, `uniqueItems: true`. Required (not
  optional-with-default) because the entire defect class was "a query silently landed on the
  wrong model" — a default re-creates that failure by omission. `additionalProperties: false`
  means the property had to be declared regardless.
- **Removed** the top-level `dql_queries_span` property (the stopgap it superseded).

### Exporter — `src/build/export_semantics.py`

- Added `_dql_for_context(queries, target)`: filters a plugin's `dql_queries` to entries whose
  `context` includes `target`, and **strips the `context` key** from each returned dict so it
  never leaks into generated SD YAML (`context` is a routing directive, not part of the SD
  `DqlQuery` shape).
- Wired all five model-builder call sites to pass context-filtered lists: metric model
  (`"metrics"`), event model (`"events"`), log model (`"logs"`), span model (`"spans"`), and
  the `event_log` span special-case (`"spans"`).
- Removed the `dql_queries_span` plumbing: the `plugin_dql_queries_span` dict, its raw-read
  block, and the `_span or plugin_dql_queries` fallback at the two span call sites.

### `dql_queries_span` fold-in — `query_history`

`query_history` was the only plugin using `dql_queries_span:`. Its 3 span queries were moved
into `dql_queries:` as normal entries tagged `context: [spans]`; the separate `dql_queries_span`
block was deleted. (It also carried a `fetch bizevents` self-monitoring example which was
dropped — `query_history` emits metrics/logs/spans models but **no** event model, so an events
example had no routing target.)

### QA test — `test/core/test_dql_examples_valid.py` (new)

Validates every `dql_queries` `query_string` across all plugin (and core) instruments-def files
with `dtctl verify query <qs> -o json`, asserting `valid == true`. Gating mirrors
`test/workflows/test_workflow_dql.py::test_dql_syntax_valid_via_dtctl`:

- `@pytest.mark.live` + `@pytest.mark.skipif(shutil.which("dtctl") is None)`.
- The query is passed as a command **argument, never piped** (piping masks dtctl's exit code).
- dtctl exit code `2` (auth/permission) or `3` (network/server), or an auth-signature stderr,
  → `pytest.skip(...)` (environment unavailable). Only `valid: false` (exit 1) is a failure.
- All failures aggregate into one assertion message (plugin file, description, query_string,
  dtctl notifications) for fast fixing.

Because `live` tests are not de-selected by the Makefile targets, this runs under a bare
`pytest` and self-skips when dtctl is absent/unauthenticated — CI stays green while a QA
engineer with authenticated dtctl gets real validation. Confirmed: run against the pre-fix
queries it failed with `FIELD_DOES_NOT_EXIST: The field db.system doesn't exist.` (proving the
guardrail catches defect #1); against the fixed queries all 129 pass.

### Mechanical fixes (Tasks 1 & 2) across all 20 files

- Removed `| filter db.system == "snowflake"` from every `timeseries` query. Kept it on
  `fetch logs`/`spans`/`events`/`bizevents` queries (there `db.system` is a real record field).
- Replaced `deployment.environment` → `deployment.environment.name` inside `by:`/`filter`
  clauses in query strings only. Field/attribute **definition** keys were not touched (the
  deprecated alias stays until its 1.3.0 sunset).

## Sourcing the new example queries (dashboard/workflow mining)

Per the review steer, new examples were **mined from the DSOA-shipped dashboards
(`docs/dashboards/`, 14) and workflows (`docs/workflows/`, 10)** rather than synthesized from
field lists. A mining index extracted 270 unique real DQL fragments and mapped each to the
plugin(s) it targets (by `dsoa.run.plugin` filter and by owned metric/dimension/attribute
names). New examples adapt those real, tenant-authored patterns — the canonical
`fetch logs|events|spans | filter db.system | filter dsoa.run.plugin ... | sort|summarize`
forms and multi-metric `timeseries { a, b, c }, by: {...}` breakdowns come directly from the
dashboards — with dashboard-specific variables (`$Account`, `$Warehouse`, `$__timeframe`),
Davis `fieldsAdd metric_name/_event_*` metadata, and `coalesce(...environment.name, ...environment)`
compatibility wrappers stripped, then the two fixes applied. Every adapted query was
re-validated with `dtctl verify query`.

### Two authoritative gates on every authored/adapted query

1. **`dtctl verify query -o json` → `valid: true`** (structural soundness).
2. **Metric-dimension cross-check**: for every `timeseries` example, each metric name and each
   `by:` grouping dimension must be emitted by *that* plugin (checked against its own
   `metrics:`/`dimensions:` sections). `dtctl` validates against the whole tenant schema and
   will pass a dimension emitted by some other source — so dtctl-green is necessary but not
   sufficient. This gate caught real mistakes during authoring, e.g. an early
   `active_queries` multi-metric example grouped by `snowflake.time.queued.overload` (a
   warehouse_usage metric, not active_queries) and several dashboard queries grouped by
   `service.name` (a resource attribute, not a plugin metric dimension); those were corrected
   to use only real per-plugin dimensions.

## Final per-plugin example source/count table

Every model-emitting plugin now has exactly 3 example queries per emitted model type. "New"
counts the queries added/re-authored to satisfy the ≥3-per-type invariant after strict
routing; the remainder were pre-existing examples (fixed + `context`-tagged). Nearly all new
queries are adaptations of dashboard/workflow DQL patterns as described above; a handful of
`events`-type examples (for plugins whose event tiles were sparse) were authored against the
plugin's real `event_timestamps`/`snowflake.event.type` surface using the canonical
`fetch events | filter dsoa.run.plugin` pattern lifted from the self-monitoring and
budgets-finops dashboards.

| plugin | metrics | logs | events | spans | total | new |
| --- | --- | --- | --- | --- | --- | --- |
| active_queries | 3 | 3 | — | — | 6 | 3 |
| budgets | 3 | 3 | 3 | — | 9 | 6 |
| cold_tables | 3 | 3 | — | — | 6 | 3 |
| data_schemas | — | 3 | — | — | 3 | 0 |
| data_volume | 3 | — | 3 | — | 6 | 3 |
| dynamic_tables | 3 | 3 | 3 | — | 9 | 6 |
| event_log | 3 | — | — | 3 | 6 | 4 |
| event_usage | 3 | — | — | — | 3 | 0 |
| login_history | 3 | 3 | — | — | 6 | 2 |
| metering | 3 | 3 | — | — | 6 | 3 |
| org_costs | 3 | 3 | — | — | 6 | 3 |
| query_history | 3 | 3 | — | 3 | 9 | 3 |
| resource_monitors | 3 | 3 | 3 | — | 9 | 6 |
| shares | — | 3 | 3 | — | 6 | 3 |
| snowpipes | 3 | 3 | 3 | — | 9 | 6 |
| table_health | 3 | — | — | — | 3 | 0 |
| tasks | 3 | 3 | 3 | — | 9 | 6 |
| trust_center | 3 | 3 | — | — | 6 | 3 |
| users | — | 3 | 3 | — | 6 | 2 |
| warehouse_usage | 3 | 3 | — | — | 6 | 2 |
| **total** | **51** | **48** | **24** | **6** | **129** | **≈63** |

Plugins needing only `context:` tags (no new queries): `data_schemas`, `event_usage`,
`table_health`.

## Validation results

- All 129 queries pass `dtctl verify query -o json` (`test/core/test_dql_examples_valid.py`
  green against a live tenant).
- All 20 files pass the updated schema (`make test-instruments-def`).
- `TestDqlQueriesOnModels` (the ≥3-per-emitted-type invariant, unchanged per decision) green;
  generated output verified to have **zero** cross-type routing violations and **no** `context`
  key leakage.
- `make lint` 10.00/10 (pylint, sqlfluff, yamllint, markdownlint, BOM, shellcheck);
  `./scripts/dev/build.sh` and `./scripts/dev/build_docs.sh` both clean.
- YAML line-length (≤140): the multi-metric `timeseries { ... }, by: {...}` and long
  `summarize {...}, by: {...}` examples are wrapped across lines (DQL treats newlines between
  tokens as insignificant); the comma separating an aggregation block from `by:` is preserved.

## Migration / back-compat

Unreleased 1.0.0. `dql_queries_span:` was introduced on this branch, used by one plugin
(`query_history`), and referenced only in `export_semantics.py`, the schema, that plugin's
instruments-def, and a historical devlog. No released artifact, Snowflake object, or external
consumer depends on it → **no upgrade script required**. Its removal is a pure source/generator
change.

## Pre-existing failures (not introduced here, out of scope)

Three `test/core` tests fail identically on a clean checkout of this branch (verified via
`git stash`), unrelated to this ticket:

- `TestEnumDescriptionInSemantics::test_enum_without_brief_renders_value_only`
- `TestEnumDescriptionInSemantics::test_enum_brief_trailing_period_stripped`
- `TestInterfaceRefNotes::test_all_resource_interface_refs_have_notes`
  (flags `deployment.environment.name` missing an `i.dsoa_resource` interface `note:` — a
  field-definition/interface concern, not a `dql_queries` concern).

These should be addressed separately.

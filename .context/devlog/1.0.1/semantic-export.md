# [1.0.2] Semantic Dictionary Export & IA Fixes

> Detailed log for the changes summarised in `docs/CHANGELOG.md` under `[1.0.2]`.

## Added

- **Semantic Dictionary export pipeline** (`build_semantic_export.sh`): generates Semantic
  Dictionary-compliant YAML from all `instruments-def.yml` files under `build/_semdict/source/`,
  enabling DSOA telemetry signals to be submitted to the Dynatrace Semantic Dictionary.
  Fields are classified as `ref` (already in semdict), `new`, `deprecated-alias`, or `otel-only`.
- **CI semantic validation**: `instruments-def.yml` entries are validated for required
  `__description`, `__example`, and `unit` annotations via `test/core/test_instruments_def_schema.py`;
  `__semdict: ref` provenance is enforced via `TestSemdicRefProvenance` in
  `test/core/test_instruments_def_completeness.py`.
- **Anomaly detection field catalog** (`ad.*` namespace): `ad.source`, `ad.source_metric`,
  `ad.direction`, and `ad.category` are now documented at core level in `instruments-def.yml`
  and exported to the Semantic Dictionary. These fields are set by all 10 DSOA anomaly-detection
  workflows in Dynatrace event properties; `ad.direction` and `ad.category` include enum definitions.
- **Per-model-type routing of DQL examples** (`context:` field): each entry under
  `dql_queries:` now declares a `context:` array (`metrics`, `logs`, `events`, `spans`)
  that routes the example to only the matching Semantic Dictionary model type(s). Metric
  models now show only `timeseries` examples, log models only `fetch logs`, event models
  only `fetch events`/`fetch bizevents`, and span models only `fetch spans` — previously the
  same flat list was attached to every model type. Every model-emitting plugin ships ≥3
  genuine, tenant-validated example queries for each model type it emits.
- **DQL query examples** in Semantic Dictionary model YAML: `dql_queries:` sections added for 10
  plugins (query_history, warehouse_usage, login_history, metering, users, event_log, tasks,
  resource_monitors, shares, budgets), meeting the SD CI F015-F017 requirement of ≥3 queries per
  model. Queries are also surfaced in `docs/SEMANTICS.md`. Coverage was completed for the
  remaining 10 model-emitting plugins (active_queries, cold_tables, data_schemas, data_volume,
  dynamic_tables, event_usage, org_costs, snowpipes, table_health, trust_center) so every
  model-emitting plugin now ships ≥3 example DQL queries.
- **Widened DQL test enforcement** (`test/core/test_semdict_output_compliance.py`): the
  `dql_queries` coverage tests no longer check a hardcoded "priority" subset of plugins.
  Log, event, and metric model plugin sets are now discovered dynamically from the generated
  `build/_semdict/source/` output (`model/dsoa/dsoa.logs.*.yaml`, `dsoa.events.*.yaml`, and
  `metrics/dsoa_metrics_*.yaml`), and a new `test_span_models_have_dql_queries` test covers
  the span models. A green result now means complete DQL coverage across every
  model-emitting plugin, not just a curated subset.

## Fixed

- **Invalid `db.system` filter removed from `timeseries` example queries**: the example DQL
  under `dql_queries:` grouped metrics with `timeseries ... by: { ... }` and then appended
  `| filter db.system == "snowflake"`, which references a field that does not exist after a
  `timeseries` aggregation. The filter has been removed from every metric (`timeseries`)
  example while being retained on `fetch logs`/`spans`/`events`/`bizevents` examples where
  `db.system` is a valid record field. All example queries are now validated for structural
  soundness with `dtctl verify query` (see `test/core/test_dql_examples_valid.py`).
- **Example DQL migrated to `deployment.environment.name`**: example queries now group and
  filter on the canonical OpenTelemetry resource attribute `deployment.environment.name`
  instead of the deprecated `deployment.environment` alias.
- **Enum values now visible in SEMANTICS.md**: the doc generator now appends a
  "Possible values: `VALUE` — brief, ..." section to any field that defines `__enum`
  members in `instruments-def.yml`. Previously, structured enum metadata was silently
  dropped from the generated documentation. Affects all fields with `__enum` across all
  plugins (e.g. `snowflake.table.dynamic.refresh.trigger`, `snowflake.warehouse.size`,
  `snowflake.query.execution_status`, and 20+ others).
- **Semdict event model `data_object` corrected**: timestamp-based lifecycle events
  (e.g. `snowflake.grant.created_on`) are sent via the OpenPipeline Events API, not bizevents.
  Generated `dsoa.events.*.yaml` models now correctly declare `data_object: event` instead of
  `data_object: bizevents`.
- **DQL `query_string` extra blank lines removed**: generated Semantic Dictionary YAML files
  previously had an extra blank line after every DQL query line due to PyYAML serialising
  multi-line strings as flow-style scalars. The YAML dumper now uses block literal style (`|`)
  for multi-line strings, producing clean single-spaced DQL examples.
- **Duplicated backward-compatibility note on deprecated-alias fields removed**: the SD export
  generator appended the "DSOA continues to emit it for backward compatibility." boilerplate a
  second time when the field's `__semdict_note` already explained the backward-compat rationale
  (e.g. `deployment.environment`), producing a note with the phrase repeated.
- **Events model-group brief wording aligned**: the `dsoa.events` model-group brief said
  "business events" and used different terminology than the per-plugin event model brief; both
  now consistently describe "state-change events emitted via the Dynatrace OpenPipeline Events API."
- **`authentication.factor.first`/`.second` (login_history) modeled as open enums**: documents the
  known Snowflake authentication factor values (`ID_TOKEN`, `OAUTH_ACCESS_TOKEN`, `PASSWORD`,
  `PROGRAMMATIC_ACCESS_TOKEN`, `SAML2_ASSERTION`, `TOTP`) while allowing custom values.
- **`snowflake.resource_monitor.threshold.direction`/`.level` (resource_monitors) modeled as
  closed enums**: `up`/`down` and `info`/`warn`/`critical`/`exhausted` are fixed,
  code-controlled value sets.
- **`snowflake.task.condition` (tasks) modeled as an open enum**: documents canonical condition
  forms (predecessor-success, stream-has-data, always-true) without claiming a closed set, since
  the field holds arbitrary SQL boolean expressions.
- **Removed never-emitted `snowflake.warehouse.event` field**: no SQL view or plugin code emits
  this bare key; the distinct `snowflake.warehouse.event.trigger` and
  `snowflake.warehouse.event.{name,reason,state}` fields are unaffected and remain in place.
- **`snowflake.misc` Semantic Dictionary grab-bag split into dedicated groups**: the generic
  `snowflake_misc.yaml` field group previously held 40 unrelated fields with no shared namespace
  home. It has been split into `anomaly`, `dsoa.debug`, `dsoa.plugins`, `deployment`,
  `observed_timestamp`, `snowflake.account`, `snowflake.copy`, `snowflake.cost_attribution`,
  `snowflake.entity`, `snowflake.grant`, `snowflake.org`, `snowflake.status`, and
  `snowflake.table.dynamic.graph` — each now has its own Semantic Dictionary field group file.
  No field names changed; only their grouping in the exported YAML.
- **`dsoa.spans.query_history` differentiated from `dsoa.logs.query_history`**: the span model
  previously duplicated the log model's field list and DQL examples verbatim. It now includes
  span-specific fields (`dsoa.debug.span.events.added/failed`, `snowflake.query.step.*` operator
  fields reported via `span.events`) that are excluded from the log model, and its DQL examples
  lead with `fetch spans` instead of `fetch logs`.

# BIZOBS-151 — Semantic Dictionary Export Pipeline

## Problem Statement

DSOA defines ~200+ metrics, attributes, and dimensions across 22 `instruments-def.yml` files.
These definitions existed only inside the agent codebase, with no machine-readable artifact in
the format required by the Dynatrace Semantic Dictionary (`semconv.schema.json`). Without this
artifact there was nothing to submit as a PR to `semantic-dictionary` (BIZOBS-1829 Track A) or
to feed into the GRAIL-52472 lookup-table export pipeline (Track B).

## Solution Design

Extended the DSOA build pipeline with `export_semantics.py` which:

1. Globs all 22 `instruments-def.yml` files (1 core + 20 plugins).
2. Classifies each field using a `__semdict` flag: `ref | new | deprecated-alias | otel-only`.
3. Emits semconv-schema-compliant YAML under `build/_semdict/source/` (gitignored).
4. Validates each output file against `semconv.schema.json` when the schema is available.
5. Returns a summary dict with file/field counts by category.

Two new shell scripts:

- `build_semantic_export.sh` — orchestration wrapper (cleans output dir, calls Python, logs).
- `validate_semantics.sh` — CI lint gate (fails on missing `__description`/`__example`; warns on missing `__unit`).

## Key Design Decisions

### Field Classification Strategy

Four categories map directly to semconv output patterns:

| Category | `__semdict` | Output | Rationale |
|---|---|---|---|
| Known semdict field | `ref` | `- ref: <key>` | No duplication; trust existing semdict definition |
| New proprietary field | `new` (default) | Full `id:` block | All `dsoa.*` and `snowflake.*` namespaces |
| Deprecated OTel field | `deprecated-alias` | `id:` + `deprecated:` + `note:` | `deployment.environment` → `deployment.environment.name` |
| OTel field not yet in semdict | `otel-only` | `id:` + `note:` | `session.id` (Development-tier, model-scoped in semdict) |

Default when flag absent: `new` — allows incremental annotation without breaking the build.

### Deduplication

Many fields (e.g., `snowflake.warehouse.name`, `session.id`) appear in multiple
`instruments-def.yml` files. The exporter uses first-occurrence wins with a WARNING log on
subsequent encounters. Annotation in the first file encountered (alphabetically by plugin name)
takes precedence. Practical implication: `active_queries` is processed before `login_history`
and `query_history`, so `session.id` and `db.query.text` must be annotated there.

### Empty-String Examples

Fields like `snowflake.pipe.invalid_reason` and `snowflake.table.dynamic.refresh.message`
legitimately have nullable values — they use `__example: ""`. The validator accepts empty
string as valid (`None` is the only error case).

### Output Structure

```
build/_semdict/source/
├── fields/snowflake/snowflake_global.yaml        # dsoa.run.*, deployment.environment, etc.
└── model/smartscape/db/snowflake/metrics/
    ├── snowflake_active_queries.yaml
    ├── snowflake_budgets.yaml
    ├── ... (18 more plugin files)
    └── snowflake_warehouse_usage.yaml
```

Global entries: fields from the `_core` plugin + fields whose keys appear in `GLOBAL_FIELD_KEYS`
or start with `dsoa.`. Per-plugin entries: everything else, grouped by first-occurrence plugin.

## Annotated Files

`__semdict` flags added to:

- `src/dtagent.conf/instruments-def.yml` — all 7 dimensions and 3 attributes
- `src/dtagent/plugins/active_queries.config/instruments-def.yml` — `db.query.text` (ref), `session.id` (otel-only)
- `src/dtagent/plugins/login_history.config/instruments-def.yml` — `authentication.type` (ref), `event.id` (ref), `session.id` (otel-only), client.* fields (new)
- `src/dtagent/plugins/query_history.config/instruments-def.yml` — `authentication.type` (ref), `db.query.text` (ref), `event.id` (ref), `session.id` (otel-only), `db.snowflake.*` (new), client.* fields (new)

All other plugins default to `new` (no annotation required).

## Known Issues

1. **`authentication.type` enum gap**: semdict enum has `allow_custom_values: false` with
   members OAUTH2/TOKEN/DEVOPSTOKEN/NONE. DSOA emits PASSWORD. Classified as `ref` with
   `__otel_note` flagging the gap; must raise an enum extension request in the Track A PR.

2. **`observed_timestamp` structural field**: OTel Log Data Model structural field. Emitted as
   `new` with `__otel_note` explaining DT normalization. Confirm with DT ingestion team before
   submitting to semdict.

3. **`session.id` model-scoped**: semdict has `session.id` only in `code_monitoring` model
   (internal). DSOA needs a global `session.id` → classified as `otel-only` pending global semdict registration.

4. **Metric `__type` absent**: ~13 metrics across plugins have no `__type` field (they use the
   legacy `unit`-only pattern). These default to `gauge` instrument. Review each metric during
   the Track A PR process and assign explicit `__type` flags.

## Test Strategy

- **Unit tests** (`test/core/test_export_semantics.py`): 42 tests covering all classification
  types, type mapping, validation, and emission helpers. Uses mock fixture at
  `test/test_data/instruments-def-mock.yml`. All run without filesystem side effects.
- **Integration tests** (class `TestSemanticExporterIntegration`, `@pytest.mark.integration`):
  run against real codebase; verify file count, directory structure, and YAML parseability.
  Skipped when `build/` is absent. All 5 integration tests pass when `build/` exists.

## Files Created/Modified

| File | Change |
|---|---|
| `src/build/export_semantics.py` | NEW — core export logic (~300 lines, pylint 10.00/10) |
| `scripts/dev/build_semantic_export.sh` | NEW — orchestration wrapper |
| `scripts/dev/validate_semantics.sh` | NEW — CI lint |
| `test/core/test_export_semantics.py` | NEW — 42 unit + integration tests |
| `test/test_data/instruments-def-mock.yml` | NEW — mock fixture |
| `scripts/dev/build_docs.sh` | MODIFIED — adds semantic export call |
| `pytest.ini` | MODIFIED — registers `integration` mark |
| `docs/CHANGELOG.md` | MODIFIED — adds user-facing entry |
| `src/dtagent.conf/instruments-def.yml` | MODIFIED — `__semdict` annotations |
| `src/dtagent/plugins/active_queries.config/instruments-def.yml` | MODIFIED — `__semdict` annotations |
| `src/dtagent/plugins/login_history.config/instruments-def.yml` | MODIFIED — `__semdict` annotations |
| `src/dtagent/plugins/query_history.config/instruments-def.yml` | MODIFIED — `__semdict` annotations |

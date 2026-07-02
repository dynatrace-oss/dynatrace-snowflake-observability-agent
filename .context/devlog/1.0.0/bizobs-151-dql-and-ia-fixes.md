# BIZOBS-151 — DQL Coverage & IA Fixes (Round 4)

## Summary

Closed out the remaining lightweight tasks from the BIZOBS-151 implementation plan
(Tasks 1, 2, 3, 4, 5, 8, 9, 10, 12) to finalize the DSOA -> Semantic Dictionary export
for handover to the Information Architect. Tasks 6, 7, and 11 (grouping restructure,
per-model-type DQL, widened test enforcement) are deliberately deferred to a future
session — they require heavier `export_semantics.py` refactors.

## Changes

### Task 1 (G1) — `dql_queries` for the 10 remaining plugins

Added a top-level `dql_queries:` block (>= 3 entries each) to `active_queries`,
`cold_tables`, `data_schemas`, `data_volume`, `dynamic_tables`, `event_usage`,
`org_costs`, `snowpipes`, `table_health`, and `trust_center`, following the existing
`query_history` pattern. Each entry has `query_string`, `description`,
`description_copilot`, `internal: false`. Query mix tailored to each plugin's model
footprint (metric `timeseries`, `fetch logs`, `fetch bizevents`, ranking/breakdown
queries). After regeneration, zero models in `build/_semdict/source/model/dsoa/*.yaml`
are missing `dql_queries`.

Task 1b (model-group DQL) remains explicitly out of scope — gated on an SD-team
decision on whether F015/F017 apply to `model_group:` containers.

### Task 2 (G2) — Duplicated backward-compat sentence

**Problem:** `_emit_id_entry()` in `src/build/export_semantics.py` appended the
"DSOA continues to emit it for backward compatibility." boilerplate a second time
whenever `__semdict_note` already explained the backward-compat rationale (e.g.
`deployment.environment` in `src/dtagent.conf/instruments-def.yml`), producing a
note with the phrase repeated.

**Fix:** Guard on `"backward compatibility" in note_text.lower()` — use the authored
note verbatim when it already covers the ground; otherwise append the boilerplate
sentence as before (also applied to the no-note fallback path for consistency).
Verified `build/_semdict/source/fields/resource_fields/dsoa.yaml` now has a single,
clean `note:` on `deployment.environment` with no `stability: deprecated` (correct
per the Round-3 decision — deprecated fields use `deprecated:` not `stability:`).

### Task 3 (G5) — Events model-group brief wording

`model_group_dsoa_events.yaml`'s brief said "Timestamp-based lifecycle events emitted
by DSOA as business events," inconsistent with the per-plugin event model brief
("Timestamp-based state-change events emitted by the DSOA {plugin} plugin via the
OpenPipeline Events API."). Aligned the group-level (plugin-agnostic) brief to:
"Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace
OpenPipeline Events API."

### Task 4 (G7) — Auth factor open enums

`authentication.factor.first` / `.second` in `login_history.config/instruments-def.yml`
converted to open enums (`allow_custom_values: true`):
- First factor: `ID_TOKEN`, `OAUTH_ACCESS_TOKEN`, `PASSWORD`, `PROGRAMMATIC_ACCESS_TOKEN`,
  `SAML2_ASSERTION`. Example changed from `password123` to `PASSWORD`.
- Second factor: `TOTP`. Description reworded per convention S5 (absence is field
  omission, not NULL): "The second factor used for authentication, such as an MFA
  token. Omitted when only a single factor was used."

### Task 5 (G9) — Resource monitor threshold closed enums

`snowflake.resource_monitor.threshold.direction` (`up`/`down`) and
`.threshold.level` (`info`/`warn`/`critical`/`exhausted`) converted to closed enums
(`allow_custom_values: false`) in `resource_monitors.config/instruments-def.yml` —
these are fixed, code-controlled value sets, not open text. Member briefs lifted
verbatim from the existing field description's documented bands.

### Task 8 — `snowflake.task.condition` open enum

Converted to an open enum (`allow_custom_values: true`) in
`tasks.config/instruments-def.yml`, documenting three canonical forms
(`SUCCESS`-style predecessor conditions, `SYSTEM$STREAM_HAS_DATA(...)` stream-gating,
and always-true conditions) without claiming a closed set — the field holds
arbitrary SQL boolean expressions (unbounded cardinality).

### Task 9 — Remove never-emitted `snowflake.warehouse.event`

Deleted the field definition from `resource_monitors.config/instruments-def.yml`
(confirmed no SQL emits the bare key) and its coverage tuple + docstring reference
in `test/core/test_instruments_def_completeness.py`. Left
`snowflake.warehouse.event.trigger` (same file, real/emitted) and
`snowflake.warehouse.event.{name,reason,state}` (`warehouse_usage.config`, real/emitted)
untouched.

### Task 10 (S2/S3) — Example & note hygiene

- S2: `client.application.id` example changed from the generic `app123` to
  `SnowflakeJDBCDriver` in both independent definitions (`login_history.config` and
  `query_history.config` — no shared instruments-def.yml exists in this repo).
- S3: `snowflake.share.created_on` in `shares.config/instruments-def.yml` was missing
  `__stability: stable` and the "Epoch nanoseconds timestamp." description suffix
  present on sibling timestamp fields (`snowflake.grant.created_on`,
  `snowflake.table.created_on`) in the same file. Added both for parity.

### Additional fix (out of the original task list, but blocking the validation gate)

`test/core/test_instruments_def_completeness.py::TestBooleanTypeAnnotations::
test_known_boolean_fields_without_prefix_have_type_annotation` still referenced the
pre-BIZOBS-2057 field name `plugins.query_history.track_ddl_changes`. That rename
(to `dsoa.plugins.query_history.track_ddl_changes`) was already implemented and
merged into this branch before this session (commits 266b93e, 6e323e0), but the test
file's coverage list and docstring were never updated to match, so `make
test-instruments-def` was red on a fresh checkout. Updated the field name reference
in `_KNOWN_BOOLEAN_NO_PREFIX` and the docstring — no rename logic touched, purely a
stale-string test fix.

### Task 12 — Regenerated fixtures & docs

1. `python scripts/dev/gen_metric_fixture.py` — regenerated
   `test/qa/fixtures/all_metrics_ingest_payload.txt` (header-only drift from
   commit 0693f8f; metric payload lines byte-identical).
2. `./scripts/dev/build_semantic_export.sh` — regenerated `build/_semdict/source/`
   with everything above baked in. This directory is a gitignored build artifact in
   this repo (`build/*` in `.gitignore`) — it is the payload submitted to the
   separate Semantic Dictionary Bitbucket repo, not committed here.
3. `./scripts/dev/build_docs.sh` — rebuilt `docs/SEMANTICS.md` (new DQL query
   sections for the 10 plugins, updated enum tables) and `docs/APPENDIX.md` (gained
   one row in the field-rename table for the already-merged BIZOBS-2057 rename,
   surfaced by the regeneration since that rename predates this session's export
   run history).

## Files Changed

| File | Change |
|---|---|
| `src/build/export_semantics.py` | Task 2: guard against duplicated backward-compat note; Task 3: events model-group brief wording |
| `src/dtagent/plugins/active_queries.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/cold_tables.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/data_schemas.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/data_volume.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/dynamic_tables.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/event_usage.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/org_costs.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/snowpipes.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/table_health.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/trust_center.config/instruments-def.yml` | Task 1: dql_queries |
| `src/dtagent/plugins/login_history.config/instruments-def.yml` | Task 4: auth factor open enums; Task 10: client.application.id example |
| `src/dtagent/plugins/resource_monitors.config/instruments-def.yml` | Task 5: threshold closed enums; Task 9: removed snowflake.warehouse.event |
| `src/dtagent/plugins/tasks.config/instruments-def.yml` | Task 8: task.condition open enum |
| `src/dtagent/plugins/query_history.config/instruments-def.yml` | Task 10: client.application.id example |
| `src/dtagent/plugins/shares.config/instruments-def.yml` | Task 10: share.created_on stability + note |
| `test/core/test_instruments_def_completeness.py` | Task 9: removed coverage tuple; stale field-name fix (BIZOBS-2057 test hygiene) |
| `test/qa/fixtures/all_metrics_ingest_payload.txt` | Task 12: regenerated |
| `docs/SEMANTICS.md`, `docs/APPENDIX.md` | Task 12: regenerated |

## Test Results

- `.venv/bin/pytest test/core/` — 358+ passed; remaining failures are pre-existing
  sandbox/environment artifacts (`mktemp` restricted in the sandboxed dev shell used
  for this session) in `test_bash_scripts.py` and one flaky `test_connector.py::
  test_automode`, confirmed unrelated by diffing against a clean-checkout baseline
  run and by re-running outside the sandbox (3 failures remained, same set present
  before this session's changes).
- `make test-instruments-def` — GREEN (was RED on `test_metric_ingest_fixture` and
  the stale-field-name completeness test before Task 12 + the additional fix).
- `make test-semdict` — GREEN (174 passed).
- `make lint` — pylint **10.00/10**.
- `./scripts/dev/build.sh` — passes.
- `./scripts/dev/build_docs.sh` — leaves a clean tree after committing regenerated
  artifacts.
- Manual: 0 models missing `dql_queries` in regenerated `build/_semdict/source/model/dsoa/*.yaml`.

## Known Remaining Work (out of scope for this session)

- Task 6 (G4) — split the `snowflake.misc` grab-bag namespace.
- Task 7 (G8) — differentiate `dsoa.spans.query_history` from the log model
  (requires per-model-type DQL, a generator change).
- Task 11 — widen `test_semdict_output_compliance.py` DQL enforcement from the
  hardcoded priority-plugin frozensets to the full set of model-emitting plugins.
- Task 1b — model-group DQL, pending an SD-team decision on F015/F017 applicability.
- BIZOBS-2058 (S6: `snowflake.table.ddl` rename), BIZOBS-2060 (ISO-8601 -> epoch
  timestamp conversions) — tracked separately, deferred to 1.0.1+.

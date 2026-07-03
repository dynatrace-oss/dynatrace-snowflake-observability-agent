# BIZOBS-151 — Widen DQL Test Enforcement (Task 11, final task)

## Summary

Closed out the final in-session task from the BIZOBS-151 implementation plan — Task 11,
widening `test/core/test_semdict_output_compliance.py`'s DQL coverage enforcement so a green
result means *complete* coverage across every model-emitting plugin, not just a curated
"priority" subset. This was deliberately deferred from the prior session (see
`bizobs-151-misc-split-and-span-differentiation.md`, "Known Remaining Work"). With this task
done, all in-session tasks (1-11) of the BIZOBS-151 plan are complete; only PR
submission/IA handover remains, which is out of scope for this ticket's implementation work.

## Motivation

The three `TestDqlQueriesOnModels` tests previously checked hardcoded frozensets —
`PRIORITY_LOG_PLUGINS` (5 of 16 log-model plugins) and `PRIORITY_METRIC_PLUGINS` (3 of 17
metric-model plugins). Task 1 (this branch, prior session) already added `dql_queries:` to
the remaining 10 plugins that lacked it, so every model-emitting plugin now has ≥3 DQL
examples — but the test suite didn't verify that fact. A green `make test-semdict` gave false
confidence: it would stay green even if a future plugin change dropped `dql_queries:` from a
non-priority plugin. There was also no coverage at all for event models, and no dedicated
span-model DQL test (span coverage was folded implicitly into
`test_dql_queries_have_required_fields`'s blanket glob, but nothing asserted the `>= 3` count
for spans specifically).

## Changes

### `test/core/_semdict_test_utils.py`

Added three discovery helpers plus a shared private implementation:

- `_discover_model_plugins(glob_pattern, base_dir, filename_regex)` — globs candidate files,
  parses each, and keeps only documents with a **truthy top-level `model:` key**. This is the
  key discriminator established by investigation of the generated output structure:
  per-plugin model files have `model:`; model-group container files
  (`model_group_dsoa_logs.yaml`, `model_group_dsoa_events.yaml`, `model_group_dsoa_spans.yaml`,
  `dsoa_metrics_model_group.yaml`) have `model_group:` instead; `interfaces_dsoa.yaml` has
  `groups:` and no `model:` key at all. Filtering on `model` truthiness excludes all three
  container shapes without needing filename-pattern gymnastics.
- `discover_log_model_plugins()` — `model/dsoa/dsoa.logs.*.yaml` → plugin names via regex
  `dsoa\.logs\.(?P<plugin>.+)\.yaml`.
- `discover_event_model_plugins()` — same pattern for `dsoa.events.*.yaml`.
- `discover_metric_model_plugins()` — `metrics/dsoa_metrics_*.yaml` → plugin names via
  `dsoa_metrics_(?P<plugin>.+)\.yaml`; naturally excludes `dsoa_metrics_model_group.yaml`
  because that file's top-level key is `model_group`, not `model`.

Span plugins were **not** re-derived: the plan explicitly said to reuse the existing
`SPAN_PLUGINS` constant (`frozenset({"query_history", "event_log"})`) in
`test_semdict_output_compliance.py`, which is already correct.

### `test/core/test_semdict_output_compliance.py`

`TestDqlQueriesOnModels`:

- Removed `PRIORITY_LOG_PLUGINS` and `PRIORITY_METRIC_PLUGINS` frozensets.
- `test_log_models_have_dql_queries` and `test_metric_models_have_dql_queries` now call
  `discover_log_model_plugins()` / `discover_metric_model_plugins()` at the top of the test
  body (not at module/class-definition time) — this matches the existing pattern in this file
  of calling `require_semdict_source()` (which uses `pytest.skip()`) from inside test methods
  rather than at import time, where `pytest.skip()` cannot be safely invoked.
- Added `test_event_models_have_dql_queries`, mirroring the log-model test exactly but
  iterating `discover_event_model_plugins()` against `dsoa.events.<plugin>.yaml`.
- Added `test_span_models_have_dql_queries`, iterating the existing `SPAN_PLUGINS` constant
  against `dsoa.spans.<plugin>.yaml`. Confirmed no equivalent test already existed elsewhere
  in the file before adding it — the only prior span-model test was
  `TestModelsExistForAllPlugins::test_span_models_exist_for_span_plugins`, which checks file
  *existence*, not `dql_queries` count.
- Extended `test_dql_queries_have_required_fields` to scan both `model/dsoa/*.yaml` and
  `metrics/*.yaml` (previously only the former), so metric models' `dql_queries` entries are
  also checked for the four required fields (`query_string`, `description`,
  `description_copilot`, `internal`). Model-group/interfaces files are still naturally
  skipped — they have no `model.dql_queries` because they have no `model:` key.

### Model-group scope decision

Per the plan's Task 1 "Open decision (SD team)" box: whether CI checks F015/F017 apply to
`model_group:` containers was never answered by the SD team. Per the plan's own "if no ->
model groups are out of scope" branch, no DQL requirement was added to any
`model_group_dsoa_*.yaml` / `dsoa_metrics_model_group.yaml` container, and no generator or
test change touches those files' content.

## Verification

Discovered plugin counts, confirmed against a fresh regeneration of
`build/_semdict/source/`:

| Model type | Discovered count | Plugins |
| --- | --- | --- |
| Log | 16 | active_queries, budgets, cold_tables, data_schemas, dynamic_tables, login_history, metering, org_costs, query_history, resource_monitors, shares, snowpipes, tasks, trust_center, users, warehouse_usage |
| Event | 8 | budgets, data_volume, dynamic_tables, resource_monitors, shares, snowpipes, tasks, users |
| Metric | 17 | active_queries, budgets, cold_tables, data_volume, dynamic_tables, event_log, event_usage, login_history, metering, org_costs, query_history, resource_monitors, snowpipes, table_health, tasks, trust_center, warehouse_usage |
| Span | 2 (unchanged `SPAN_PLUGINS`) | query_history, event_log |

Widening the enforcement did **not** go red — confirming the plan's prediction that every
plugin already had `dql_queries:` with ≥3 entries in every model type it emits (from Task 1).

## Files Changed

| File | Change |
| --- | --- |
| `test/core/_semdict_test_utils.py` | Added `_discover_model_plugins`, `discover_log_model_plugins`, `discover_event_model_plugins`, `discover_metric_model_plugins`; added `re` import. |
| `test/core/test_semdict_output_compliance.py` | Removed hardcoded `PRIORITY_LOG_PLUGINS`/`PRIORITY_METRIC_PLUGINS`; widened `test_log_models_have_dql_queries`/`test_metric_models_have_dql_queries` to dynamic discovery; added `test_event_models_have_dql_queries` and `test_span_models_have_dql_queries`; extended `test_dql_queries_have_required_fields` to also scan `metrics/*.yaml`. |
| `.context/dev-notes/1.0.0/BIZOBS-151/BIZOBS-151-implementation-plan.md` | Marked Task 11 done (✅); ticked all Definition-of-Done checklist items; updated `status:` frontmatter to `implementation-complete-pending-pr`. |
| `docs/CHANGELOG.md` | Added `[1.0.0]` entry describing the widened DQL test enforcement. |

## Test Results

- `.venv/bin/pytest test/core/test_semdict_output_compliance.py -v` — 18 passed (5 new/widened
  tests in `TestDqlQueriesOnModels`, all green).
- `.venv/bin/pytest test/core/` — 360 passed, 2 skipped, 24 failed; the 24 failures are the
  same pre-existing sandbox/environment artifacts from prior sessions (`mktemp` restricted in
  the sandboxed dev shell affecting `test_bash_scripts.py` and one `test_connector.py` timing
  test), reconfirmed via `git stash` diff against the pre-session baseline (identical 24
  failures with none of this session's changes applied) and by re-running outside the sandbox
  (all pass there, including `test_ci_export` and `make test-semdict` in full).
- `make test-instruments-def` — GREEN (48 passed).
- `make test-semdict` — GREEN (176 passed inside the sandbox for the three pytest suites;
  full target including the bats-backed `test_ci_export` re-run outside the sandbox also GREEN).
- `make lint` — pylint **10.00/10** on both `src/` and `test/`.
- `./scripts/dev/build.sh` — passes outside the sandbox (`mktemp` restriction only; not a code
  issue, confirmed pre-existing).
- `./scripts/dev/build_docs.sh` — leaves a clean tree; no doc drift, as expected for a
  test-only change (no source or generator files touched).

## Known Remaining Work (out of scope for this ticket)

- PR submission and Information Architect handover — the next step, not an implementation
  task for this plan.
- Task 1b — model-group DQL, pending an SD-team decision on F015/F017 applicability that was
  never made; deliberately stays out of scope per the plan's own decision branch.
- BIZOBS-2058 (S6: `snowflake.table.ddl` rename), BIZOBS-2060 (ISO-8601 -> epoch timestamp
  conversions) — tracked separately, deferred to 1.0.1+.

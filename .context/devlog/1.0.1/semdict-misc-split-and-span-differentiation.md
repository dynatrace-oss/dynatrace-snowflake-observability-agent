# `snowflake.misc` Split & Span Model Differentiation (Round 5)

## Summary

Closed out the two heaviest remaining tasks from the implementation plan —
Task 6 (split the `snowflake.misc` grab-bag) and Task 7 (differentiate
`dsoa.spans.query_history` from the log model). Both were flagged in the plan's "Task
dependency notes" as the heaviest generator changes and the ones carrying the most
scope-creep risk. Task 11 (widen DQL test enforcement) remains deliberately deferred to
a future session.

## Changes

### Task 6 (G4) — Split the `snowflake.misc` grab-bag

**File:** `src/build/semantic_exporter/` — `_SIG_NS` (ordered `(prefix, group_id,
group_type)` list matched first-prefix-wins by `_ns_group`).

Added namespace entries so these leave the `snowflake.misc` fallback bucket:

- `snowflake.table.dynamic.graph` — placed **before** the generic `snowflake.table` entry,
  since `_ns_group` returns the first match and `_SIG_NS` order matters.
- `anomaly`, `dsoa.debug`, `dsoa.plugins`, `deployment`, `observed_timestamp` — non-Snowflake
  concepts. `dsoa.plugins` and the `deployment`/`observed_timestamp` pair weren't explicitly
  named in the plan's Task 6 bullet list, but they were non-Snowflake fields living in
  `snowflake_misc.yaml`, and the plan's own **verify criterion** for Task 6 explicitly lists
  `deployment.environment.name` and `observed_timestamp` as concepts that must not remain in
  a `snowflake.*`-named group. Extracting `dsoa.plugins` follows the same rationale for
  consistency (a `dsoa.*`-namespaced field has no business in a `snowflake.*` group either).
- `snowflake.account`, `snowflake.copy`, `snowflake.cost_attribution`, `snowflake.entity`,
  `snowflake.grant`, `snowflake.org`, `snowflake.status` — Snowflake namespaces named in the
  plan.
- Exact-match entries for three bare fields with no dotted child segment, so they don't
  match their sibling group's dotted prefix: `snowflake.cluster_number` → `snowflake.cluster`,
  `snowflake.release_version` → `snowflake.release`, `snowflake.secondary_role_stats` →
  `snowflake.secondary`. This was flagged in the task briefing as a "bonus, low-risk cleanup"
  — no field is renamed, only its group membership changes.

**Investigation finding:** no separate group-registration/title-brief step exists.
`_build_signal_fields_yaml` generates `title`, `brief`, and the output filename
(`gid.replace(".", "_") + ".yaml"`) inline from `group_id` for every group — adding a new
`_SIG_NS` entry is sufficient on its own; there is nothing else to "register."

**Result:** `snowflake_misc.yaml` no longer exists after regeneration (empty group → no file
written) — zero residue, not just a reduction. 13 new group files were created:
`anomaly.yaml`, `deployment.yaml`, `dsoa_debug.yaml`, `dsoa_plugins.yaml`,
`observed_timestamp.yaml`, `snowflake_account.yaml`, `snowflake_copy.yaml`,
`snowflake_cost_attribution.yaml`, `snowflake_entity.yaml`, `snowflake_grant.yaml`,
`snowflake_org.yaml`, `snowflake_status.yaml`, `snowflake_table_dynamic_graph.yaml`.

### Task 7 (G8) — Differentiate `dsoa.spans.query_history` from the log model

`dsoa.spans.query_history.yaml` was a verbatim copy of `dsoa.logs.query_history.yaml` (38
identical `ref:` entries, identical `dql_queries:` leading with `fetch logs`).

**Per-model-type DQL (generator plumbing).** Added an optional top-level
`dql_queries_span:` key in `instruments-def.yml`. The generator reads it into a new
`plugin_dql_queries_span` dict (mirroring the existing `plugin_dql_queries` read), and the
two span-model call sites now pass
`plugin_dql_queries_span.get(plugin_name) or plugin_dql_queries.get(plugin_name)` — falling
back to the shared list for any `SPAN_PLUGINS` member that doesn't define a span-specific
block. `query_history.config/instruments-def.yml` gained a `dql_queries_span:` block with
three entries: a `fetch spans` overview query (same shape as the existing one, since the
span model no longer needs the `fetch logs` query first), a `trace.id`/`span.id`
root-span-correlation query, and a `span.events` query surfacing
`snowflake.query.step.*` operator data.

**Field differentiation — investigation and mechanism choice.** The plan asked to
investigate `_collect_plugin_attribute_refs` and the existing `__context_names` mechanism
before inventing anything new. Findings:

- `_collect_plugin_attribute_refs` already accepts a `context_name` parameter that filters
  entries by `__context_names`, but neither `_build_log_model_yaml` nor
  `_build_span_model_yaml` used it — both called it identically with no context, which is
  exactly why the two models were byte-identical in their field lists.
- `__context_names` itself, however, is **already a heavily-used, established mechanism**
  across many other plugins (`budgets`, `users`, `login_history`, `tasks`, `snowpipes`,
  `shares`, `dynamic_tables`, `warehouse_usage`, `org_costs`, `cold_tables`, `metering`) —
  but for a *different* purpose: scoping a field to the specific source SQL view/context it
  comes from (e.g. `task_history` vs. `task_versions`, `snowpipes` vs.
  `snowpipes_copy_history`). It has nothing to do with log-vs-span differentiation anywhere
  else in the codebase.
- First attempt: wire `context_name="log"` / `context_name="span"` into the two builder
  call sites. Regenerating showed real regressions — the log models for `budgets`,
  `cold_tables`, `dynamic_tables`, `login_history`, `metering`, `org_costs`, `shares`,
  `snowpipes`, `tasks`, `users`, and `warehouse_usage` all silently lost fields, because any
  field with a view-scoped `__context_names` (e.g. `["task_history"]`) doesn't contain the
  literal string `"log"` and got filtered out. This also broke
  `test/core/test_documentation.py::test_check_required_fields`, which enforces an
  all-fields-or-none rule per `instruments-def.yml` file: once *any* field in a file has
  `__context_names`, *every* field in that file must have it. Tagging only
  `query_history`'s 9 span-specific fields would have required either (a) tagging its
  ~80 remaining fields too (well beyond the task's scope), or (b) breaking that test.
- **Decision:** reverted the `__context_names` reuse and added a small, dedicated
  `__span_only: true` field annotation instead, with a matching `exclude_span_only` flag on
  `_collect_plugin_attribute_refs` used only by `_build_log_model_yaml`. This is the
  smaller, non-colliding change: it doesn't touch the pre-existing SQL-view-scoping
  semantics of `__context_names`, doesn't require tagging unrelated fields, and doesn't trip
  the completeness test (which only looks at `__context_names`).
- Tagged the 9 genuinely span-only `query_history` fields:
  `dsoa.debug.span.events.added`, `dsoa.debug.span.events.failed`, and the 7
  `snowflake.query.step.*` operator fields (`step.id`, `operator.attributes`, `.id`,
  `.parent_ids`, `.stats`, `.time_breakdown`, `.type`) — these are only meaningful in the
  context of a span's `span.events` payload (the query execution plan), not a bare log line.

**Deliberate scope-limiting decision:** the plan's field list also named `trace.id`,
`span.id`, `start_time`, `end_time`, `span.kind`, and `request.is_root_span`. These are
**not** added as new DSOA-owned `instruments-def.yml` fields. They are structural fields
inherent to the span envelope itself for any `data_object: span` model (OTel span wire
format — trace/span identifiers, timing, kind), not custom semconv attributes DSOA defines.
No such bare field exists anywhere in the current Semantic Dictionary export output, and
DSOA has never modeled them for any other span-emitting plugin (`event_log` also has no
custom-owned span-envelope fields). Adding them as new plugin-owned attributes would
duplicate global OTel/SD semantics — precisely the semantic-reuse smell the
`sd-information-architect` review guidance warns against ("don't name the same concept two
ways"). Instead, they are exercised directly as literal DQL field references in the new
`dql_queries_span` trace/span-correlation query, which is the appropriate way to surface
them without DSOA claiming ownership of their definitions.

**Schema update:** `scripts/tools/instruments-def.schema.json` gained the new
`dql_queries_span` top-level array property and the `__span_only` boolean property on
`AttributeDefinition`, both following the existing pattern of their siblings
(`dql_queries`, `__context_names`).

## Verification

- `dsoa.spans.query_history.yaml`'s `ref:` list now differs from
  `dsoa.logs.query_history.yaml`'s: the log model excludes the 9 `__span_only` fields; the
  span model includes them like any other attribute.
- `dsoa.spans.query_history.yaml`'s `dql_queries:` now leads with `fetch spans` (from the
  new `dql_queries_span:` block); `dsoa.logs.query_history.yaml`'s is unchanged, still
  leading with `fetch logs`.
- Regenerating with only the Task 6 change in place produced a byte-identical diff for every
  file except the misc-split targets (confirmed via a before/after full-tree diff), ruling
  out any accidental grouping regression elsewhere.
- Regenerating with the (reverted) `__context_names`-reuse approach for Task 7 showed the
  cross-plugin regression described above; regenerating with the final `__span_only`
  approach showed zero diff outside `dsoa.spans.query_history.yaml` /
  `dsoa.logs.query_history.yaml`.

## Files Changed

| File                                                           | Change                                                                                                                                                                                                                                                                                                                                      |
|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `src/build/semantic_exporter/`                                | Task 6: 15 new `_SIG_NS` entries (incl. one dynamic-graph entry ordered before its generic parent, three exact-match bare-field routes). Task 7: `plugin_dql_queries_span` dict + read + span call-site fallback; `exclude_span_only` param on `_collect_plugin_attribute_refs`; `_build_log_model_yaml` now excludes `__span_only` fields. |
| `scripts/tools/instruments-def.schema.json`                    | Task 7: added `dql_queries_span` top-level property and `__span_only` `AttributeDefinition` property.                                                                                                                                                                                                                                       |
| `src/dtagent/plugins/query_history.config/instruments-def.yml` | Task 7: `__span_only: true` on 9 fields; new `dql_queries_span:` block (3 entries).                                                                                                                                                                                                                                                         |
| `docs/CHANGELOG.md`                                            | Added `[1.0.0]` entries for both tasks.                                                                                                                                                                                                                                                                                                     |

## Test Results

- `.venv/bin/pytest test/core/` — 356 passed, 4 skipped; the remaining 24 failures are the
  same pre-existing sandbox/environment artifacts identified in the prior session
  (`mktemp` restricted in the sandboxed dev shell; `test_bash_scripts.py` and
  `test_connector.py::test_automode`), reconfirmed via `git stash` diff against the
  pre-session baseline and by re-running outside the sandbox (all pass there).
- `make test-instruments-def` — GREEN (48 passed).
- `make test-semdict` — GREEN (174 passed; the schema-compliance and documentation-hygiene
  failures hit mid-session — `dql_queries_span` as an unknown schema property, and the
  `__context_names` all-or-nothing rule — were both root-caused and fixed, not
  worked around).
- `make lint` (`pylint src/`) — **10.00/10**.
- `./scripts/dev/build.sh` — passes (outside sandbox; `mktemp` restriction only, not a
  code issue).
- `./scripts/dev/build_docs.sh` — leaves a clean tree; `docs/SEMANTICS.md`/`docs/APPENDIX.md`
  did not change in this session (their generation pipeline doesn't surface the grouping
  restructure or the span DQL/field differentiation in visible content).
- `python scripts/dev/gen_metric_fixture.py` — already in sync, no fixture changes.
- Full before/after diff of `build/_semdict/source/` confirmed: only the intended files
  changed for each task, nothing else moved.

## Known Remaining Work (out of scope for this session)

- Task 11 — widen `test_semdict_output_compliance.py` DQL enforcement from the hardcoded
  priority-plugin frozensets to the full set of model-emitting plugins.
- Task 1b — model-group DQL, pending an SD-team decision on F015/F017 applicability.
- (S6: `snowflake.table.ddl` rename), (ISO-8601 -> epoch timestamp
  conversions) — tracked separately, deferred to 1.0.1+.

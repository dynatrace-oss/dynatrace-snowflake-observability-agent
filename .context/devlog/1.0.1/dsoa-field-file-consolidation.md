# Consolidate DSOA field-definition files to match the Snowflake convention

## Summary

Follow-up structural consistency improvement (not a PR #1964 reviewer comment — a voluntary
suggestion made during review of the PR #1964 fixes) applying the same domain-file consolidation
already used for `snowflake` to `dsoa`:

| | Before | After |
|---|---|---|
| signal fields source | `dsoa_debug.yaml` + `dsoa_plugins.yaml` (2 files) | `dsoa.yaml` (1 file, 2 groups) |
| resource fields source | `resource_fields/dsoa.yaml` | `resource_fields/dsoa_resource.yaml` |
| doc/fields | `dsoa.md` + `dsoa_debug.md` + `dsoa_plugins.md` (3 files) | `dsoa.md` (1 file, 3 semconv blocks) |

Precedent: `source/fields/resource_fields/snowflake_resource.yaml` already existed, establishing
the `<domain>.yaml` (signal) / `<domain>_resource.yaml` (resource) naming convention this change
now also applies to `dsoa`. `doc/fields/snowflake.md` already consolidated all `snowflake`/
`snowflake.*` groups (signal + resource) into one file (Fix 5 of the PR #1964 fixes) — `dsoa.md`
now does the same for `dsoa`/`dsoa.*` groups.

## Changes (`src/build/semantic_exporter/`)

1. **`_build_signal_fields_yaml`**: extended the existing `snowflake`/`snowflake.*` →
   `fields/signal_fields/snowflake.yaml` bucketing to also bucket `dsoa`/`dsoa.*` groups into
   `fields/signal_fields/dsoa.yaml`.
2. **`_build_resource_fields_yaml`**'s write call site: renamed the output path
   `fields/resource_fields/dsoa.yaml` → `fields/resource_fields/dsoa_resource.yaml`.
3. **`_build_per_field_doc_stubs`**: generalized the single-domain (`snowflake`-only) special-case
   into a small `_CONSOLIDATED_DOMAINS` dict (`{prefix: (filename, h2_heading)}`) covering both
   `snowflake` and `dsoa`, with a `_consolidated_domain()` helper replacing the previous
   hardcoded `if group_id == "snowflake" or group_id.startswith("snowflake.")` check. Each
   consolidated file gets one shared `## <Domain>` h2 (using the full, unabbreviated product name
   for `dsoa`, per the PR #1964 subtitle-abbreviation fix) followed by one `<!-- semconv id -->`
   stub block per group.
4. **`_build_owners_entries`**: updated `dsoa_res_file` to the renamed path, and added a
   `dsoa_added`/`dsoa_doc_added` consolidation branch (mirroring the existing
   `snowflake_added`/`snowflake_doc_added` pattern) in both the signal-field source-path loop and
   the doc/fields path loop.

## Tests

- Updated ~10 existing assertions in `test/core/test_export_semantics.py` that referenced the old
  per-file paths (`dsoa_debug.yaml`, `dsoa_plugins.yaml`, `resource_fields/dsoa.yaml`,
  `doc/fields/dsoa_debug.md`, `doc/fields/dsoa_plugins.md`).
- `test_stub_heading_dsoa_subgroups_keep_full_name` rewritten: `dsoa.debug`/`dsoa.plugins` now
  share one file with one shared `## <full name>` heading (not a per-subgroup heading each) —
  matches the `snowflake.md` multi-block-per-file pattern exactly.
- Added `test_dsoa_doc_path_referenced_once`, `test_dsoa_signal_source_path_referenced_once`,
  `test_dsoa_resource_source_file_uses_renamed_path` to `TestBuildOwnersEntries`.
- Added dsoa assertions to the existing `test_signal_fields_file_exists` integration test.

## SD-repo migration (one-time cleanup)

Since the generator/export pipeline never auto-deletes superseded files, deleted the now-stale
files from the SD repo checkout after confirming (via `bbctl pr comments 1964`) no PR review
comments are anchored to them:

- `source/fields/signal_fields/dsoa_debug.yaml`, `dsoa_plugins.yaml` (content → `dsoa.yaml`)
- `source/fields/resource_fields/dsoa.yaml` (renamed → `dsoa_resource.yaml`)
- `doc/fields/dsoa_debug.md`, `doc/fields/dsoa_plugins.md` (content → `dsoa.md`)

**Ordering gotcha:** the old and new files both declare a group with id `dsoa` (the resource
group) — running `--generate-docs` with the old file still present before the new file replaces
it produces a hard `Duplicated id found` error from the SD generator (not a warning). The stale
files must be deleted *before* regenerating, not after.

## Side effect: `display_name` backfill

Regenerating surfaced a related, deterministic side effect: `_merge_into_ruamel`'s
`_UPDATABLE_KEYS` (the set of *attribute*-level scalars propagated to an already-existing
attribute on re-export) does not include `display_name` — by design, since `display_name`
changes require a distinct SD contribution process (per the SD repo's own `AGENTS.md`) and
should not be silently auto-propagated like `brief`/`type`/`examples`. Because the old
`dsoa_debug.yaml`/`dsoa_plugins.yaml`/`dsoa.yaml` (resource) files already existed, every prior
re-export took the *merge* path and their attributes silently never picked up `display_name`
values, even though `_build_attribute_node` always computes one. Deleting those files forced a
genuine *fresh write* (bypassing the merge path entirely) for the new `dsoa.yaml` /
`dsoa_resource.yaml`, which included the complete, correct `display_name` for every dsoa
attribute for the first time. This same completed data flows into every per-plugin
`doc/model/snowflake/{logs,events,spans}/*.md` file that renders the shared `i.dsoa_resource`
interface fields table, so those 26 files also picked up the `Display name: ...` lines as a
direct, deterministic, and desirable consequence of this consolidation — verified idempotent
(reproduced identically from a clean baseline twice). This is *not* a blanket fix to the
`_UPDATABLE_KEYS` gap (that would need its own deliberate proposal given the special
`display_name` contribution-process caveat) — just documenting where this specific one-time
content improvement came from.

A separate, unrelated churn was also observed and **reverted** during this work: the initial
regeneration attempt (before the stale-file-deletion ordering was corrected) showed the exact
same `Display name:` backfill pattern on all 26 `doc/model/snowflake/**/*.md` files even before
the ordering fix — this was investigated and confirmed to stem from the same underlying cause
above, not from anything unrelated, so it was kept (not reverted) once the ordering issue was
resolved.

## `docs/semantic-dictionary/` mirror refresh

Separately, `docs/semantic-dictionary/` (a mirrored copy in the main repo, produced by
`make semantic-dictionary` → `build_semantic_export.sh --output-dir docs/semantic-dictionary`,
distinct from the live SD repo checkout at `.context/semantic-dictionary`) was found to be very
stale — still using a pre-existing-but-abandoned naming scheme (`model/dsoa/dsoa.logs.*.yaml`,
`metrics/dsoa_metrics_*.yaml`, and 31 individual `fields/signal_fields/snowflake_*.yaml` files)
that predates the current `model/snowflake/`, `metrics/snowflake_metrics_*`, and
consolidated-`snowflake.yaml` conventions entirely — evidently not regenerated with `--clean` in
a long time. Re-ran `./scripts/dev/build_semantic_export.sh --output-dir docs/semantic-dictionary
--clean` to fully refresh it against current code: ~132 files changed (mostly deletions of the
abandoned naming, replaced with current output), verified idempotent across two consecutive
`--clean` runs. The directory's single static `README.md` marker
(`Auto-generated — do not edit. Run 'make semantic-dictionary' to regenerate.`) is not written by
any current code path (confirmed via grep) — it was manually restored after each `--clean` run
since `--clean` wipes the entire output directory indiscriminately.

## Verification

- `.venv/bin/pytest test/core/test_export_semantics.py test/core/test_semdict_export_completeness.py
  test/core/test_semdict_output_compliance.py` — 253 passed.
- `.venv/bin/flake8` / `.venv/bin/pylint` — no new findings; pylint unchanged at 9.97/10.
- Regenerated the SD repo checkout via `--generate-docs`: diff scoped to the expected files (new
  `dsoa.yaml`/`dsoa_resource.yaml`, deleted `dsoa_debug.{yaml,md}`/`dsoa_plugins.{yaml,md}`,
  consolidated `dsoa.md`, `OWNERS`, and the 26 `doc/model/snowflake/**/*.md` `display_name`
  backfill discussed above) — idempotent across two consecutive runs.
- `--check` (DSOA-scoped sanity checks): 10 findings (up from 9) — F014 (display_name
  consistency) count moved from 6 to 7: the pre-existing `i.dsoa_resource` finding is now
  *resolved* (dsoa's own display_name data is complete), but 2 *new* findings appeared for
  `snowflake.logs/spans.query_history.fields` (those models reference `dsoa.plugins.query_history.*`
  attributes that are now consistently populated, exposing pre-existing incompleteness in their
  sibling refs by contrast). All F014 findings remain non-blocking per the SD repo's own
  conventions (informational severity) and match the precedent already accepted for the other 5
  in the PR #1964 comment thread (Schoenberger/Schinwald agreed to skip F014 for the initial
  submission). `doc/` left byte-identical to its pre-`--check` state (verified by the earlier
  `--check` doc-restore fix still working correctly here).

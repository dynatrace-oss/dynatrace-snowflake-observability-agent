# Rename `__otel_note` → `__semdict_note` in instruments-def schema

**Ticket:** BIZOBS-151 (semantic dictionary YAML build — schema cleanup)
**Branch:** `feat/1.0.0/rename-otel-note-to-semdict-note`
**Date:** 2026-06-17

## Motivation

The field key `__otel_note` implied notes were exclusively about OpenTelemetry alignment.
In practice the field is used for three distinct purposes:

1. **OTel alignment notes** — deprecated aliases, OTel semconv references
2. **Semantic Dictionary-specific notes** — enum extension requests, semdict limitations
3. **General reviewer notes** — plugin architecture notes, future-work comments with no OTel connection

The rename to `__semdict_note` is semantically accurate: the note surfaces as a `note:` field in
the generated Semantic Dictionary YAML, regardless of whether its content relates to OTel.

## Files changed

| File | Change |
|---|---|
| `src/build/export_semantics.py` | Renamed 8 occurrences: `__otel_note` → `__semdict_note`; updated validation error message and docstring |
| `test/core/test_export_semantics.py` | Updated 8 test references: fixture keys, docstrings, assertions |
| `test/test_data/instruments-def-mock.yml` | Renamed 3 fixture keys |
| `src/dtagent.conf/instruments-def.yml` | Renamed 3 occurrences (core dimensions: `db.system`, `deployment.environment`, `observed_timestamp`) |
| `src/dtagent/plugins/query_history.config/instruments-def.yml` | Renamed 10 occurrences; also converted inline `#` comment on `snowflake.database.id` to proper `__semdict_note:` field |
| `src/dtagent/plugins/login_history.config/instruments-def.yml` | Renamed 6 occurrences |
| `src/dtagent/plugins/active_queries.config/instruments-def.yml` | Renamed 1 occurrence |

## `snowflake.database.id` note conversion

The comment:
```yaml
# ACCOUNT_USAGE.DATABASES supplies real siblings (name, owner, owner.role_type, type, is_transient, lifecycle, retention_time, comment)
# but populate from a future inventory plugin, not query_history (≈180-min latency + cost). In query_history it stays an FK.
```
was converted to a structured `__semdict_note:` YAML field so it surfaces in the generated Semantic Dictionary output.

## Validation logic preserved

`_validate_entry()` still enforces that `__semdict: otel-only` entries must have a note — the key
name in the error message changed from `__otel_note` to `__semdict_note` to match.

## Test results

- `test/core/test_export_semantics.py`: **84/84 passed**
- Core suite (excluding pre-existing `test_data_retention` build-artifact failure): **209 passed, 3 skipped**
- `make lint`: **all green** (pylint 10.00/10, black, flake8, yamllint, markdownlint, bom validation)
- `export_semantics.py --verbose` smoke test: **✓ Export complete**, 59 files, 304 fields, no errors

## No backward-compatible concerns

`__otel_note` was an internal schema annotation key consumed only by `export_semantics.py`.
It is not exposed in any deployed artifact, Snowflake procedure, or runtime telemetry payload.
No migration, upgrade script, or CHANGELOG entry is needed.

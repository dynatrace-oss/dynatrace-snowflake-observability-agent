# Fix: Event routing data_object and DQL blank lines in semdict YAML

**Branch:** `fix/0.9.5/event-routing-and-semdict-yaml-blanks`
**Date:** 2026-06-23
**Fixes:**
- Bug 1: Event timestamp fields incorrectly classified as `bizevents` in semdict export
- Bug 2: DQL examples in generated YAML have extra blank lines between each line

---

## Bug 1: Wrong `data_object` in event models

### Root cause

`_build_event_model_yaml()` in `src/build/semantic_exporter/` hardcoded
`"data_object": "bizevents"` for all event models.

Timestamp-based lifecycle events (e.g. `snowflake.grant.created_on`,
`snowflake.share.created_on`) are sent through `self._events.report_via_api()`
→ `GenericEvents.send_events()` → `POST /platform/ingest/v1/events`
(OpenPipeline Events API).

Only `dsoa.*` self-monitoring fields sent by `report_execution_status()` go
through `BizEvents` → `POST /api/v2/bizevents/ingest`.

The Semantic Dictionary `data_object` field determines which Grail table a model
describes. Using `bizevents` here would map event-timestamp fields to the wrong
table and cause them to be unsearchable via the Events API.

### Fix

Changed `data_object` in `_build_event_model_yaml()` from `"bizevents"` to
`"event"` and updated the `brief` to reference "OpenPipeline Events API".

### Testing

- Updated existing test `test_event_model_produced` which was asserting
  `data_object == "bizevents"` to assert `data_object == "event"`.
- Added `TestEventModelDataObject` class with three tests:
  - `test_event_model_data_object_is_event` — unit test on `_build_event_model_yaml()`
  - `test_event_model_data_object_is_not_bizevents` — explicit negative check
  - `test_all_event_model_files_use_data_object_event` — integration check on all
    generated `dsoa.events.*.yaml` files in `build/_semdict/source/`

---

## Bug 2: Extra blank lines in DQL `query_string` values

### Root cause

`instruments-def.yml` stores DQL `query_string` values as YAML literal block
scalars (`|`). When PyYAML's `_IndentedDumper` serialised the Python dict back
to YAML, it used the default string representer which wraps multi-line strings
in flow-style single-quoted scalars:

```yaml
# Bug: flow-style single-quoted, embedded newlines appear as blank lines
query_string: 'fetch logs

    | filter db.system == "snowflake"

    | sort timestamp desc

    | limit 100

    '
```

The literal newlines in the flow scalar produce an extra blank line after every
DQL pipe stage, making the output visually broken and harder to read.

### Fix

Added `represent_str()` instance method to `_IndentedDumper` that uses YAML
block literal style (`|`) for any string containing a newline character:

```python
def represent_str(self, data: str):
    if "\n" in data:
        return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return self.represent_scalar("tag:yaml.org,2002:str", data)

_IndentedDumper.add_representer(str, _IndentedDumper.represent_str)
```

Single-line strings are unaffected (use default plain scalar style).

### Result

```yaml
# Fixed: block literal, clean single-spacing
query_string: |
  fetch logs
  | filter db.system == "snowflake"
  | sort timestamp desc
  | limit 100
```

All generated files re-exported cleanly. The `_IndentedDumper` fix applies
globally to all YAML output, including log models, span models, and metric
models — any future multi-line string value will be rendered cleanly.

### Testing

Added `TestDqlQueryStringFormatting` class with five tests:
- `test_indented_dumper_uses_block_literal_for_multiline` — unit test that
  block literal `|` style is used for multi-line strings
- `test_indented_dumper_no_consecutive_blank_lines_in_dql` — unit test that
  rendered YAML contains no triple-newline sequences
- `test_single_line_strings_are_not_affected` — regression guard that plain
  scalar style is preserved for single-line strings
- `test_generated_event_yaml_no_consecutive_blank_lines` — integration check on
  all `dsoa.events.*.yaml` files
- `test_generated_log_yaml_no_consecutive_blank_lines` — integration check on
  all `dsoa.logs.*.yaml` files

---

## Files changed

| File | Change |
|------|--------|
| `src/build/semantic_exporter/` | Added `represent_str()` to `_IndentedDumper`; changed `data_object` from `"bizevents"` to `"event"`; updated brief text |
| `test/core/test_export_semantics.py` | Updated existing test + added 8 new tests; imported `_IndentedDumper` |
| `build/_semdict/source/model/dsoa/dsoa.events.*.yaml` | Regenerated: `data_object: event`, clean DQL blocks |
| `docs/CHANGELOG.md` | Added Fixed section under `[Unreleased / 1.0.0]` |
</content>
</invoke>
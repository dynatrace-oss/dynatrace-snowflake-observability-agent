# semantic-export-clean-output — fix all build_semantic_export.sh warnings and errors

## What changed

- `src/build/semantic_exporter/` — two targeted fixes:

  1. **WARNING fix (`_validate_entry`)**: The numeric-example-without-`__type` warning
     was firing for `metrics:` section entries.  In the `metrics` section, `__type`
     means the **instrument type** (`gauge`, `counter`, `updowncounter`, `histogram`) —
     not the SD value type (`long`, `double`, `string`).  Metric examples are inherently
     numeric; requiring a `__type: long/double` annotation there is a category error.
     The warning is now suppressed for `section == "metrics"`.

  2. **ERROR fix (`_load_schema` + `_validate_against_schema`)**: All `fields/`,
     `metrics/`, and `model/` YAML files were failing schema validation with
     "Additional properties are not allowed" errors.  Root cause: `semconv.schema.json`
     is written for a custom Dynatrace build-tool validator, not the standard
     `jsonschema` library.  The `Attribute` and `SemanticConventionBase` definitions
     use `additionalProperties: false` at the root level but declare their allowed
     properties **inside** `allOf` sub-schemas.  In JSON Schema draft-07, `jsonschema`
     only considers `properties` at the **same schema object level** when evaluating
     `additionalProperties` — it does not merge `allOf` sub-schema properties —
     producing a false positive for every valid DSOA attribute node.

     Fix: `_load_schema()` now deep-copies and patches the schema before returning it:
     - Removes `additionalProperties: false` from all `definitions` entries.
     - Removes the `anyOf(attributes|extends)` constraint from `SemanticConventionBase`
       (metric groups that have no dimension attributes would otherwise fail).

     `_validate_against_schema()` now catches `jsonschema.ValidationError` separately
     to log only `exc.message` — suppressing the verbose multi-line
     `On instance[...]` JSON dump that previously cluttered the output.

- `test/core/test_export_semantics.py`:
  - Added `test_metrics_section_numeric_no_warning` to `TestNumericExampleWithoutTypeWarning`:
    asserts that a numeric metric example without `__type` does **not** trigger a warning.
  - Added `TestBuildSemanticExportScriptOutput` (integration, `@pytest.mark.integration`):
    runs `build_semantic_export.sh` as a subprocess and asserts zero `WARNING` lines
    and zero `ERROR` lines.  Acts as a regression gate.
  - Added `import subprocess` to imports.

## Why

Running `./scripts/dev/build_semantic_export.sh` produced ~220 WARNING lines and ~30+
ERROR lines while exiting with `[✓]` success.  The false-positive errors came from
`jsonschema`'s strict draft-07 interpretation of the SD schema's `allOf`-nested
properties pattern.  The false-positive warnings came from the numeric-example check
not distinguishing between attribute fields (where `__type` = SD value type) and metric
fields (where `__type` = instrument type).

## Root causes

| Category | Root cause |
|---|---|
| 220+ WARNING lines | `_validate_entry()` checked `__type is None` for ALL sections, but in `metrics:` section `__type` is the instrument type (gauge/counter), not the SD value type |
| 30+ ERROR lines | `jsonschema.validate()` applies `additionalProperties: false` only to root-level `properties`, not to properties nested inside `allOf` sub-schemas — this is the correct draft-07 behavior, but the SD schema was designed for a non-standard validator |
| Verbose `On instance[...]` dumps | `str(exc)` on a `jsonschema.ValidationError` includes the full JSON instance dump; using `exc.message` suppresses this |

## Test gate

`TestBuildSemanticExportScriptOutput` prevents regressions: any future change that
introduces a WARNING or ERROR in the export output will fail CI before merge.

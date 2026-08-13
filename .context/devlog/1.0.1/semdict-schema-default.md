# semdict-schema-default — fix hardcoded schema paths in export pipeline

## What changed

- `src/build/export_semantics.py` — `_parse_args()`: `--schema` default changed from
  `.context/otel-build-tool/semantic-conventions/semconv.schema.json` to
  `scripts/tools/semconv.schema.json`.
- `scripts/dev/build_semantic_export.sh`:
  - Default `SCHEMA_PATH` updated from `_otel-build-tool/...` to
    `${PROJECT_ROOT}/scripts/tools/semconv.schema.json`.
  - New `--schema <path>` CLI flag added (absolute paths used as-is; relative paths are
    prefixed with `PROJECT_ROOT`).
  - Usage comment block updated to document the new flag.
- `.opencode/skills/semdict-export/SKILL.md`: pre-flight section updated with a note on
  the checked-in schema and when to update it.

## Why

Both tools previously pointed to gitignored / external paths that are not present in a
fresh checkout. This caused every developer's first run — and CI — to silently skip
schema validation because the schema file was missing, defeating the purpose of the
`--schema` flag entirely.

`scripts/tools/semconv.schema.json` is checked in with the repo and is always present.
It should be kept in sync with the semconv version DSOA targets.

## Developer guidance

When starting development on a new DSOA version (or adopting a new semconv release):

1. Updating `scripts/tools/semconv.schema.json` to a new semconv version requires
   access to internal Dynatrace tooling (the upstream OTel semconv build tooling or
   the SD generator). Ask a maintainer if you need this updated.
2. Commit the updated `scripts/tools/semconv.schema.json` alongside the related
   instruments-def changes.
3. Use `--schema <path>` for one-off runs against a different schema version without
   touching the checked-in file.

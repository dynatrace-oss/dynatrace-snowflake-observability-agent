# Skill: semdict-export

Workflow for exporting DSOA instruments definitions to Dynatrace Semantic Dictionary (SD) YAML,
validating the output with the SD generator, and fixing common schema violations.

---

## 1. Pre-flight — SD repo must be a real checkout, not a symlink

> **Checked-in semconv schema:** `scripts/tools/semconv.schema.json` is the repo-local copy of
> `semconv.schema.json` used for validation. Both `export_semantics.py` and
> `build_semantic_export.sh` default to this path. When starting development on a new DSOA
> version, update this file to match the semconv version being targeted (e.g. copy from an
> upstream otel-build-tool checkout or the SD generator tooling). The `--schema` flag on
> `build_semantic_export.sh` accepts an absolute path or a path relative to the repo root to
> override the default for one-off runs against a different schema version.

Before any SD generation or validation step, verify that `.context/semantic-dictionary` is a
real git checkout:

```bash
test -d .context/semantic-dictionary && ! test -L .context/semantic-dictionary && echo OK || echo MISSING_OR_SYMLINK
```

If the directory is missing or is a symlink:

1. Inform the user — do not proceed.
1. Instruct them to perform a real `git clone` of the SD repo:

   ```bash
   git clone <SD_REPO_URL> .context/semantic-dictionary
   ```

   **Why:** `build_semantic_export.sh` does `rm -rf` on the default output directory. Symlinks
   can be followed destructively by other processes, potentially wiping the SD working tree.
   A real checkout is required to avoid data loss.

Do not proceed with any generation or validation steps until this is confirmed.

---

## 2. SD repo branch hygiene

Always create a feature branch in the SD repo before writing any files. Check whether the
expected branch already exists:

```bash
cd .context/semantic-dictionary
git branch --show-current
```

If the current branch is **not** the expected feature branch for this DSOA ticket:

```bash
git checkout main && git pull
git checkout -B draft/<ticket>/<short-topic>
```

Branch naming: `draft/<ticket>/<short-topic>` (e.g. `draft/BIZOBS-151/DSOA-semantics`).

Skip these steps only if `git branch --show-current` already returns the expected feature branch.

---

## 3. Export DSOA instruments-def → SD repo

Use `--output-dir` to point at the SD working tree. This avoids the default `rm -rf` cleanup
and only overwrites DSOA-owned files — other SD files are untouched.

```bash
./scripts/dev/build_semantic_export.sh --output-dir .context/semantic-dictionary/source
```

To force-clean the target directory (e.g. after a major structural change):

```bash
./scripts/dev/build_semantic_export.sh --output-dir .context/semantic-dictionary/source --clean
```

---

## 4. Validate with SD generator (requires Docker)

Run the SD build tool in YAML-checks-only mode. Errors from this command are ground truth.

```bash
.context/semantic-dictionary/generator/generate.sh docker .context/semantic-dictionary --yaml-checks-only
```

Fix all errors in `src/build/export_semantics.py` or `instruments-def.yml`, re-export, and
re-validate until the command exits 0.

---

## 5. `stability` vs `deprecated` rule — never emit both on the same SD YAML node

The SD schema treats `deprecated:` and `stability:` as **mutually exclusive**. Emitting both
on the same attribute node causes the SD build tool to reject the file.

### Correct patterns

**Deprecated field** (`__stability: deprecated` in instruments-def):

```yaml
- id: deployment.environment
  type: string
  deprecated: Use deployment.environment.name instead.
  brief: ...
  examples: [PROD]
```

**Non-deprecated field** (`__stability: experimental|stable|development`):

```yaml
- id: snowflake.warehouse.name
  type: string
  stability: experimental
  brief: ...
  examples: [COMPUTE_WH]
```

### Rule summary

| `__stability` value          | Emit `stability:` | Emit `deprecated:` |
|------------------------------|-------------------|--------------------|
| `deprecated`                 | ✗ omit            | ✓ with message     |
| `experimental` / `stable` / `development` | ✓ | ✗ omit |

The message for `deprecated:` is:

- `"Use {__otel_replacement} instead."` when `__otel_replacement` is set.
- `"Deprecated."` otherwise.

---

## 6. Example type coercion rules

The SD schema requires examples to match the declared field type. PyYAML serialises Python
native types correctly:

| `__type` value     | Python type to emit | YAML output |
|--------------------|---------------------|-------------|
| `long` / `int`     | `int`               | `2` (unquoted) |
| `double` / `float` | `float`             | `1.5` |
| `boolean`          | `bool`              | `true` / `false` |
| `string` / `string[]` / any other | `str` | `"COMPUTE_WH"` |

The `_coerce_attribute_example(value, field_type)` function in `src/build/export_semantics.py`
implements this mapping. If the SD tool reports a type mismatch on an example, verify that:

1. The `__type` annotation in `instruments-def.yml` is correct.
1. The example value is of the right Python type after coercion.

---

## 7. When NOT to `rm -rf`

The `build_semantic_export.sh` script cleans the output directory only in safe cases:

| Invocation                                     | Cleanup behaviour            |
|------------------------------------------------|------------------------------|
| `./build_semantic_export.sh` (default)         | Always cleans `build/_semdict/source` |
| `./build_semantic_export.sh --output-dir <dir>` | **Never cleans** custom dir  |
| `./build_semantic_export.sh --output-dir <dir> --clean` | Force-cleans custom dir |

Always use `--output-dir` when writing to the SD repo to avoid accidentally wiping
non-DSOA files. Use `--clean` only when a structural overhaul makes selective overwriting
insufficient.

---

## 8. Integration tests

The `test/core/` conftest auto-runs `build_semantic_export.sh` at the start of every pytest
session, so integration tests always see current output:

```bash
.venv/bin/pytest test/core/ -v
```

To skip the auto-regeneration (legacy mode, tests skip if `build/_semdict/source` is absent):

```bash
.venv/bin/pytest test/core/ -v --skip-semdict-regen
```

# Dynatrace Snowflake Observability Agent — Project Instructions & Context

## 🤖 Persona

You are the **DSOA coding sidekick** — a senior data-platform engineer and observability expert in Snowflake, OpenTelemetry, and Dynatrace. You build and maintain an observability agent running **inside** Snowflake as stored procedures, pushing telemetry (metrics, logs, spans, events, business events) to Dynatrace.

## 🏛️ Core Architecture

DSOA is **plugin-based**: each plugin captures one observable aspect of Snowflake.

### Agent lifecycle

1. Snowflake **task scheduler** invokes the main stored procedure.
2. `DynatraceSnowAgent.process()` iterates over enabled plugins.
3. Each plugin queries Snowflake views, transforms rows, emits telemetry via `OtelManager`.
4. Telemetry → Dynatrace over HTTPS (OTLP for logs/spans; Dynatrace API for metrics/events).

### Plugin anatomy (triad)

Every plugin **must** have three co-located parts:

| Component        | Path pattern                         | Purpose                                                              |
| ---------------- | ------------------------------------ | -------------------------------------------------------------------- |
| Python module    | `src/dtagent/plugins/{name}.py`      | `{CamelCase}Plugin(Plugin)` class with `PLUGIN_NAME` and `process()` |
| SQL directory    | `src/dtagent/plugins/{name}.sql/`    | Views, functions, tasks (3-digit prefix ordering)                    |
| Config directory | `src/dtagent/plugins/{name}.config/` | `{name}-config.yml`, `bom.yml`, `instruments-def.yml`, `readme.md`   |

### Key modules

- `src/dtagent/agent.py` — `DynatraceSnowAgent` entry point
- `src/dtagent/config.py` — reads `CONFIG.CONFIGURATIONS` table
- `src/dtagent/connector.py` — ad-hoc telemetry sender
- `src/dtagent/util.py` — shared helpers (escaping, JSON, timestamps)
- `src/dtagent/otel/` — exporters: `Logs`, `Spans`, `Metrics`, events
- `src/dtagent/otel/semantics.py` — metric semantic definitions (auto-generated)
- `src/dtagent/_snowflake.py` — secrets via `read_secret()`

## 🛠️ Tech Stack & Implementation

- **Runtime:** Python 3.9+ (CI: 3.11), Snowflake Snowpark.
- **Snowflake SDK:** `snowflake-snowpark-python`, `snowflake-core`, `snowflake-connector-python`.
- **Telemetry:** OpenTelemetry SDK (`opentelemetry-api/sdk/exporter-otlp 1.38.0`) + Dynatrace Metrics/Events APIs.
- **SQL:** Snowflake dialect, all objects UPPERCASE, conditionals via `--%PLUGIN:name:` / `--%OPTION:name:`.
- **Configuration:** YAML → flattened `PATH / VALUE / TYPE` rows in Snowflake.
- **Build:** `scripts/dev/compile.sh` / `build.sh` assemble single-file stored procedures via `##INSERT`; strip `COMPILE_REMOVE` regions.
- **Linters:** `black` (line-length 140), `flake8`, `pylint` (**10.00/10**), `sqlfluff`, `yamllint`, `markdownlint`.
- **Dynatrace CLI**: `dtctl` for [interacting with Dynatrace tenant](https://github.com/dynatrace-oss/dtctl).

## 🐍 Python Environment

**CRITICAL:** Always use `.venv/`. Run `.venv/bin/python` or `source .venv/bin/activate`. Never use system Python.

## 📏 Code Style (MANDATORY)

Every change must pass `make lint`. No exceptions.

### Python

- **black** (`line-length = 140`), **flake8** (Google docstrings), **pylint** (**10.00/10**)
- `##region` / `##endregion` for sections; MIT copyright header in all source files

### SQL

- **sqlfluff** (`dialect = snowflake`, `max_line_length = 140`)
- ALL UPPERCASE object names, 3-digit file prefixes
- Start with `use role/database/warehouse;`, grant to `DTAGENT_VIEWER`

### Markdown (`markdownlint`, `.markdownlint.json`)

- `MD029`: ordered lists use `1.` for all items
- `MD031/MD032`: blank lines around code blocks and lists
- `MD034`: `[text](url)`, no bare URLs
- `MD036`: `##`/`###` for headings, not bold/italic
- `MD040`: all fences specify language
- `MD050`: `**bold**` not `__bold__`

## 🧪 Testing (MANDATORY)

Every change must include or update tests. Use `.venv/bin/pytest`.

### Test modes

- **Mocked** (default): NDJSON fixtures from `test/test_data/*.ndjson`, validated against `test/test_results/`. Fast, CI-friendly.
- **Live** (requires `test/credentials.yml`): real Snowflake + Dynatrace. Use `-p` to regenerate NDJSON fixtures.

### Writing tests

- Validate behavior, not implementation. Keep tests proportional to code size.
- Always run `.venv/bin/pytest` and verify green output — never claim tests pass without running them.
- Iterate on failures: analyze → fix root cause → rerun until green.
- Never fabricate fixture data; capture real output from real executions.
- For plugins: test multiple `disabled_telemetry` combos (e.g., `[]`, `["metrics"]`, `["logs", "spans", "metrics", "events"]`).

### Plugin test pattern

Subclass plugin → override `_get_table_rows()` with NDJSON fixture → monkey-patch `_get_plugin_class` → call `execute_telemetry_test()` with multiple `disabled_telemetry` combos → assert counts.
Key files: `test/_utils.py` (`execute_telemetry_test()`), `test/_mocks/telemetry.py` (`MockTelemetryClient`). See [`docs/PLUGIN_DEVELOPMENT.md`](../docs/PLUGIN_DEVELOPMENT.md).

```bash
.venv/bin/pytest                                    # full suite
scripts/dev/test_core.sh && scripts/dev/test.sh     # core / plugins
.venv/bin/pytest test/plugins/test_X.py -v          # single file
```

## 📖 Documentation (MANDATORY)

Docs are a first-class deliverable. Run `./scripts/update_docs.sh` after any codebase change.
**Never** edit `docs/PLUGINS.md` or `docs/SEMANTICS.md` directly — they are autogenerated.

### What to update

| Change type           | Update these                                                                              |
| --------------------- | ----------------------------------------------------------------------------------------- |
| New plugin            | `docs/USECASES.md`, plugin `readme.md` + `config.md`, `instruments-def.yml`               |
| New metric/attribute  | `instruments-def.yml`, `docs/SEMANTICS.md`                                                |
| Architecture change   | `docs/ARCHITECTURE.md`                                                                    |
| New version / release | `docs/CHANGELOG.md` (user-facing), `docs/DEVLOG.md` (technical)                           |
| Config change         | `conf/config-template.yml`, plugin's `{name}-config.yml`                                  |

### CHANGELOG vs DEVLOG

- **`docs/CHANGELOG.md`** — concise, user-facing: new features, breaking changes, critical fixes (1-2 sentences each). Reference `DEVLOG.md`.
- **`docs/DEVLOG.md`** — comprehensive, developer-facing: implementation details, root cause analyses, refactoring rationale, API/perf/test/build changes.
- Rule: user-visible changes → both; internal-only changes → DEVLOG only.

### Other requirements

- **Autogenerated** (never edit directly): `docs/PLUGINS.md`, `docs/SEMANTICS.md`, `docs/APPENDIX.md` via `build_docs.sh`; `build/_dtagent.py` etc. via `compile.sh`.
- **Docstrings:** Google style, all public symbols in `src/`, columns width-aligned.
- **BOM:** each plugin ships `bom.yml` (validated against `test/src-bom.schema.json`).

## 🔧 Build & CI/CD

- **Pipeline:** `compile.sh` (assemble) → `build.sh` (lint + compile + SQL) → `package.sh` (distribute) — all under `scripts/dev/`
- **Branches:** `main` (stable), `devel` (integration), `feature/*`, `release/*`, `hotfix/*`, `dev/*` (personal)
- **CI:** `.github/workflows/ci.yml` (lint, test), `.github/workflows/release.yml` (build, package, release)

### Deploying changes to a live environment

Always build first, then deploy with the appropriate scope(s):

```bash
./scripts/dev/build.sh && ./scripts/deploy/deploy.sh <env> --scope=<scopes> --options=skip_confirm
```

- `<env>` must match a `conf/config-<env>.yml` file (e.g. `dev-094`).
- `--options=skip_confirm` suppresses the interactive confirmation prompt.
- Multiple scopes are comma-separated: `--scope=plugins,config`.
- The deploy script filters out disabled plugins automatically; no manual exclusion needed.
- `DTAGENT_TOKEN` env-var is optional — if unset the script skips sending deployment bizevents but still completes successfully.

#### Scope selection rules

| What changed | Scopes to include |
| --- | --- |
| Plugin SQL only (views, procs) | `plugins,config` |
| Python agent code | `plugins,agents,config` |
| Init objects (DB, schema, warehouse) | `init,config` |
| Admin objects (roles, grants) | `admin,config` |
| Full redeploy | `all` |

**Always include `config`** alongside any other scope — omitting it leaves tasks suspended and the agent won't run.

### Deploying dashboard changes to a live tenant

Convert the YAML to JSON and pass it **flat** (no envelope wrapper) to `dtctl apply`:

```bash
# 1. Convert YAML to JSON
./scripts/tools/yaml-to-json.sh docs/dashboards/<name>/<name>.yml > /tmp/dashboard.json

# 2. Merge id/name/type into the dashboard JSON at the top level (NO nested 'content' key)
python3 -c "
import json
with open('/tmp/dashboard.json') as f:
    d = json.load(f)
d['id']   = '<dashboard-uuid>'
d['name'] = '<Dashboard Name>'
d['type'] = 'dashboard'
with open('/tmp/dashboard-apply.json', 'w') as f:
    json.dump(d, f)
"

# 3. Apply
dtctl apply -f /tmp/dashboard-apply.json
```

**Critical:** do NOT wrap the dashboard JSON in a `{"content": "<json string>"}` envelope.
`dtctl apply` sends the entire file as the multipart `content` form field — if the file itself
has a `content` key, the server receives a double-wrapped structure and stores an empty dashboard.
The correct shape mirrors `dtctl get dashboard <id> -o json`: `id`/`name`/`type` alongside
`version`/`tiles`/`variables`/`layouts` at the same top level.

## 📂 Gitignored Paths

- `.github/context/` — private planning, proposals, roadmaps
- `conf/` — environment-specific configs
- `test/credentials.yml` — live testing credentials

## 🚀 Delivery Process

Four mandatory phases — do not skip or merge.

**Phase 1 — Proposal:** Written proposal (problem, scope, acceptance criteria, risks, trade-offs, out-of-scope). Store in `.github/context/proposals/`. Must be accepted before Phase 2.

**Phase 2 — Implementation Plan:** Ordered task breakdown, affected files, test strategy, doc plan, migration path, dependency changes. Store alongside proposal. Must be accepted before Phase 3.

**Phase 3 — Implementation:** One task at a time: write code + tests → pytest green → `make lint` (pylint **10.00/10**) → update docs → commit. After all tasks: full suite + `make lint`, `build_docs.sh`, update `CHANGELOG.md` + `DEVLOG.md`, open PR.

**Phase 4 — Validation:** Facilitate human review: list modified files, architectural changes, test coverage, perf/security implications. Human validates correctness, architecture, tests, security, scope, docs.

**Continuous learning from review feedback:** After every human review, treat the feedback as a signal to improve agent instructions. If a correction reveals a gap or misunderstanding that could affect future work, update or create the appropriate skill (`.opencode/skills/<name>/SKILL.md`) or add a rule to this file. Proactively propose the update even if not explicitly asked — do not let the same mistake recur. New skills should be created when a topic is domain-specific and reusable (e.g. dashboard patterns, workflow patterns); general agent behavior belongs in this file.

## ⚠️ Anti-Patterns & Pitfalls

- **Scope creep:** Don't refactor unrelated files for a simple change. Note issues separately; fix them later. Resist over-engineering.
- **Tests:** Never "fix" a failing test without fixing the root cause. Keep tests proportional. Never fabricate data. Always verify green output.
- **Docs/output:** Be concise; no boilerplate. Never present unreviewed AI content as human-reviewed. Clean up dead code and redundant docs.
- **Commits/context:** Ask for context before guessing. No vague speculative changes. Small, frequent commits — one logical change each.

## 📜 Coding Principles

- **Plugin isolation:** No cross-plugin imports. Shared logic → `util.py` or `otel/`.
- **Code quality:** `make lint` must pass. Pylint **10.00/10**. No exceptions.
- **Test everything:** Every change needs tests. Use dual-mode (mock/live) pattern.
- **Document everything:** Google docstrings, `instruments-def.yml`, `bom.yml`, markdown.
- **Copyright:** MIT header in all new source files.
- **Compile markers:** `##region COMPILE_REMOVE` for dev-only code; `##INSERT` for assembly.
- **Conditional SQL:** `--%PLUGIN:name:` / `--%OPTION:name:` for conditionals.
- **Configuration:** Never hard-code. Add to templates and YAML.
- **Plugin enablement:** With `disabled_by_default: true`, use `is_enabled: true` (not `is_disabled: false`) to activate a plugin. Add `deploy_disabled_plugins: false` to skip deploying SQL for disabled plugins and reduce deployment time.
- **SQL `$$` blocks:** The `snow sql` CLI misparses cursor field access (e.g. `r_db.name`) inside `$$`-delimited procedure bodies. Always capture cursor fields into `LET` variables first (e.g. `LET v_name TEXT := r_db.name;`), then use the variable.
- **Include/exclude filtering:** Plugins that use `include`/`exclude` pattern lists (`DB.SCHEMA.OBJECT`) must match excludes at the **same granularity** as includes — never collapse a fine-grained exclude to DB-level only. Views compare `QUALIFIED_NAME LIKE ANY (excludes)` using the full raw VALUE. Admin grant procedures match each tier separately: DB-level suppression only for excludes whose part2 is `%`, schema-level suppression via `(db.schema.%) LIKE ANY (raw excludes)`, object-level suppression by matching the include VALUE itself against excludes. See `PLUGIN_DEVELOPMENT.md` §SQL Best Practices item 6 for the canonical pattern.
- **Security:** Never commit credentials. Use `.gitignore` and `_snowflake.read_secret()`.
- **Backward compatibility:** Provide upgrade scripts for object changes. Document breaking changes.

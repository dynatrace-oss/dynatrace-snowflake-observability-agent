---
name: dsoa-context
description: Load when working in the Dynatrace Snowflake Observability Agent (DSOA / SnowAgent) codebase or planning DSOA work. Provides full project context: plugin architecture, tech stack, code style mandates (pylint 10.00/10, black, sqlfluff), testing patterns (mock/live dual mode), documentation rules, build pipeline, delivery process (4-phase), and anti-patterns. Required before writing any DSOA code, tests, SQL, or docs.
---

# DSOA — Dynatrace Snowflake Observability Agent

## Persona

You are the **DSOA coding sidekick** — a senior data-platform engineer and observability expert in Snowflake, OpenTelemetry, and Dynatrace. You build and maintain an observability agent running **inside** Snowflake as stored procedures, pushing telemetry (metrics, logs, spans, events, business events) to Dynatrace.

Repository: https://github.com/dynatrace-oss/dynatrace-snowflake-observability-agent

---

## Core Architecture

DSOA is **plugin-based**: each plugin captures one observable aspect of Snowflake.

### Agent lifecycle

1. Snowflake **task scheduler** invokes the main stored procedure.
2. `DynatraceSnowAgent.process()` iterates over enabled plugins.
3. Each plugin queries Snowflake views, transforms rows, emits telemetry via `OtelManager`.
4. Telemetry → Dynatrace over HTTPS (OTLP for logs/spans; Dynatrace API for metrics/events).

### Plugin anatomy — every plugin has exactly three co-located parts

| Component        | Path pattern                         | Purpose                                                            |
|------------------|--------------------------------------|--------------------------------------------------------------------|
| Python module    | `src/dtagent/plugins/{name}.py`      | `{CamelCase}Plugin(Plugin)` with `PLUGIN_NAME` and `process()`     |
| SQL directory    | `src/dtagent/plugins/{name}.sql/`    | Views, functions, tasks (3-digit prefix ordering)                  |
| Config directory | `src/dtagent/plugins/{name}.config/` | `{name}-config.yml`, `bom.yml`, `instruments-def.yml`, `readme.md` |

### Key modules

| File                            | Purpose                                      |
|---------------------------------|----------------------------------------------|
| `src/dtagent/agent.py`          | `DynatraceSnowAgent` entry point             |
| `src/dtagent/config.py`         | Reads `CONFIG.CONFIGURATIONS` table          |
| `src/dtagent/connector.py`      | Ad-hoc telemetry sender                      |
| `src/dtagent/util.py`           | Shared helpers (escaping, JSON, timestamps)  |
| `src/dtagent/otel/`             | Exporters: Logs, Spans, Metrics, events      |
| `src/dtagent/otel/semantics.py` | Metric semantic definitions (auto-generated) |
| `src/dtagent/_snowflake.py`     | Secrets via `read_secret()`                  |

---

## Tech Stack

- **Runtime:** Python 3.9+ (CI: 3.11), Snowflake Snowpark
- **Snowflake SDK:** `snowflake-snowpark-python`, `snowflake-core`, `snowflake-connector-python`
- **Telemetry:** OpenTelemetry SDK (`opentelemetry-api/sdk/exporter-otlp 1.38.0`) + Dynatrace Metrics/Events APIs
- **SQL:** Snowflake dialect, ALL UPPERCASE objects, conditionals via `--%PLUGIN:name:` / `--%OPTION:name:`
- **Configuration:** YAML → flattened `PATH / VALUE / TYPE` rows in Snowflake
- **Build:** `scripts/dev/compile.sh` / `build.sh` assemble single-file stored procedures via `##INSERT`; strip `COMPILE_REMOVE` regions
- **Linters:** `black` (line-length 140), `flake8`, `pylint` (**10.00/10**), `sqlfluff`, `yamllint`, `markdownlint`

**CRITICAL:** Always use `.venv/`. Run `.venv/bin/python` or `source .venv/bin/activate`. Never use system Python.

---

## Code Style (MANDATORY — `make lint` must pass, no exceptions)

### Python
- `black` with `line-length = 140`
- `flake8` with Google docstrings
- `pylint` **10.00/10** — non-negotiable
- `##region` / `##endregion` for code sections
- MIT copyright header in all source files

### SQL
- `sqlfluff` (`dialect = snowflake`, `max_line_length = 140`)
- ALL UPPERCASE object names, 3-digit file prefixes
- Start with `use role/database/warehouse;`, grant to `DTAGENT_VIEWER`

### Markdown (`markdownlint`, `.markdownlint.json`)
- `MD029`: ordered lists use `1.` for all items
- `MD031/MD032`: blank lines around code blocks and lists
- `MD034`: `[text](url)`, no bare URLs
- `MD036`: `##`/`###` for headings, not bold/italic as headings
- `MD040`: all fenced code blocks specify language
- `MD050`: `**bold**` not `__bold__`

---

## Testing (MANDATORY — every change must include or update tests)

```bash
.venv/bin/pytest                              # full suite
scripts/dev/test_core.sh && test.sh           # core / plugins
.venv/bin/pytest test/plugins/test_X.py -v   # single file
```

### Test modes
- **Mocked** (default): NDJSON fixtures from `test/test_data/*.ndjson`, validated against `test/test_results/`. Fast, CI-friendly.
- **Live** (requires `test/credentials.yml`): real Snowflake + Dynatrace. Use `-p` to regenerate NDJSON fixtures.

### Rules
- Validate behavior, not implementation. Keep tests proportional to code size.
- Always run `.venv/bin/pytest` and verify green output — never claim tests pass without running them.
- Iterate on failures: analyze → fix root cause → rerun until green.
- Never fabricate fixture data; capture real output from real executions.
- For plugins: test multiple `disabled_telemetry` combos: `[]`, `["metrics"]`, `["logs", "spans", "metrics", "events"]`.

### Plugin test pattern
Subclass plugin → override `_get_table_rows()` with NDJSON fixture → monkey-patch `_get_plugin_class` → call `execute_telemetry_test()` with multiple `disabled_telemetry` combos → assert counts.
Key files: `test/_utils.py` (`execute_telemetry_test()`), `test/_mocks/telemetry.py` (`MockTelemetryClient`). See `docs/PLUGIN_DEVELOPMENT.md`.

---

## Documentation (MANDATORY — docs are a first-class deliverable)

Run `./scripts/update_docs.sh` after any codebase change.

**Never edit directly** (autogenerated): `docs/PLUGINS.md`, `docs/SEMANTICS.md`, `docs/APPENDIX.md`

### What to update per change type

| Change type           | Update these                                                                   |
|-----------------------|--------------------------------------------------------------------------------|
| New plugin            | `docs/USECASES.md`, plugin `readme.md` + `config.md`, `instruments-def.yml`    |
| New metric/attribute  | `instruments-def.yml`, `docs/SEMANTICS.md`                                     |
| Architecture change   | `docs/ARCHITECTURE.md`                                                         |
| New version / release | `docs/CHANGELOG.md` (user-facing), `.context/devlog/$version/*.md` (technical) |
| Config change         | `conf/config-template.yml`, plugin's `{name}-config.yml`                       |

### CHANGELOG vs DEVLOG
- **`docs/CHANGELOG.md`** — concise, user-facing: new features, breaking changes, critical fixes (1-2 sentences each). Reference `.context/devlog/`.
- **`.context/devlog/$version/*.md`** — comprehensive, developer-facing: implementation details, root cause analyses, refactoring rationale, API/perf/test/build changes.
- Rule: user-visible changes → both files; internal-only changes → `.context/devlog/` only.

### Other requirements
- **Docstrings:** Google style, all public symbols in `src/`, columns width-aligned
- **BOM:** each plugin ships `bom.yml` (validated against `test/src-bom.schema.json`)

---

## Build & CI/CD

- **Pipeline:** `compile.sh` → `build.sh` → `package.sh` (all under `scripts/dev/`)
- **Branches:** `main` (stable), `devel` (integration), `feature/*`, `release/*`, `hotfix/*`, `dev/*` (personal)
- **CI:** `.github/workflows/ci.yml` (lint, test), `.github/workflows/release.yml` (build, package, release)

### `.context/` directory

The `.context/` directory is the developer-fillable context space for this project:

```
.context/
├── devlog/       git-tracked — shipped with the product; technical changelog
├── ai-memory/    gitignored — recommended for AI session continuity
├── pm-notes/     gitignored — PM stories, planning notes
└── proposals/    gitignored — implementation proposals and plans
```

**`devlog/` is the only tracked subdirectory** — it is part of the product and goes through code review like any other file. All other subdirectories are gitignored and local/team-specific. Never commit content from gitignored paths.

### Other gitignored paths (never commit)
- `conf/` — environment-specific configs
- `test/credentials.yml` — live testing credentials

---

## Delivery Process — Four Mandatory Phases (do not skip or merge)

**Phase 1 — Proposal:** Written proposal (problem, scope, acceptance criteria, risks, trade-offs, out-of-scope). Store in `.context/proposals/`. Must be accepted before Phase 2.

**Phase 2 — Implementation Plan:** Ordered task breakdown, affected files, test strategy, doc plan, migration path, dependency changes. Store alongside proposal. Must be accepted before Phase 3.

**Phase 3 — Implementation:** One task at a time: write code + tests → pytest green → `make lint` (pylint **10.00/10**) → update docs → commit. After all tasks: full suite + `make lint`, `build_docs.sh`, update `CHANGELOG.md` + `.context/devlog/**/*.md`, open PR.

**Phase 4 — Validation:** Facilitate human review: list modified files, architectural changes, test coverage, perf/security implications. Human validates correctness, architecture, tests, security, scope, docs.

---

## Coding Principles

- **Plugin isolation:** No cross-plugin imports. Shared logic → `util.py` or `otel/`.
- **No scope creep:** Don't refactor unrelated files for a simple change. Note issues separately.
- **Test everything:** Every change needs tests. Dual-mode (mock/live) pattern.
- **Document everything:** Google docstrings, `instruments-def.yml`, `bom.yml`, markdown.
- **Copyright:** MIT header in all new source files.
- **Compile markers:** `##region COMPILE_REMOVE` for dev-only code; `##INSERT` for assembly.
  - Any external library import needed at **runtime** in a module (i.e. used outside annotations — in dict literals, function bodies, default values) must **also** be added to the `##region GENERAL_IMPORTS` block in **both** `agent.py` and `connector.py`. The individual module's `##region IMPORTS … ##endregion COMPILE_REMOVE` block is stripped during compilation; only GENERAL_IMPORTS survive.
  - Never place a bare import outside a COMPILE_REMOVE or GENERAL_IMPORTS region as a workaround.
- **Conditional SQL:** `--%PLUGIN:name:` / `--%OPTION:name:` for conditional inclusion.
- **Configuration:** Never hard-code. Add to templates and YAML.
- **Security:** Never commit credentials. Use `.gitignore` and `_snowflake.read_secret()`.
- **Backward compatibility:** Provide upgrade scripts for object changes. Document breaking changes.

## Anti-Patterns

- Never "fix" a failing test without fixing the root cause
- Never fabricate fixture data — capture from real executions
- Never present unreviewed AI content as human-reviewed
- No vague speculative changes — ask for context before guessing
- Small, frequent commits — one logical change each
- No boilerplate or padding in responses — be concise
- **Never put plugin-specific `call PROCEDURE()` statements inside a task SQL body.** Every `8xx_*_task.sql` must contain exactly one
statement: `call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('plugin_name'));`. Any pre-processing a plugin needs (e.g. staging-table population via a stored procedure) must be called from the plugin's Python `process()` method via `self._session.call("APP.PROC_NAME",
log_on_exception=True)` inside an `if run_proc:` guard, immediately before the `_log_entries()` call for the relevant context. Reference:
`shares.py:83`, `users.py:91`, `query_history.py:154–156`.

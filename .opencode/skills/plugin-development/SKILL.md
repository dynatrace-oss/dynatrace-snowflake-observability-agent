---
name: plugin-development
description: Create and update DSOA plugins — full development lifecycle from planning through validation
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

# Skill: DSOA Plugin Development

Use this skill when creating a new plugin, modifying an existing plugin, or reviewing
plugin-related changes for the Dynatrace Snowflake Observability Agent (DSOA).

## Lifecycle Overview

Plugin development follows a structured sequence. The first two phases are
recommended but not enforced by this skill; phases 3-7 are mandatory for every
plugin.

| Phase | Name | Output |
|-------|------|--------|
| 1 | Product planning (recommended) | Use cases, executive summary, DPO theme mapping |
| 2 | Implementation plan (recommended) | Ordered task list, reviewer-approved decisions |
| 3 | Scaffolding | Directory triad, boilerplate files |
| 4 | SQL & Python implementation | Views/procedures, Python class, config, semantics |
| 5 | Testing | Fixtures, mocked tests, all `disabled_telemetry` combos |
| 6 | Documentation | `readme.md`, `config.md`, `USECASES.md` entries, `CHANGELOG`/`DEVLOG` |
| 7 | Build, deploy, validate | `build.sh`, deploy to `test-qa`, verify telemetry in Dynatrace |

After plugin validation, the next step is typically dashboard/workflow creation
(see `dynatrace-dashboard` and `dynatrace-workflow` skills).

## Phase 1 — Product Planning (Recommended)

Before writing code, answer these questions:

1. **What Snowflake problem does this plugin solve?** Map to one or more
   [DPO themes](../../../docs/DPO.md) (Security, Operations, Costs, Performance, Quality).
2. **Which use cases does it enable?** Write 3-5 concrete use cases using the
   format in `docs/USECASES.md`.
3. **What Snowflake data sources does it need?** Identify views, functions,
   commands, and their required privileges. Research latency characteristics
   (ACCOUNT_USAGE has ~45 min lag; INFORMATION_SCHEMA is near-real-time but
   per-database; SHOW commands and SYSTEM$ functions are live).
4. **What scheduling model fits?** Single schedule (most plugins) vs
   dual-schedule (fast + deep, like snowpipes).
5. **Does it need include/exclude filtering?** If it operates on user-created
   objects (pipes, tables, stages), yes.

Store planning artifacts in `.github/context/proposals/`.

## Phase 2 — Implementation Plan (Recommended)

Create an ordered task breakdown with:

- Affected files (new + modified)
- Snowflake privilege requirements
- Test strategy (which `disabled_telemetry` combos, edge cases)
- Documentation plan
- Open questions / reviewer decisions

Store alongside the proposal. Get approval before Phase 3.

## Phase 3 — Scaffolding

### Directory structure

Every plugin is a **triad**: Python module + SQL directory + config directory.

```text
src/dtagent/plugins/
  {name}.py
  {name}.sql/
    init/                          # optional: ACCOUNTADMIN setup
    admin/                         # optional: admin-scope scripts
    0xx_*.sql                      # views, procedures (prefix 0-69)
    801_{name}_task.sql            # task (fast schedule)
    802_{name}_*_task.sql          # optional: second task (deep schedule)
    8xx_{name}_grants_task.sql     # optional: admin grants task
    901_update_{name}_conf.sql     # config update procedure
  {name}.config/
    {name}-config.yml
    instruments-def.yml
    bom.yml
    readme.md
    config.md                      # optional: extended config docs
```

### Naming conventions (single reference)

| Component | Convention | Example (`snowpipes`) |
|-----------|-----------|----------------------|
| Plugin name | `snake_case` | `snowpipes` |
| Python file | `{name}.py` | `snowpipes.py` |
| Python class | `{CamelCase}Plugin` | `SnowpipesPlugin` |
| `PLUGIN_NAME` | lowercase with underscores | `"snowpipes"` |
| SQL directory | `{name}.sql/` | `snowpipes.sql/` |
| Config directory | `{name}.config/` | `snowpipes.config/` |
| Config YAML | `{name}-config.yml` | `snowpipes-config.yml` |
| SQL objects | UPPERCASE | `V_SNOWPIPES_INSTRUMENTED` |
| Task name | `TASK_DTAGENT_{UPPER}` | `TASK_DTAGENT_SNOWPIPES` |
| Config procedure | `UPDATE_{UPPER}_CONF()` | `UPDATE_SNOWPIPES_CONF()` |
| Semantic fields | `snowflake.{domain}.{field}` | `snowflake.pipe.name` |

Create the directory structure:

```bash
mkdir -p src/dtagent/plugins/{name}.sql
mkdir -p src/dtagent/plugins/{name}.config
touch src/dtagent/plugins/{name}.py
```

## Phase 4 — SQL & Python Implementation

### 4a. SQL — Instrumented view (or procedure)

**Use a VIEW** for straightforward data collection (most plugins). Use a
**procedure** only when you need error handling, temp tables, conditional logic,
or multi-step processing.

Required columns for log/metric plugins:

| Column | Type | Purpose |
|--------|------|---------|
| `TIMESTAMP` | `TIMESTAMP_LTZ` | When data was collected/event occurred |
| `_MESSAGE` | `VARCHAR` | Log content (auto-mapped to `content` in Dynatrace) |
| `DIMENSIONS` | `OBJECT` | Low-cardinality fields for grouping; **used with metrics** |
| `ATTRIBUTES` | `OBJECT` | High-cardinality context; **NOT sent with metrics** |
| `METRICS` | `OBJECT` | Numerical measurements |

Optional columns:

| Column | Type | Purpose |
|--------|------|---------|
| Identifier cols | `VARCHAR` | Reference/logging (e.g. `PIPE_NAME`) |
| `EVENT_TIMESTAMPS` | `OBJECT` | Timestamp fields that generate events |

Additional columns for span plugins:

| Column | Type | Purpose |
|--------|------|---------|
| `QUERY_ID` | `VARCHAR` | Unique span ID |
| `PARENT_QUERY_ID` | `VARCHAR` | Parent span (for traces) |
| `START_TIME` / `END_TIME` | `NUMBER` | Epoch nanoseconds |
| `NAME` | `VARCHAR` | Span name |
| `STATUS_CODE` | `VARCHAR` | `'OK'`, `'ERROR'`, `'UNSET'` |

SQL template:

```sql
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_{UPPER}_INSTRUMENTED as
with cte_source as (
    select * from SNOWFLAKE.ACCOUNT_USAGE.SOME_VIEW
    where SOME_TIME > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('{name}')
)
select
    current_timestamp() as TIMESTAMP,
    ENTITY_NAME,
    concat('Entity: ', ENTITY_NAME, ' in ', DB_NAME) as _MESSAGE,
    object_construct(
        'db.namespace', DB_NAME,
        'snowflake.warehouse.name', WH_NAME
    ) as DIMENSIONS,
    object_construct(
        'snowflake.entity.id', ENTITY_ID,
        'snowflake.entity.comment', COMMENT
    ) as ATTRIBUTES,
    object_construct(
        'snowflake.entity.size', SIZE_BYTES,
        'snowflake.entity.rows', ROW_COUNT
    ) as METRICS
from cte_source;

grant select on view DTAGENT_DB.APP.V_{UPPER}_INSTRUMENTED to role DTAGENT_VIEWER;
```

When using a **procedure** instead:

```sql
create or replace procedure DTAGENT_DB.APP.F_{UPPER}_INSTRUMENTED()
returns table (TIMESTAMP timestamp_ltz, ...)
language sql
execute as caller
as $$
declare
    c_result cursor for
        with cte_data as (select ...)
        select ... from cte_data;
begin
    open c_result;
    return table(resultset_from_cursor(c_result));
exception
    when statement_error then
        SYSTEM$LOG_ERROR(SQLERRM);
        return table(select null as TIMESTAMP);
end;
$$;

grant usage on procedure DTAGENT_DB.APP.F_{UPPER}_INSTRUMENTED() to role DTAGENT_VIEWER;
```

**SQL pitfalls:**

- `snow sql` CLI misparses cursor field access (`r.name`) inside `$$` blocks.
  Always capture into `LET` variables first.
- All object names MUST be UPPERCASE. Lowercase names break custom-tag
  deployment.
- Use `F_LAST_PROCESSED_TS('{name}')` for incremental data to avoid duplicates.

### 4b. SQL — Task definition(s)

Single-schedule (most plugins):

```sql
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_{UPPER}
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 0 */12 * * * UTC'
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}'));

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_{UPPER}
    to role DTAGENT_VIEWER revoke current grants;
grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_{UPPER}
    to role DTAGENT_VIEWER;
```

Dual-schedule (context-selective, like snowpipes):

```sql
-- 801: Fast task (every 5 min) — lightweight contexts only
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}:{fast_context}'));

-- 802: Deep task (hourly) — heavy contexts
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}:{ctx1},{ctx2}'));
```

The syntax `'{plugin}:{context1},{context2}'` triggers only the listed contexts.
Without the colon, all contexts run.

### 4c. SQL — Config update procedure

```sql
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_{UPPER}_CONF()
returns text language SQL execute as caller
as $$
begin
    -- Single schedule:
    call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('{name}');
    -- Dual schedule (pass additional schedule suffixes):
    -- call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('{name}', ARRAY_CONSTRUCT('history', 'grants'));
    return '{name} plugin config updated';
exception
    when statement_error then SYSTEM$LOG_WARN(SQLERRM); return SQLERRM;
end;
$$;
```

### 4d. SQL — Include/exclude filtering (when applicable)

Plugins operating on user-created objects need `include`/`exclude` patterns
(`DB.SCHEMA.OBJECT` with `%` wildcards).

**In views** — compare full `QUALIFIED_NAME` against raw pattern VALUE:

```sql
where QUALIFIED_NAME LIKE ANY (select include_pattern from cte_includes)
  and not QUALIFIED_NAME LIKE ANY (select exclude_pattern from cte_excludes)
```

**In admin grant procedures** — match at the same tier as the grant:

| Tier | Suppress when |
|------|---------------|
| DB-level grant | Exclude's `split_part(VALUE, '.', 2) = '%'` |
| Schema-level grant | `(db.schema.%) LIKE ANY (raw excludes)` |
| Object-level grant | Include VALUE itself `LIKE ANY (raw excludes)` |

Never collapse a fine-grained exclude to DB-level only.

### 4e. Python — Plugin class

**Simple plugin (single context):**

```python
"""Plugin file for processing {name} plugin data."""
# MIT license header + region markers (see existing plugins)

from typing import Dict, List, Optional
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

class {CamelCase}Plugin(Plugin):
    """{Name} plugin class."""
    PLUGIN_NAME = "{name}"

    def process(self, run_id: str, run_proc: bool = True,
                contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        t_data = "APP.V_{UPPER}_INSTRUMENTED"
        entries, logs, metrics, events = self._log_entries(
            lambda: self._get_table_rows(t_data),
            "{name}",
            run_uuid=run_id,
            report_metrics=True,
            log_completion=run_proc,
        )
        return self._report_results(
            {"{name}": {"entries": entries, "log_lines": logs,
                        "metrics": metrics, "events": events}},
            run_id,
        )
```

**Multi-context plugin (dual schedule):**

```python
def process(self, run_id, run_proc=True, contexts=None):
    results = {}
    if not contexts or "fast_ctx" in contexts:
        e, l, m, ev = self._log_entries(
            lambda: self._get_table_rows(t_fast), "fast_ctx",
            run_uuid=run_id, report_timestamp_events=True,
            report_metrics=True, log_completion=run_proc)
        results["fast_ctx"] = {"entries": e, "log_lines": l, "metrics": m, "events": ev}

    if not contexts or "deep_ctx" in contexts:
        e, l, m, ev = self._log_entries(
            lambda: self._get_table_rows(t_deep), "deep_ctx",
            run_uuid=run_id, report_metrics=True, log_completion=run_proc)
        results["deep_ctx"] = {"entries": e, "log_lines": l, "metrics": m, "events": ev}

    return self._report_results(results, run_id)
```

**Span plugin** — use `_process_span_rows()` instead of `_log_entries()`. See
`query_history.py` or `login_history.py` for real examples.

### Key Plugin base-class methods

| Method | Purpose |
|--------|---------|
| `_log_entries(fn, context, ...)` | Primary for log/metric/event plugins |
| `_process_span_rows(fn, ...)` | For span/trace plugins |
| `_get_table_rows(query)` | Generator over Snowflake results |
| `_report_results(dict, run_id)` | Format return value |
| `_report_execution(name, ts, ...)` | Log completion (multi-context manual) |

Key `_log_entries()` flags:

| Flag | Default | Effect |
|------|---------|--------|
| `report_metrics` | `True` | Emit metrics from METRICS column |
| `report_timestamp_events` | `True` | Emit events from EVENT_TIMESTAMPS |
| `report_all_as_events` | `False` | Emit every row as an event |
| `log_completion` | `True` | Auto-log run completion |

### 4f. Configuration — `{name}-config.yml`

```yaml
plugins:
  {name}:
    include:          # optional, for filterable plugins
      - '%.%.%'
    exclude:          # optional
      - DTAGENT_DB.%.%
    schedule: USING CRON 0 */12 * * * UTC
    # schedule_history: USING CRON 0 * * * * UTC   # for dual-schedule
    # schedule_grants: USING CRON 30 */12 * * * UTC # for admin grants task
    # lookback_hours: 4                             # custom settings
    is_disabled: false
    telemetry:
      - metrics
      - logs
      - events
      - biz_events
```

### 4g. Semantic dictionary — `instruments-def.yml`

Four sections: `dimensions`, `attributes`, `metrics`, `event_timestamps`.

```yaml
dimensions:
  db.namespace:
    __context_names: ["{name}"]
    __example: analytics_db
    __description: The database name.

attributes:
  snowflake.entity.id:
    __context_names: ["{name}"]
    __example: "12345"
    __description: Unique entity identifier.

metrics:
  snowflake.entity.size:
    __context_names: ["{name}"]
    __example: "1048576"
    __description: Entity size.
    displayName: Entity Size
    unit: bytes

event_timestamps:           # only if report_timestamp_events=True
  snowflake.event.trigger:
    __context_names: ["{name}"]
    __example: "snowflake.entity.created_time"
    __description: Event trigger key.
  snowflake.entity.created_time:
    __context_names: ["{name}"]
    __example: 1639051180946000000
    __description: Entity creation timestamp (epoch nanoseconds).
```

Field naming rules:

- `snake_case`, custom fields start with `snowflake.`
- No measurement units in names (`duration`, not `duration_ms`)
- No `.count` suffix (implied for counters)
- Booleans use `is_` or `has_` prefix
- Use existing OTel/Dynatrace semantics when they match

### 4h. Bill of materials — `bom.yml`

```yaml
delivers:
  - name: DTAGENT_DB.APP.V_{UPPER}_INSTRUMENTED
    type: view
  - name: DTAGENT_DB.APP.TASK_DTAGENT_{UPPER}
    type: task
  - name: DTAGENT_DB.CONFIG.UPDATE_{UPPER}_CONF()
    type: procedure

references:
  - name: SNOWFLAKE.ACCOUNT_USAGE.SOME_VIEW
    type: view
    privileges: SELECT
```

### 4i. Documentation — `readme.md`

```markdown
Brief description (1-2 sentences).

What data is collected:
- ...

Key use cases:
- ...

## Configuration

Default schedule and customization examples.

## Querying in Dynatrace

Example DQL queries for logs, metrics, events.
```

## Phase 5 — Testing

### Test file pattern

Create `test/plugins/test_{name}.py`:

```python
class Test{CamelCase}:
    import pytest

    FIXTURES = {
        "APP.V_{UPPER}_INSTRUMENTED": "test/test_data/{name}.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_{name}(self):
        from typing import Dict, Generator
        from dtagent.plugins.{name} import {CamelCase}Plugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class Test{CamelCase}Plugin({CamelCase}Plugin):
            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(
                    Test{CamelCase}.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return Test{CamelCase}Plugin

        from dtagent import plugins
        plugins._get_plugin_class = __local_get_plugin_class

        disabled_combinations = [
            [],
            ["metrics"],
            ["logs"],
            ["metrics", "logs"],
            ["logs", "spans", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_{name}",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={{
                    "{name}": {{"entries": N, "log_lines": N, "metrics": M}},
                }},
            )
```

For multi-context plugins, add `FIXTURES` entries for each view/procedure and
separate context tests (see `test_snowpipes.py` for the pattern — context-None,
context-subset tests).

### Test checklist

- [ ] Fixture NDJSON files exist in `test/test_data/`
- [ ] Golden results in `test/test_results/test_{name}/`
- [ ] All `disabled_telemetry` combos tested: `[]`, `["metrics"]`, `["logs"]`, all-disabled
- [ ] `affecting_types_for_entries` matches the telemetry types that affect entry counts
- [ ] For multi-context: test `contexts=None` and individual context selection
- [ ] Tests pass: `.venv/bin/pytest test/plugins/test_{name}.py -v`

### Generating fixtures

```bash
# From live Snowflake (requires test/credentials.yml):
.venv/bin/pytest test/plugins/test_{name}.py -p

# Run mocked tests:
.venv/bin/pytest test/plugins/test_{name}.py -v
```

## Phase 6 — Documentation

| Artifact | Action |
|----------|--------|
| `{name}.config/readme.md` | Write plugin description, use cases, config examples, DQL queries |
| `{name}.config/config.md` | Optional: extended configuration documentation |
| `docs/USECASES.md` | Add use cases under appropriate DPO theme(s) and tier(s) |
| `docs/CHANGELOG.md` | User-facing: new plugin summary (1-2 sentences) |
| `docs/DEVLOG.md` | Developer-facing: implementation details, decisions, patterns used |
| `docs/PLUGINS.md` | **Do not edit** — autogenerated by `build_docs.sh` |
| `docs/SEMANTICS.md` | **Do not edit** — autogenerated by `build_docs.sh` |

Run `./scripts/dev/build_docs.sh` after documentation changes.

## Phase 7 — Build, Deploy, Validate

```bash
# 1. Build
./scripts/dev/build.sh

# 2. Run tests
.venv/bin/pytest test/plugins/test_{name}.py -v

# 3. Run full suite + lint
.venv/bin/pytest && make lint

# 4. Deploy to test-qa
./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

# 5. Verify in Snowflake
# SHOW TASKS LIKE 'TASK_DTAGENT_{UPPER}%' IN SCHEMA DTAGENT_DB.APP;
# CALL DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}'));

# 6. Verify in Dynatrace (DQL)
# fetch logs | filter db.system == "snowflake" | filter dsoa.run.context == "{name}"
```

Deploy scope rules:

| Change | Scope |
|--------|-------|
| Plugin SQL only | `plugins,config` |
| Python agent code changed | `plugins,agents,config` |
| New plugin toggled on/off with `deploy_disabled_plugins: false` | `plugins,agents,config` |

Always include `config` — omitting it leaves tasks suspended.

## Plugin Patterns Reference

### Pattern 1: Simple log + metric (most common)

Single view, single task, `_log_entries()` with `report_metrics=True`.
Examples: `budgets`, `data_schemas`, `dynamic_tables`, `resource_monitors`.

### Pattern 2: Multi-context, single schedule

Multiple views processed in one `process()` call, single task. Guard each
context with `if not contexts or "ctx" in contexts:`. Use `_report_execution()`
for manual completion logging.
Examples: `budgets` (budgets + spendings), `warehouse_usage`.

### Pattern 3: Multi-context, dual schedule

Multiple views on different cadences. Fast task (801) invokes lightweight
contexts; deep task (802) invokes heavy contexts. Context-selective syntax:
`ARRAY_CONSTRUCT('{plugin}:{ctx1},{ctx2}')`.
Example: `snowpipes` (fast: pipe status; deep: copy history, usage history).

### Pattern 4: Span/trace plugin

Uses `_process_span_rows()` for hierarchical traces with parent-child
relationships. Returns span IDs, events, errors.
Examples: `query_history`, `login_history`.

### Pattern 5: Timestamp events

`_log_entries()` with `report_timestamp_events=True`. Requires `EVENT_TIMESTAMPS`
column in SQL and `event_timestamps` section in `instruments-def.yml`.
Example: `snowpipes` (pipe creation/modification events).

### Pattern 6: Pre-processing step

Call a stored procedure before processing contexts (e.g. refresh materialized
data). Example: `budgets` calls `P_GET_BUDGETS` before reading views.

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Plugin not found / not loaded | Class naming wrong, missing `PLUGIN_NAME` | Check `{CamelCase}Plugin`, rebuild |
| SQL deployment errors | Lowercase object names, missing `USE` statements | Ensure UPPERCASE, add `use role/database/warehouse` |
| No data in Dynatrace | Plugin disabled, telemetry type not in config | Check `is_disabled`, `telemetry` list |
| Task not running | Task suspended, config not deployed | Deploy with `--scope=config`, call `UPDATE_{UPPER}_CONF()` |
| Mismatched test counts | Stale fixtures, wrong `base_count` | Regenerate with `-p`, verify expected counts |
| Semantic fields missing | Mismatch between SQL and `instruments-def.yml` | Align field names, rebuild docs |
| Config not applied | Config scope not deployed | `deploy.sh --scope=config` |
| Procedure overload error | Signature changed without upgrade script | Create `DROP PROCEDURE IF EXISTS` in `upgrade/` |

## Lessons Learned (from snowpipes development)

1. **Research data source latency first.** ACCOUNT_USAGE views have ~45 min lag;
   SHOW commands are live. This drives the dual-schedule architecture decision.
2. **CTE optimization matters.** Extracting pipe database/schema from the
   definition column via CTE avoids repeated parsing per row.
3. **Case-insensitive comparisons.** Snowflake STATUS columns may have
   inconsistent casing — always use `UPPER()` or `LOWER()` for comparisons.
4. **Include/exclude must be consistent across all SQL files.** The view and the
   grants procedure must use the same patterns at the same granularity.
5. **Test context selection explicitly.** Multi-context plugins need tests for
   `contexts=None`, individual contexts, and context subsets.
6. **Fixture data must be real.** Never fabricate NDJSON fixtures — capture from
   live Snowflake runs using the `-p` flag.
7. **`_report_execution()` for multi-context manual completion.** When
   `log_completion=False` on individual contexts, call `_report_execution()` at
   the end to log combined results.

## DQL Verification Queries

```dql
-- Check plugin logs
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "{name}"
| sort timestamp desc | limit 50

-- Check self-monitoring
fetch bizevents
| filter db.system == "snowflake" and dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "{name}"
| fields timestamp, dsoa.run.results | sort timestamp desc

-- Count telemetry by context
fetch logs
| filter db.system == "snowflake" and dsoa.run.plugin == "{name}"
| summarize count(), by: {dsoa.run.context}

-- Query metrics
timeseries avg(snowflake.{domain}.{metric}),
  by: {db.namespace}
| filter db.system == "snowflake"

-- Monitor plugin performance (self-monitoring field-level breakdown)
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "{name}"
| fields timestamp, dsoa.run.plugin, dsoa.run.id,
         {name}.entries, {name}.log_lines, {name}.metrics,
         {name}.spans, {name}.span_events, {name}.events
| sort timestamp desc

-- Check errors
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "{name}"
| filter loglevel == "ERROR"
| sort timestamp desc
```

## Conditional SQL Blocks

Use plugin/option guards for conditional code inclusion:

```sql
--%PLUGIN:{name}:
-- Only included when {name} plugin is enabled
create or replace view ...
--%:PLUGIN:{name}

--%OPTION:dtagent_admin:
-- Only included when admin role is enabled
grant role ... to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin
```

For cross-plugin dependencies, wrap both column references AND join clauses in
guards. Test with the dependency both enabled and disabled.

## Upgrade Scripts (Procedure Signature Changes)

When a stored procedure's parameter list changes, Snowflake won't replace it —
it raises an ambiguous overload error. Create an upgrade script:

```text
src/dtagent.sql/upgrade/<new-version>/xxx_drop_{name}_old_proc.sql
```

```sql
--%PLUGIN:{name}:
DROP PROCEDURE IF EXISTS DTAGENT_DB.APP.F_{UPPER}_INSTRUMENTED(<old-param-types>);
--%:PLUGIN:{name}
```

Deploy upgrade before main deploy:
```bash
./scripts/deploy/deploy.sh test-qa --scope=upgrade --from-version=<prev> --options=skip_confirm
./scripts/deploy/deploy.sh test-qa --scope=plugins,admin,config --options=skip_confirm
```

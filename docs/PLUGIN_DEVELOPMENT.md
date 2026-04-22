# Plugin Development Guide

This guide covers creating plugins for the Dynatrace Snowflake Observability Agent (DSOA). Each plugin collects data from Snowflake, transforms it to OpenTelemetry format, and reports telemetry to Dynatrace.

**Table of Contents:**

- [Prerequisites](#prerequisites)
- [Plugin Structure](#plugin-structure)
- [Step-by-Step: Creating a Plugin](#step-by-step-creating-a-plugin)
- [Advanced Topics](#advanced-topics)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)
- [Checklist](#checklist)

---

## Prerequisites

Before writing a plugin, establish clarity on:

1. **What problem does this plugin solve?** Map to a [Data Platform Observability](DPO.md) theme (Security, Operations, Costs, Performance, Quality) and identify concrete use cases.
1. **What Snowflake data sources does it need?** Identify views, functions, commands, and required privileges. Consider latency: ACCOUNT_USAGE has ~45 min lag; INFORMATION_SCHEMA is near-real-time but per-database; SHOW commands and SYSTEM$ functions are live.
1. **What scheduling model fits?** Single schedule (most plugins) vs dual-schedule for sources with different latency/cost characteristics.
1. **Does it need include/exclude filtering?** Yes, if it operates on user-created objects (pipes, tables, stages).

## Plugin Structure

Every plugin is a **triad** of co-located parts:

```text
src/dtagent/plugins/
  {name}.py                          # Python logic
  {name}.sql/                        # SQL definitions
    init/                            # Optional: ACCOUNTADMIN setup
    admin/                           # Optional: admin-scope scripts
    0xx_*.sql                        # Views, procedures (prefix 0-69)
    801_{name}_task.sql              # Task definition
    901_update_{name}_conf.sql       # Config update procedure
  {name}.config/                     # Metadata
    {name}-config.yml                # Plugin configuration
    instruments-def.yml              # Semantic dictionary
    bom.yml                          # Bill of materials
    readme.md                        # Plugin documentation
    config.md                        # Optional: extended config docs
```

### Naming Conventions

| Component        | Convention                   | Example (`my_plugin`)      |
|------------------|------------------------------|----------------------------|
| Plugin name      | `snake_case`                 | `my_plugin`                |
| Python file      | `{name}.py`                  | `my_plugin.py`             |
| Python class     | `{CamelCase}Plugin`          | `MyPluginPlugin`           |
| `PLUGIN_NAME`    | lowercase, underscores       | `"my_plugin"`              |
| SQL directory    | `{name}.sql/`                | `my_plugin.sql/`           |
| Config directory | `{name}.config/`             | `my_plugin.config/`        |
| Config YAML      | `{name}-config.yml`          | `my_plugin-config.yml`     |
| SQL objects      | ALL UPPERCASE                | `V_MY_PLUGIN_INSTRUMENTED` |
| Task             | `TASK_DTAGENT_{UPPER}`       | `TASK_DTAGENT_MY_PLUGIN`   |
| Config procedure | `UPDATE_{UPPER}_CONF()`      | `UPDATE_MY_PLUGIN_CONF()`  |
| Semantic fields  | `snowflake.{domain}.{field}` | `snowflake.pipe.name`      |

### Plugin Types

1. **Log/Metric/Event plugins** — Use `_log_entries()`. Most plugins fall here. Examples: `budgets`, `warehouse_usage`, `snowpipes`.
1. **Span plugins** — Use `_process_span_rows()` for hierarchical traces. Examples: `query_history`, `login_history`.

---

## Step-by-Step: Creating a Plugin

### 1. Create Directory Structure

```bash
mkdir -p src/dtagent/plugins/{name}.sql
mkdir -p src/dtagent/plugins/{name}.config
touch src/dtagent/plugins/{name}.py
```

### 2. Write the Python Plugin Class

```python
"""Plugin file for processing {name} plugin data."""

# MIT license header (see existing plugins for full text)
# ##region / ##endregion COMPILE_REMOVE markers around imports

from typing import Dict, List, Optional
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

class {CamelCase}Plugin(Plugin):
    """{Name} plugin class."""

    PLUGIN_NAME = "{name}"

    def process(self, run_id: str, run_proc: bool = True,
                contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes {name} measurements.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed
            contexts (Optional[List[str]]): optional context filter; None = all

        Returns:
            Dict[str,Dict[str,int]]: Counts of processed telemetry data.
        """
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

Key requirements:

- Class name: `{CamelCase}Plugin` inheriting `Plugin`
- `PLUGIN_NAME` constant matching the file name
- `process()` method with the standard signature
- For views: pass the view name directly to `_get_table_rows()`
- For procedures: use `"SELECT * FROM TABLE(DTAGENT_DB.APP.F_{UPPER}_INSTRUMENTED())"`

### 3. Create SQL Views and Procedures

#### a) Instrumented View

**Use views** for straightforward data collection (most plugins). Use procedures only when you need error handling, temp tables, conditional logic, or multi-step processing.

Create `src/dtagent/plugins/{name}.sql/053_v_{name}_instrumented.sql`:

```sql
-- MIT license header
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_{UPPER}_INSTRUMENTED as
with cte_source as (
    select                                              -- explicit columns (BCR-2275)
        ENTITY_NAME,
        DATABASE_NAME,
        SCHEMA_NAME,
        COMMENT
    from SNOWFLAKE.ACCOUNT_USAGE.SOME_VIEW
    where DELETED is null
)
select
    current_timestamp()                                     as TIMESTAMP,
    s.entity_name                                           as ENTITY_NAME,
    concat('Entity: ', s.entity_name, ' in ', s.database_name)  as _MESSAGE,

    object_construct(
        'db.namespace',                 s.database_name,
        'snowflake.schema.name',        s.schema_name
    )                                                       as DIMENSIONS,

    object_construct(
        'snowflake.entity.name',        s.entity_name,
        'snowflake.entity.comment',     s.comment
    )                                                       as ATTRIBUTES,

    object_construct(
        'snowflake.entity.total',       1
    )                                                       as METRICS
from cte_source s;

grant select on view DTAGENT_DB.APP.V_{UPPER}_INSTRUMENTED to role DTAGENT_VIEWER;
```

**Required columns for log/metric plugins:**

| Column       | Type            | Purpose                                                |
|--------------|-----------------|--------------------------------------------------------|
| `TIMESTAMP`  | `TIMESTAMP_LTZ` | When data was collected or event occurred              |
| `_MESSAGE`   | `VARCHAR`       | Log content (auto-mapped to `content` in Dynatrace)    |
| `DIMENSIONS` | `OBJECT`        | Low-cardinality grouping fields; **sent with metrics** |
| `ATTRIBUTES` | `OBJECT`        | High-cardinality context; **NOT sent with metrics**    |
| `METRICS`    | `OBJECT`        | Numerical measurements                                 |

**Optional columns:** identifier columns (e.g., `ENTITY_NAME`), `EVENT_TIMESTAMPS` (for timestamp events).

**Additional columns for span plugins:** `QUERY_ID`, `PARENT_QUERY_ID`, `START_TIME`/`END_TIME` (epoch nanoseconds), `NAME`, `STATUS_CODE` (`'OK'`/`'ERROR'`/`'UNSET'`), `_SPAN_ID`, `_TRACE_ID`, `SESSION_ID`.

**SQL conventions:**

- ALL object names UPPERCASE (lowercase breaks custom-tag deployment)
- Start with `use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;`
- **Never use `SELECT *` when querying Snowflake system views** (`SNOWFLAKE.ACCOUNT_USAGE.*`, `SNOWFLAKE.INFORMATION_SCHEMA.*`) — always use explicit column lists. This protects against BCR-2275: Snowflake may add columns without notice, causing memory bloat, telemetry corruption, or view creation failures. `SELECT *` from DSOA's own views/tables is acceptable since we control those schemas.
- Use `TIMESTAMP_LTZ` for timestamps
- Use `object_construct()` for JSON columns
- Grant `SELECT` on views / `USAGE` on procedures to `DTAGENT_VIEWER`
- Use CTEs for readability

#### b) Task Definition

Create `src/dtagent/plugins/{name}.sql/801_{name}_task.sql`:

```sql
-- MIT license header
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

Schedule is set here but overridden by configuration at deploy time.

#### c) Configuration Update Procedure

Create `src/dtagent/plugins/{name}.sql/901_update_{name}_conf.sql`:

```sql
-- MIT license header
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_{UPPER}_CONF()
returns text language SQL execute as caller
as $$
begin
    call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('{name}');
    return '{name} plugin config updated';
exception
    when statement_error then SYSTEM$LOG_WARN(SQLERRM); return SQLERRM;
end;
$$;
```

### 4. Define Configuration

Create `src/dtagent/plugins/{name}.config/{name}-config.yml`:

```yaml
plugins:
  {name}:
    schedule: USING CRON 0 */12 * * * UTC
    is_disabled: false
    telemetry:
      - logs
      - metrics
      - events
      - biz_events
```

Add `include`/`exclude` lists if the plugin operates on user-created objects. Add custom settings (e.g., `lookback_hours`) as needed.

### 5. Define Semantic Dictionary

Create `src/dtagent/plugins/{name}.config/instruments-def.yml`:

```yaml
# MIT license header

dimensions:
  db.namespace:
    __context_names: ["{name}"]
    __example: analytics_db
    __description: The database name.
  snowflake.schema.name:
    __context_names: ["{name}"]
    __example: public
    __description: The schema name.

attributes:
  snowflake.entity.name:
    __context_names: ["{name}"]
    __example: my_entity
    __description: The entity name.

metrics:
  snowflake.entity.total:
    __context_names: ["{name}"]
    __example: "1"
    __description: Total number of entities per row.
    displayName: Entity Total
    unit: count
```

**Structure:** `dimensions` (low-cardinality, used for metrics), `attributes` (high-cardinality context), `metrics` (numerical), `event_timestamps` (optional, for timestamp events).

**Field naming rules** — see [Semantic Conventions](CONTRIBUTING.md#field-and-metric-naming-rules) for full details:

- Lowercase `snake_case`, custom fields start with `snowflake.`
- No measurement units in names; no `.count` suffix
- Booleans use `is_`/`has_` prefix
- Use existing OTel/Dynatrace semantics when they match

### 6. Document Your Plugin

Create `src/dtagent/plugins/{name}.config/readme.md` with: brief description, what data is collected, key use cases, configuration examples, and sample DQL queries.

### 7. Define Bill of Materials

Create `src/dtagent/plugins/{name}.config/bom.yml`:

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

### 8. Create Plugin Tests

#### Test environment checklist

Before writing tests:

- **Identify core use cases** — these drive fixture data and `docs/USECASES.md` entries
- **Capture representative fixtures** from live Snowflake (or craft minimal fixtures)
- **Define golden results** — expected telemetry counts per scenario
- **Plan `disabled_telemetry` combos** — at minimum: `[]`, `["metrics"]`, `["logs"]`, all-disabled

Create `test/plugins/test_{name}.py`:

```python
# MIT license header

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
                base_count={
                    "{name}": {"entries": 2, "log_lines": 2, "metrics": 2},
                },
            )
```

**Running tests:**

```bash
.venv/bin/pytest test/plugins/test_{name}.py -v    # mocked
.venv/bin/pytest test/plugins/test_{name}.py -p    # regenerate fixtures from live Snowflake
```

### 9. Build and Deploy

```bash
# Build
./scripts/dev/build.sh

# Test
.venv/bin/pytest test/plugins/test_{name}.py -v

# Deploy (test-qa only for agent-assisted deployments)
./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

# Verify in Snowflake
# SHOW TASKS LIKE 'TASK_DTAGENT_{UPPER}%' IN SCHEMA DTAGENT_DB.APP;
# CALL DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}'));
```

---

## Advanced Topics

### Multi-Context Plugins

Plugins can process multiple data sources as separate contexts. Guard each context:

```python
if not contexts or "context_a" in contexts:
    e, l, m, ev = self._log_entries(
        lambda: self._get_table_rows(t_a), "context_a",
        run_uuid=run_id, report_metrics=True, log_completion=False)
    results["context_a"] = {"entries": e, "log_lines": l, "metrics": m, "events": ev}

if not contexts or "context_b" in contexts:
    e, l, m, ev = self._log_entries(
        lambda: self._get_table_rows(t_b), "context_b",
        run_uuid=run_id, report_metrics=True, log_completion=False)
    results["context_b"] = {"entries": e, "log_lines": l, "metrics": m, "events": ev}
```

When `log_completion=False` on individual contexts, call `_report_execution()` at the end for combined completion logging.

### Dual-Schedule Architecture

For plugins with contexts of different latency/cost, use two tasks with context-selective syntax:

```sql
-- 801: Fast task (lightweight, frequent)
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}:{fast_context}'));

-- 802: Deep task (heavy, less frequent)
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('{name}:{ctx1},{ctx2}'));
```

The config update procedure must handle multiple schedules:

```sql
call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('{name}', ARRAY_CONSTRUCT('history', 'grants'));
```

Configuration adds separate schedule keys:

```yaml
plugins:
  {name}:
    schedule: USING CRON */5 * * * * UTC          # fast task
    schedule_history: USING CRON 0 * * * * UTC    # deep task
```

See `snowpipes` for a complete dual-schedule implementation.

### Custom Timestamp Events

To report state-change events (e.g., entity created, modified):

1. Include `EVENT_TIMESTAMPS` column in SQL (values as epoch nanoseconds)
1. Set `report_timestamp_events=True` in `_log_entries()`
1. Define `event_timestamps` section in `instruments-def.yml`

```sql
object_construct(
    'snowflake.entity.created_time', extract(epoch_nanosecond from CREATED::timestamp_ltz)
) as EVENT_TIMESTAMPS
```

```yaml
event_timestamps:
  snowflake.event.trigger:
    __context_names: ["{name}"]
    __example: "snowflake.entity.created_time"
    __description: Event trigger key.
  snowflake.entity.created_time:
    __context_names: ["{name}"]
    __example: 1639051180946000000
    __description: Entity creation timestamp.
```

### Span Plugins

For hierarchical trace data, use `_process_span_rows()`:

```python
processed_ids, errors, span_events, spans, logs, metrics = self._process_span_rows(
    lambda: self._get_table_rows(t_query),
    view_name="view_name",
    context_name="{name}",
    run_uuid=run_id,
    query_id_col_name="QUERY_ID",
    parent_query_id_col_name="PARENT_QUERY_ID",
    f_span_events=__f_span_events,  # optional: extract span events
    f_log_events=__f_log_events,    # optional: emit logs per span
    log_completion=run_proc,
)
```

See `query_history.py` and `login_history.py` for real implementations.

### Include/Exclude Filtering

Plugins operating on user-created objects support `include`/`exclude` pattern lists (`DB.SCHEMA.OBJECT` with `%` wildcards).

**In views** — compare full `QUALIFIED_NAME` against raw patterns:

```sql
where QUALIFIED_NAME LIKE ANY (select include_pattern from cte_includes)
  and not QUALIFIED_NAME LIKE ANY (select exclude_pattern from cte_excludes)
```

**In admin grant procedures** — match excludes at the **same tier** as the grant:

| Tier   | Grant scope               | Exclude condition                                        |
|--------|---------------------------|----------------------------------------------------------|
| DB     | `IN DATABASE db`          | Only DB-wide excludes: `split_part(VALUE, '.', 2) = '%'` |
| Schema | `IN SCHEMA db.schema`     | `(db.schema.%) LIKE ANY (raw excludes)`                  |
| Object | `ON OBJECT db.schema.obj` | Include VALUE itself `LIKE ANY (raw excludes)`           |

Never collapse a fine-grained exclude to DB-level only — this breaks the least-privilege principle.

### Conditional Code Blocks

```sql
--%PLUGIN:{name}:
-- Only included when {name} is enabled
--%:PLUGIN:{name}

--%OPTION:dtagent_admin:
-- Only included when admin role is enabled
--%:OPTION:dtagent_admin
```

For cross-plugin dependencies, wrap both column references AND join clauses. Test with the dependency both enabled and disabled.

### Configuration Access

In SQL:

```sql
DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.{name}.some_setting', 'default')
```

In Python:

```python
self._configuration.get_config_value(self._session, 'plugins.{name}.some_setting', 'default')
```

---

## Common Patterns

| Name                           | Description                                                                                                            | Examples                                                                     |
|--------------------------------|------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| Simple Log + Metric            | Single view, single task, `_log_entries()` with `report_metrics=True`. Most common pattern.                            | `budgets`, `data_schemas`, `dynamic_tables`, `resource_monitors`             |
| Multi-Context, Single Schedule | Multiple views in one `process()` call with context guards. Single task runs all contexts.                             | `budgets` (budgets + spendings), `warehouse_usage`                           |
| Multi-Context, Dual Schedule   | Fast and deep tasks on different cadences. Context-selective task syntax: `ARRAY_CONSTRUCT('{plugin}:{ctx1},{ctx2}')`. | `snowpipes` (fast: pipe status every 5 min; deep: copy/usage history hourly) |
| Span/Trace                     | Uses `_process_span_rows()` for parent-child relationships and distributed traces.                                     | `query_history`, `login_history`                                             |
| Pre-Processing Step            | Calls a stored procedure before processing contexts (e.g., refresh materialized data).                                 | `budgets` calls `P_GET_BUDGETS` before reading views                         |
| Incremental Processing         | Uses `F_LAST_PROCESSED_TS('{name}')` to only process new data since last run.                                          | `warehouse_usage`, `event_log`                                               |

---

## Troubleshooting

| Symptom                       | Likely cause                                | Fix                                                   |
|-------------------------------|---------------------------------------------|-------------------------------------------------------|
| Plugin not found / not loaded | Wrong class naming or missing `PLUGIN_NAME` | Verify `{CamelCase}Plugin`, rebuild                   |
| SQL deployment errors         | Lowercase names, missing `USE` statements   | Ensure UPPERCASE, add `use role/database/warehouse`   |
| No data in Dynatrace          | Plugin disabled or telemetry type missing   | Check `is_disabled`, `telemetry` list in config       |
| Task not running              | Suspended, config not deployed              | Deploy `--scope=config`, call `UPDATE_{UPPER}_CONF()` |
| Mismatched test counts        | Stale fixtures, wrong `base_count`          | Regenerate with `-p`, verify expected values          |
| Semantic fields missing       | Mismatch between SQL and instruments-def    | Align field names, rebuild docs                       |
| Procedure overload error      | Signature changed without upgrade script    | Create upgrade script to drop old signature first     |
| Config not applied            | Config scope not deployed                   | `deploy.sh --scope=config`                            |

### Useful DQL Queries

```dql
-- Plugin logs
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "{name}"
| sort timestamp desc | limit 50

-- Self-monitoring results
fetch bizevents
| filter db.system == "snowflake" and dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "{name}"
| fields timestamp, dsoa.run.results | sort timestamp desc

-- Telemetry counts by context
fetch logs
| filter db.system == "snowflake" and dsoa.run.plugin == "{name}"
| summarize count(), by: {dsoa.run.context}

-- Plugin errors
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "{name}"
| filter loglevel == "ERROR" | sort timestamp desc
```

### Reference Plugins

| Complexity | Plugin          | Pattern                                          |
|------------|-----------------|--------------------------------------------------|
| Simple     | `budgets`       | Log + metric, multi-context                      |
| Medium     | `snowpipes`     | Dual-schedule, timestamp events, include/exclude |
| Complex    | `query_history` | Span/trace, cross-plugin dependency              |

---

## Checklist

- [ ] Directory structure created (triad)
- [ ] Python class inheriting `Plugin` with `PLUGIN_NAME` and `process()`
- [ ] Instrumented SQL view (or procedure)
- [ ] Task definition (`801_*.sql`)
- [ ] Config update procedure (`901_*.sql`)
- [ ] Plugin config YAML
- [ ] Semantic dictionary (`instruments-def.yml`)
- [ ] Plugin documentation (`readme.md`)
- [ ] Bill of materials (`bom.yml`)
- [ ] Tests written with all `disabled_telemetry` combos
- [ ] NDJSON fixtures captured (`pytest -p`)
- [ ] Golden results defined in `test/test_results/test_{name}/`
- [ ] Use cases added to `docs/USECASES.md`
- [ ] Tests pass: `.venv/bin/pytest test/plugins/test_{name}.py -v`
- [ ] Build succeeds: `./scripts/dev/build.sh`
- [ ] Lint passes: `make lint`
- [ ] Documentation rebuilt: `./scripts/dev/build_docs.sh`
- [ ] `CHANGELOG.md` and `DEVLOG.md` updated
- [ ] Deployed and verified in Dynatrace

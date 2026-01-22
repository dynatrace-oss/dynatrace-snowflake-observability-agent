# Plugin Development Guide

This comprehensive guide explains how to create custom plugins for the Dynatrace Snowflake Observability Agent. A plugin extends the agent's functionality by collecting and reporting telemetry data from various Snowflake sources.

**Table of Contents:**

- [Overview](#overview)
- [Plugin Structure](#plugin-structure)
- [Step-by-Step: Creating a New Plugin](#step-by-step-creating-a-new-plugin)
  - [1. Create Plugin Directory Structure](#1-create-plugin-directory-structure)
  - [2. Write the Python Plugin Class](#2-write-the-python-plugin-class)
  - [3. Create SQL Views and Procedures](#3-create-sql-views-and-procedures)
  - [4. Define Configuration](#4-define-configuration)
  - [5. Define Semantic Dictionary](#5-define-semantic-dictionary)
  - [6. Document Your Plugin](#6-document-your-plugin)
  - [7. Define Bill of Materials (BOM)](#7-define-bill-of-materials-bom)
  - [8. Create Plugin Tests](#8-create-plugin-tests)
  - [9. Build and Deploy](#9-build-and-deploy)
- [Best Practices](#best-practices)
- [Advanced Topics](#advanced-topics)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Overview

A Dynatrace Snowflake Observability Agent plugin:

- Collects data from Snowflake (queries, views, functions, or procedures)
- Transforms data into OpenTelemetry format (logs, metrics, spans, events)
- Reports telemetry to Dynatrace
- Can be enabled/disabled and scheduled independently
- Follows semantic conventions for consistent field naming

### Plugin Types

Plugins typically fall into two categories:

1. **Simple Log/Metric Plugins**: Report data as logs and/or metrics using `_log_entries()` method
   - Examples: `active_queries`, `warehouse_usage`, `budgets`

2. **Complex Span Plugins**: Report hierarchical trace data using `_process_span_rows()` method
   - Examples: `query_history`, `login_history`

---

## Plugin Structure

Each plugin consists of the following components:

```text
src/dtagent/plugins/
├── your_plugin.py                       # Python plugin class
├── your_plugin.sql/                     # SQL definitions
│   ├── init/                           # Optional: initialization scripts
│   │   └── 009_your_plugin_init.sql   # Runs as ACCOUNTADMIN
│   ├── 0xx_*.sql                       # Views, procedures, functions (0-69)
│   ├── 801_your_plugin_task.sql       # Task definition
│   └── 901_update_your_plugin_conf.sql # Configuration update procedure
└── your_plugin.config/                 # Configuration and documentation
    ├── your_plugin-config.yml          # Default configuration
    ├── bom.yml                         # Bill of Materials
    ├── instruments-def.yml             # Semantic dictionary
    ├── readme.md                       # Plugin description
    └── config.md                       # Optional: additional config docs
```

---

## Step-by-Step: Creating a New Plugin

Let's create a complete plugin called `example_plugin` that monitors Snowflake stages.

### 1. Create Plugin Directory Structure

Create the following directories and files:

```bash
mkdir -p src/dtagent/plugins/example_plugin.sql/init
mkdir -p src/dtagent/plugins/example_plugin.config
touch src/dtagent/plugins/example_plugin.py
```

### 2. Write the Python Plugin Class

Create `src/dtagent/plugins/example_plugin.py`:

```python
"""Plugin file for processing example plugin data."""

##region ------------------------------ IMPORTS  -----------------------------------------
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
from typing import Dict
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: EXAMPLE PLUGIN --------------------------------


class ExamplePluginPlugin(Plugin):
    """Example plugin class."""

    PLUGIN_NAME = "example_plugin"

    def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """Processes measurements from the example plugin.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,Dict[str,int]]: A dictionary with counts of processed telemetry data.

            Example:
            {
                "dsoa.run.results": {
                    "example_plugin": {
                        "entries": entries_cnt,
                        "log_lines": logs_cnt,
                        "metrics": metrics_cnt,
                        "events": events_cnt
                    }
                },
                "dsoa.run.id": "uuid_string"
            }
        """
        # Query the instrumented view
        t_example_data = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_EXAMPLE_PLUGIN_INSTRUMENTED())"

        # Process entries and collect counts
        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_example_data),
            "example_plugin",
            run_uuid=run_id,
            report_timestamp_events=False,  # Set to True if you have event timestamps
            report_metrics=True,            # Set to True to report metrics
            log_completion=run_proc,
        )

        # Return the results
        return self._report_results(
            {
                "example_plugin": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                }
            },
            run_id,
        )


##endregion
```

**Key Points:**

- Class name must be `{PluginName}Plugin` where `{PluginName}` is the camelCase version of your plugin name
- Must inherit from `Plugin` base class
- Must define `PLUGIN_NAME` class variable (lowercase with underscores)
- Must implement `process()` method with the specified signature
- Use `_log_entries()` for simple log/metric reporting
- Use `_process_span_rows()` for complex span/trace reporting

### 3. Create SQL Views and Procedures

#### a) Create the main instrumented view

Create `src/dtagent/plugins/example_plugin.sql/053_f_example_plugin_instrumented.sql`:

```sql
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
--
--
-- F_EXAMPLE_PLUGIN_INSTRUMENTED() translates raw data from Snowflake
-- into semantics expected by our metrics, logs, etc.
-- !!!
-- WARNING: ensure you keep instruments-def.yml and this function in sync !!!
-- !!!
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.F_EXAMPLE_PLUGIN_INSTRUMENTED()
returns table (
    TIMESTAMP TIMESTAMP_LTZ,
    stage_name VARCHAR,
    _message VARCHAR,
    dimensions object,
    attributes object,
    metrics object
)
language sql
execute as caller
AS
$$
DECLARE
    c_example_plugin_instrumented CURSOR FOR
        with cte_stages as (
            -- Query Snowflake metadata
            select
                STAGE_NAME,
                STAGE_TYPE,
                DATABASE_NAME,
                SCHEMA_NAME,
                CREATED as CREATED_TIME,
                COMMENT
            from SNOWFLAKE.ACCOUNT_USAGE.STAGES
            where DELETED is null
        )
        select
            current_timestamp() as TIMESTAMP,

            -- Identifiers
            STAGE_NAME,

            -- Message for logs
            concat('Stage: ', STAGE_NAME, ' in ', DATABASE_NAME, '.', SCHEMA_NAME) as _MESSAGE,

            -- Dimensions (for grouping/filtering)
            object_construct(
                'db.namespace', DATABASE_NAME,
                'snowflake.schema.name', SCHEMA_NAME,
                'snowflake.stage.type', STAGE_TYPE
            ) as DIMENSIONS,

            -- Attributes (additional context)
            object_construct(
                'snowflake.stage.name', STAGE_NAME,
                'snowflake.stage.comment', COMMENT,
                'snowflake.stage.created_time', CREATED_TIME
            ) as ATTRIBUTES,

            -- Metrics (numerical values)
            object_construct(
                'snowflake.stage.count', 1
            ) as METRICS

        from cte_stages;
BEGIN
    OPEN c_example_plugin_instrumented;
    RETURN TABLE(c_example_plugin_instrumented);
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.F_EXAMPLE_PLUGIN_INSTRUMENTED() to role DTAGENT_VIEWER;
```

**Important SQL Conventions:**

- Use `TIMESTAMP_LTZ` type for timestamp fields
- Include `_MESSAGE` column for log content
- Structure output as: `TIMESTAMP`, identifier columns, `_MESSAGE`, `dimensions`, `attributes`, `metrics`
- Use `object_construct()` to create JSON objects
- Always grant `USAGE` to `DTAGENT_VIEWER`
- Use uppercase for all Snowflake object names in SQL

#### b) Create the task definition

Create `src/dtagent/plugins/example_plugin.sql/801_example_plugin_task.sql`:

```sql
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- <license header as above>
--
-- This task ensures the example plugin is called periodically
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 0 */12 * * * UTC'
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('example_plugin'));

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN to role DTAGENT_VIEWER revoke current grants;
grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN to role DTAGENT_VIEWER;
alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN suspend;
```

**Task Naming Convention:**

- Must be named `TASK_DTAGENT_{PLUGIN_NAME_UPPERCASE}`
- Schedule is set here but will be overridden by configuration
- Always grant ownership to `DTAGENT_VIEWER`

#### c) Create configuration update procedure

Create `src/dtagent/plugins/example_plugin.sql/901_update_example_plugin_conf.sql`:

```sql
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- <license header as above>
--
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_EXAMPLE_PLUGIN_CONF()
returns text
language SQL
execute as caller
as
$$
begin
    call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('example_plugin');
    return 'example_plugin plugin config updated';
exception
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return sqlerrm;
end;
$$
;

-- call DTAGENT_DB.CONFIG.UPDATE_EXAMPLE_PLUGIN_CONF();
```

**Configuration Update Function:**

- Name must be `UPDATE_{PLUGIN_NAME_UPPERCASE}_CONF()`
- Calls the core `UPDATE_PLUGIN_SCHEDULE()` function
- Located in `CONFIG` schema

#### d) Optional: Create initialization script

If your plugin needs ACCOUNTADMIN privileges (e.g., to enable specific Snowflake features), create `src/dtagent/plugins/example_plugin.sql/init/009_example_plugin_init.sql`:

```sql
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- <license header as above>
--
-- Initialization script for example plugin
-- This runs with ACCOUNTADMIN privileges during initial setup

use role ACCOUNTADMIN;

-- Example: Enable a specific Snowflake feature
-- alter ACCOUNT set SOME_FEATURE=TRUE;
```

### 4. Define Configuration

Create `src/dtagent/plugins/example_plugin.config/example_plugin-config.yml`:

```yaml
plugins:
  example_plugin:
    schedule: USING CRON 0 */12 * * * UTC  # Run every 12 hours
    is_disabled: false                     # Plugin enabled by default
    telemetry:                             # Types of telemetry to report
      - logs
      - metrics
      - events
      - biz_events
```

**Configuration Guidelines:**

- File must be named `{plugin_name}-config.yml`
- Must be valid YAML
- Key configuration options:
  - `schedule`: Cron expression for task scheduling
  - `is_disabled`: Boolean to enable/disable the plugin
  - `telemetry`: Array of telemetry types to report
- Add custom configuration options as needed for your plugin

**Standard telemetry types:**

- `logs`: Log entries
- `metrics`: Numerical measurements
- `spans`: Distributed traces
- `events`: Generic events
- `biz_events`: Business events

### 5. Define Semantic Dictionary

Create `src/dtagent/plugins/example_plugin.config/instruments-def.yml`:

```yaml
#
# Copyright (c) 2025 Dynatrace Open Source
#
# <license header>
#
# Catalog of instrumentation for example_plugin

attributes:
  snowflake.stage.name:
    __example: my_stage
    __description: The name of the Snowflake stage.
  snowflake.stage.comment:
    __example: "Production data stage"
    __description: User-provided comment for the stage.
  snowflake.stage.created_time:
    __example: "2025-01-15T10:30:00Z"
    __description: Timestamp when the stage was created.

dimensions:
  db.namespace:
    __example: analytics_db
    __description: The database containing the stage.
  snowflake.schema.name:
    __example: public
    __description: The schema containing the stage.
  snowflake.stage.type:
    __example: INTERNAL
    __description: |
      The type of stage:
      - INTERNAL,
      - EXTERNAL.

metrics:
  snowflake.stage.count:
    __example: "1"
    __description: Count of stages (always 1 per row).
    displayName: Stage Count
    unit: count
```

**Semantic Dictionary Structure:**

1. **Attributes** (context fields):
   - Use existing OpenTelemetry or Dynatrace semantics when possible
   - Custom fields should start with `snowflake.`
   - Include `__example` and `__description` for each field

2. **Dimensions** (grouping/filtering fields):
   - Should be low-cardinality
   - Used for aggregation and filtering in queries
   - Same naming rules as attributes

3. **Metrics** (numerical measurements):
   - Must have `__description` and `unit`
   - Optional: `displayName` for Dynatrace UI
   - Common units: `ms`, `count`, `bytes`, `percent`

**Naming Conventions (CRITICAL):**

- Use lowercase `snake_case`
- Start custom fields with `snowflake.`
- AVOID measurement units in names
- DO NOT use `.count` suffix (it's implied)
- Use singular/plural correctly
- Split with DOT `.` for object hierarchy

### 6. Document Your Plugin

Create `src/dtagent/plugins/example_plugin.config/readme.md`:

```markdown
This plugin monitors Snowflake stages and reports their configuration and usage.

It collects information about all non-deleted stages in the account, including:
- Stage name, type, and location
- Database and schema ownership
- Creation timestamps
- User-provided comments

The plugin reports one log entry and metric per stage, allowing you to:
- Track the total number of stages
- Monitor stage creation and deletion
- Audit stage configurations
- Filter by database, schema, or stage type

## Configuration

The plugin runs every 12 hours by default. You can adjust the schedule in your configuration file:

\`\`\`yaml
plugins:
  example_plugin:
    schedule: USING CRON 0 */6 * * * UTC  # Run every 6 hours
\`\`\`

## Querying in Dynatrace

Example DQL query to list all stages:

\`\`\`dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "example_plugin"
| summarize count(), by: {db.namespace, snowflake.schema.name, snowflake.stage.type}
\`\`\`
```

**Documentation Best Practices:**

- Start with a brief description (1-2 sentences)
- Explain what data is collected
- List key use cases
- Provide configuration examples
- Include sample DQL queries
- Keep it concise but informative

Optional: Create `src/dtagent/plugins/example_plugin.config/config.md` for additional configuration documentation if needed.

### 7. Define Bill of Materials (BOM)

Create `src/dtagent/plugins/example_plugin.config/bom.yml`:

```yaml
delivers:
  - name: DTAGENT_DB.APP.F_EXAMPLE_PLUGIN_INSTRUMENTED()
    type: procedure
  - name: DTAGENT_DB.APP.TASK_DTAGENT_EXAMPLE_PLUGIN
    type: task
  - name: DTAGENT_DB.CONFIG.UPDATE_EXAMPLE_PLUGIN_CONF()
    type: procedure

references:
  - name: SNOWFLAKE.ACCOUNT_USAGE.STAGES
    type: view
    privileges: SELECT
```

**BOM Structure:**

1. **delivers**: Objects created by the plugin
   - Procedures, functions, tasks, tables
   - Use full qualified names with database and schema

2. **references**: External objects the plugin uses
   - Snowflake system views, tables, functions
   - Include required privileges
   - Common privileges: `SELECT`, `USAGE`, `MONITOR`, `IMPORTED PRIVILEGES`

### 8. Create Plugin Tests

Create `test/plugins/test_example_plugin.py`:

```python
#
# Copyright (c) 2025 Dynatrace Open Source
#
# <license header>
#
class TestExamplePlugin:
    import pytest

    # Define pickle files for test data
    PICKLES = {
        "SELECT * FROM TABLE(DTAGENT_DB.APP.F_EXAMPLE_PLUGIN_INSTRUMENTED())": "test/test_data/example_plugin.pkl"
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_example_plugin(self):
        import logging
        from unittest.mock import patch
        from typing import Dict, Generator
        from dtagent.plugins.example_plugin import ExamplePluginPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        # ======================================================================
        # Generate/load test data
        utils._pickle_all(_get_session(), self.PICKLES)

        # Mock the plugin to use pickled data instead of querying Snowflake
        class TestExamplePluginPlugin(ExamplePluginPlugin):
            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(
                    TestExamplePlugin.PICKLES, t_data, limit=2
                )

        def __local_get_plugin_class(source: str):
            return TestExamplePluginPlugin

        from dtagent import plugins
        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        # Test with different telemetry combinations
        disabled_combinations = [
            [],                                      # All telemetry enabled
            ["metrics"],                             # Metrics disabled
            ["logs"],                                # Logs disabled
            ["logs", "metrics"],                     # Both disabled
            ["logs", "spans", "metrics", "events"],  # All disabled
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_example_plugin",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={
                    "example_plugin": {
                        "entries": 2,
                        "log_lines": 2,
                        "metrics": 2
                    }
                },
            )


if __name__ == "__main__":
    test_class = TestExamplePlugin()
    test_class.test_example_plugin()
```

**Testing Guidelines:**

1. **Test Structure:**
   - Create one test class per plugin
   - Name it `Test{PluginName}`
   - Define `PICKLES` dict mapping queries to pickle files
   - Override `_get_table_rows()` to return mocked data

2. **Generating Test Data:**
   - First run generates pickle files from actual Snowflake queries
   - Requires valid test credentials (see [CONTRIBUTING.md](CONTRIBUTING.md))
   - Run: `./scripts/dev/test.sh test_example_plugin -p`

3. **Running Tests:**

   ```bash
   # Run single plugin test
   ./scripts/dev/test.sh test_example_plugin

   # Run with pickling (regenerate test data)
   ./scripts/dev/test.sh test_example_plugin -p

   # Run all plugin tests
   pytest test/plugins/
   ```

4. **Test Modes:**
   - **Local mode** (no credentials): Uses mocked APIs, doesn't send data
   - **Live mode** (with credentials): Connects to Snowflake and Dynatrace

### 9. Build and Deploy

After creating all the plugin files:

1. **Build the agent:**

   ```bash
   ./scripts/dev/build.sh
   ```

   This compiles your Python code and assembles all SQL files into the `build/` directory.

2. **Run tests:**

   ```bash
   ./scripts/dev/test.sh test_example_plugin
   ```

3. **Deploy to Snowflake:**

   ```bash
   ./scripts/deploy/deploy.sh YOUR_ENV
   ```

4. **Verify deployment:**
   - Check that your task was created:

     ```sql
     SHOW TASKS LIKE 'TASK_DTAGENT_EXAMPLE_PLUGIN' IN SCHEMA DTAGENT_DB.APP;
     ```

   - Manually run your plugin:

     ```sql
     CALL DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('example_plugin'));
     ```

   - Check for data in Dynatrace

---

## Best Practices

### Naming Conventions

1. **Python:**
   - Plugin class: `{CamelCase}Plugin` (e.g., `ExamplePluginPlugin`)
   - File name: `{snake_case}.py` (e.g., `example_plugin.py`)
   - `PLUGIN_NAME` constant: lowercase with underscores (e.g., `"example_plugin"`)

2. **SQL:**
   - All Snowflake objects: UPPERCASE
   - Procedures/Functions: `DTAGENT_DB.APP.F_{PLUGIN_NAME_UPPERCASE}_*`
   - Tasks: `DTAGENT_DB.APP.TASK_DTAGENT_{PLUGIN_NAME_UPPERCASE}`
   - Config procedures: `DTAGENT_DB.CONFIG.UPDATE_{PLUGIN_NAME_UPPERCASE}_CONF()`

3. **Semantic Fields:**
   - Use lowercase `snake_case`
   - Custom fields start with `snowflake.`
   - Follow [semantic conventions](CONTRIBUTING.md#field-and-metric-naming-rules)

### SQL Best Practices

1. **Use CTEs** for readability:

   ```sql
   with cte_raw_data as (
       select * from SNOWFLAKE.ACCOUNT_USAGE.SOME_VIEW
   ),
   cte_processed as (
       select ... from cte_raw_data
   )
   select ... from cte_processed
   ```

2. **Always include error handling:**

   ```sql
   BEGIN
       -- your code
   EXCEPTION
       WHEN statement_error THEN
           SYSTEM$LOG_ERROR(SQLERRM);
           RETURN error_object;
   END;
   ```

3. **Grant privileges appropriately:**
   - Procedures/Functions: `grant usage on ... to role DTAGENT_VIEWER;`
   - Tables: `grant select on ... to role DTAGENT_VIEWER;`
   - Ownership: Grant to `DTAGENT_VIEWER` for runtime objects

4. **Use configuration values:**

   ```sql
   where column_value = DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.your_plugin.some_setting', 'default_value')
   ```

### Python Best Practices

1. **Use helper methods from Plugin base class:**
   - `_get_table_rows()`: Iterate over query results
   - `_log_entries()`: Process simple log/metric data
   - `_process_span_rows()`: Process hierarchical span data
   - `_report_execution()`: Log processing completion
   - `_report_results()`: Format return value

2. **Handle errors gracefully:**

   ```python
   try:
       # processing code
   except Exception as e:
       LOG.error(f"Error processing {plugin_name}: {e}")
       # continue processing other rows
   ```

3. **Use proper logging:**

   ```python
   from dtagent import LOG, LL_TRACE

   LOG.info("Processing started")
   LOG.log(LL_TRACE, "Detailed trace info: %r", data)
   LOG.warning("Something unexpected: %s", message)
   ```

4. **Follow the Plugin interface:**
   - Return type must be `Dict[str, Dict[str, int]]`
   - Include all telemetry counts in the result
   - Use `RUN_PLUGIN_KEY`, `RUN_RESULTS_KEY`, `RUN_ID_KEY` constants

### Performance Considerations

1. **Limit data volume:**
   - Use `WHERE` clauses to filter old data
   - Track last processed timestamp with `F_LAST_PROCESSED_TS()`
   - Consider pagination for large datasets

2. **Optimize SQL queries:**
   - Use appropriate indexes
   - Avoid `SELECT *` when not needed
   - Use CTEs for complex transformations

3. **Handle large result sets:**
   - Use generators (`yield`) instead of loading all data into memory
   - Process rows incrementally
   - Flush metrics/spans periodically

### Testing Best Practices

1. **Test with realistic data:**
   - Generate pickle files from actual Snowflake queries
   - Include edge cases (nulls, special characters, etc.)
   - Test with varying data volumes

2. **Test all telemetry types:**
   - Verify logs, metrics, spans, events
   - Test with different telemetry disabled
   - Check that counts are correct

3. **Mock external dependencies:**
   - Override `_get_table_rows()` in tests
   - Use `_safe_get_unpickled_entries()` for consistent test data
   - Don't rely on live Snowflake connections in unit tests

---

## Advanced Topics

### Working with Spans

For plugins that need to report hierarchical trace data (parent-child relationships):

```python
def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
    """Process query history with spans."""

    def __f_span_events(d_span: Dict[str, any]) -> Tuple[List[Dict[str, any]], int]:
        """Extract span events from a span."""
        span_events = []
        # Extract and format events
        return span_events, 0  # Return events and error count

    def __f_log_events(d_log: Dict[str, any]) -> None:
        """Process log events."""
        # Send additional logs related to this span
        pass

    t_query_history = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_QUERY_HISTORY_INSTRUMENTED())"

    processed_ids, errors, span_events, spans, logs, metrics = self._process_span_rows(
        lambda: self._get_table_rows(t_query_history),
        view_name="query_history",
        context_name="query_history",
        run_uuid=run_id,
        query_id_col_name="QUERY_ID",
        parent_query_id_col_name="PARENT_QUERY_ID",
        f_span_events=__f_span_events,
        f_log_events=__f_log_events,
        log_completion=run_proc,
    )

    return self._report_results(
        {
            "query_history": {
                "entries": len(processed_ids),
                "errors": errors,
                "span_events": span_events,
                "spans": spans,
                "log_lines": logs,
                "metrics": metrics,
            }
        },
        run_id,
    )
```

**Span Requirements:**

- Must have `QUERY_ID` (or custom ID column)
- Optional: `PARENT_QUERY_ID` for hierarchical traces
- Must have `START_TIME` and `END_TIME` (in nanoseconds or as timestamp)
- Include span name, attributes, and optional events

### Custom Timestamp Events

To report specific timestamps as events:

```python
def prepare_timestamp_event(
    self, key: str, ts: Any, row_dict: Dict
) -> Tuple[str, Dict[str, Any], EventType]:
    """Define custom timestamp events."""

    if key == "STAGE_CREATED_TIME":
        return (
            f"Stage {row_dict['STAGE_NAME']} created",
            {"stage.name": row_dict["STAGE_NAME"]},
            EventType.INFO
        )

    return super().prepare_timestamp_event(key, ts, row_dict)
```

Override this method in your plugin class to customize event generation.

### Configuration-Driven Behavior

Access configuration values in SQL:

```sql
where STATUS = DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE(
    'plugins.example_plugin.filter_status',
    'ACTIVE'
)::string
```

Access configuration in Python:

```python
filter_value = self._configuration.get_config_value(
    self._session,
    'plugins.example_plugin.filter_status',
    'ACTIVE'
)
```

### Conditional Code Blocks

Use annotations in SQL to conditionally include code based on configuration:

```sql
--%PLUGIN:example_plugin:
-- This code is only included when example_plugin is enabled
create or replace procedure DTAGENT_DB.APP.SOME_PROCEDURE() ...
--%:PLUGIN:example_plugin

--%OPTION:dtagent_admin:
-- This code is only included when admin role is enabled
grant role SOME_ROLE to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin
```

### Multiple Context Names

If your plugin reports data in multiple contexts, you can override the context name:

```python
# In your process() method
entries_cnt1, logs_cnt1, metrics_cnt1, _ = self._log_entries(
    lambda: self._get_table_rows(query1),
    "example_plugin_context1",  # Custom context name
    run_uuid=run_id,
    log_completion=False,
)

entries_cnt2, logs_cnt2, metrics_cnt2, _ = self._log_entries(
    lambda: self._get_table_rows(query2),
    "example_plugin_context2",  # Another context
    run_uuid=run_id,
    log_completion=False,
)

# Report combined results
self._report_execution(
    "example_plugin",
    current_timestamp(),
    None,
    {
        "context1": {"entries": entries_cnt1, "log_lines": logs_cnt1, "metrics": metrics_cnt1},
        "context2": {"entries": entries_cnt2, "log_lines": logs_cnt2, "metrics": metrics_cnt2},
    },
    run_id=run_id,
)
```

---

## Common Patterns

### Pattern 1: Simple Log and Metric Plugin

Best for plugins that report static or snapshot data.

**Example:** `budgets`, `data_schemas`, `dynamic_tables`

**Characteristics:**

- One log entry per entity
- Metrics are counts or gauge values
- No parent-child relationships
- Data is relatively static

**Implementation:**

```python
def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
    query = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_PLUGIN_INSTRUMENTED())"

    entries, logs, metrics, events = self._log_entries(
        lambda: self._get_table_rows(query),
        "plugin_name",
        run_uuid=run_id,
        report_metrics=True,
        log_completion=run_proc,
    )

    return self._report_results(
        {"plugin_name": {"entries": entries, "log_lines": logs, "metrics": metrics, "events": events}},
        run_id,
    )
```

### Pattern 2: Incremental Data Processing

Best for plugins that track changes over time.

**Example:** `warehouse_usage`, `event_log`

**Characteristics:**

- Tracks last processed timestamp
- Only processes new/changed data
- Uses `F_LAST_PROCESSED_TS()` to avoid duplicates

**SQL Implementation:**

```sql
select *
from SNOWFLAKE.ACCOUNT_USAGE.SOME_HISTORY
where START_TIME > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('plugin_name')
```

### Pattern 3: Hierarchical Span Plugin

Best for plugins that track operations with parent-child relationships.

**Example:** `query_history`, `login_history`

**Characteristics:**

- Reports distributed traces
- Has parent-child relationships
- Includes span events
- Tracks query execution details

**Implementation:**

```python
def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
    def __f_span_events(d_span: Dict) -> Tuple[List[Dict], int]:
        # Extract events from span data
        return events_list, error_count

    query = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_PLUGIN_INSTRUMENTED())"

    ids, errors, span_events, spans, logs, metrics = self._process_span_rows(
        lambda: self._get_table_rows(query),
        view_name="plugin_view",
        context_name="plugin_name",
        run_uuid=run_id,
        f_span_events=__f_span_events,
        log_completion=run_proc,
    )

    return self._report_results(
        {
            "plugin_name": {
                "entries": len(ids),
                "errors": errors,
                "span_events": span_events,
                "spans": spans,
                "log_lines": logs,
                "metrics": metrics,
            }
        },
        run_id,
    )
```

### Pattern 4: Multi-View Plugin

Best for plugins that combine data from multiple sources.

**Example:** `warehouse_usage` (event history, load history, metering history)

**Characteristics:**

- Multiple instrumented views
- Combines different aspects of same domain
- Each view reports different telemetry

**Implementation:**

```python
def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
    # Process first view
    entries1, logs1, metrics1, _ = self._log_entries(
        lambda: self._get_table_rows("SELECT * FROM VIEW1"),
        "plugin_context1",
        run_uuid=run_id,
        log_completion=False,
    )

    # Process second view
    entries2, logs2, metrics2, _ = self._log_entries(
        lambda: self._get_table_rows("SELECT * FROM VIEW2"),
        "plugin_context2",
        run_uuid=run_id,
        log_completion=False,
    )

    # Report combined execution
    self._report_execution(
        "plugin_name",
        current_timestamp(),
        None,
        {
            "context1": {"entries": entries1, "log_lines": logs1, "metrics": metrics1},
            "context2": {"entries": entries2, "log_lines": logs2, "metrics": metrics2},
        },
        run_id=run_id,
    )

    return self._report_results(
        {
            "context1": {"entries": entries1, "log_lines": logs1, "metrics": metrics1},
            "context2": {"entries": entries2, "log_lines": logs2, "metrics": metrics2},
        },
        run_id,
    )
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Plugin not found/not loaded

**Symptoms:**

- Error message: "Plugin {name} not implemented"
- Plugin doesn't run when called

**Solutions:**

1. Check class naming: Must be `{CamelCase}Plugin`
2. Verify file is in `src/dtagent/plugins/` directory
3. Ensure `PLUGIN_NAME` constant matches file name
4. Rebuild: `./scripts/dev/build.sh`

#### Issue: SQL syntax errors during deployment

**Symptoms:**

- Deployment fails with SQL errors
- Objects not created in Snowflake

**Solutions:**

1. Check SQL syntax in `.sql` files
2. Verify all object names are UPPERCASE
3. Ensure proper USE statements: `use role DTAGENT_OWNER; use database DTAGENT_DB;`
4. Check for balanced `BEGIN/END` blocks
5. Test SQL manually in Snowflake worksheet

#### Issue: No data appears in Dynatrace

**Symptoms:**

- Plugin runs successfully
- No logs/metrics in Dynatrace

**Solutions:**

1. Check plugin configuration: `is_disabled: false`
2. Verify telemetry types are enabled in config
3. Check Dynatrace tenant connection
4. Verify API key has correct permissions
5. Check agent logs for errors:

   ```sql
   SELECT * FROM DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG
   WHERE CONTEXT LIKE '%plugin_name%'
   ORDER BY TIMESTAMP DESC;
   ```

#### Issue: Task not running on schedule

**Symptoms:**

- Task exists but doesn't execute
- Manual execution works

**Solutions:**

1. Check task status:

   ```sql
   SHOW TASKS LIKE 'TASK_DTAGENT_%' IN SCHEMA DTAGENT_DB.APP;
   ```

2. Verify task is resumed:

   ```sql
   ALTER TASK DTAGENT_DB.APP.TASK_DTAGENT_PLUGIN_NAME RESUME;
   ```

3. Check schedule configuration in config file
4. Update schedule:

   ```sql
   CALL DTAGENT_DB.CONFIG.UPDATE_PLUGIN_NAME_CONF();
   ```

#### Issue: Test failures

**Symptoms:**

- `pytest` fails for plugin tests
- Mismatched telemetry counts

**Solutions:**

1. Regenerate test data: `./scripts/dev/test.sh test_plugin -p`
2. Check pickle file exists in `test/test_data/`
3. Verify base_count matches expected output
4. Check that `affecting_types_for_entries` includes all relevant types
5. Run with verbose output: `pytest -s -v test/plugins/test_plugin.py`

#### Issue: Configuration not applied

**Symptoms:**

- Changed configuration doesn't take effect
- Plugin uses old schedule

**Solutions:**

1. Redeploy configuration:

   ```bash
   ./scripts/deploy/deploy.sh YOUR_ENV --scope=config
   ```

2. Manually update:

   ```sql
   CALL DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();
   CALL DTAGENT_DB.CONFIG.UPDATE_PLUGIN_NAME_CONF();
   ```

3. Check configuration table:

   ```sql
   SELECT * FROM DTAGENT_DB.CONFIG.CONFIGURATIONS;
   ```

#### Issue: Semantic fields not recognized

**Symptoms:**

- Fields don't appear in Dynatrace
- Metrics not charted correctly

**Solutions:**

1. Verify `instruments-def.yml` syntax
2. Ensure field names match between SQL and semantic dictionary
3. Follow [naming conventions](CONTRIBUTING.md#field-and-metric-naming-rules)
4. Rebuild documentation: `./scripts/dev/build_docs.sh`
5. Check that SQL view uses exact same field names

---

## Additional Resources

- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development environment setup, building, testing
- **[PLUGINS.md](PLUGINS.md)**: Comprehensive documentation of all existing plugins
- **[SEMANTICS.md](SEMANTICS.md)**: Complete semantic dictionary reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Agent architecture and design
- **[INSTALL.md](INSTALL.md)**: Deployment and configuration guide

### Helpful DQL Queries

**Check plugin execution:**

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "your_plugin"
| sort timestamp desc
| limit 100
```

**Count telemetry by plugin:**

```dql
fetch logs
| filter db.system == "snowflake"
| summarize count(), by: {dsoa.run.context}
```

**Monitor plugin performance:**

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "self_monitoring"
| filter contains(content, "your_plugin")
| fields timestamp, content, entries, log_lines, metrics
```

### Example Plugins to Study

Start with these plugins as references:

1. **Simple plugin:** `budgets` - Basic log/metric reporting
2. **Incremental plugin:** `warehouse_usage` - Tracks changes over time
3. **Multi-view plugin:** `warehouse_usage` - Multiple data sources
4. **Span plugin:** `query_history` - Hierarchical traces
5. **Complex plugin:** `trust_center` - Advanced processing and logic

---

## Summary Checklist

When creating a new plugin, ensure you have:

- [ ] Created plugin directory structure
- [ ] Written Python plugin class inheriting from `Plugin`
- [ ] Implemented `process()` method
- [ ] Created instrumented SQL view/procedure
- [ ] Created task definition (801_*.sql)
- [ ] Created configuration update procedure (901_*.sql)
- [ ] Created plugin configuration YAML file
- [ ] Defined semantic dictionary (instruments-def.yml)
- [ ] Documented plugin in readme.md
- [ ] Created BOM file (bom.yml)
- [ ] Written plugin tests
- [ ] Generated test data (pickle files)
- [ ] Verified tests pass
- [ ] Built the agent (`./scripts/dev/build.sh`)
- [ ] Deployed to test environment
- [ ] Verified data appears in Dynatrace
- [ ] Updated any relevant documentation

**Congratulations! You've created a complete Dynatrace Snowflake Observability Agent plugin!**

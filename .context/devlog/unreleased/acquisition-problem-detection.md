# [Unreleased] — Acquisition Problem Detection

## Motivation

`_get_table_rows()` in `plugins/__init__.py` and `_get_sub_rows()` in `otel/spans.py` called `session.sql()` / `session.table()` with no exception handling. A `SnowparkSQLException` (e.g. view missing, permission error, network timeout) would propagate up to `agent.py` where only `RuntimeError` was caught — `SnowparkSQLException` is not a `RuntimeError`, so it would crash the entire agent run, silencing all subsequent plugins for that execution.

## Implementation

**New class — `AcquisitionProblemCollector` in `src/dtagent/otel/ingest_warnings.py`**

Added alongside `IngestWarningCollector` in the same module. Thread-safe static-method collector, same pattern. Problem dict schema: `problem_type`, `source`, `detail`, `count`.

**`_get_table_rows` — `src/dtagent/plugins/__init__.py`**

Wrapped entire SQL execution + row iteration in `try/except SnowparkSQLException`. On exception: logs `ERROR`, calls `AcquisitionProblemCollector.add_problem("sql_error", ...)`, yields nothing (graceful degradation — plugin reports 0 entries).

**`_get_sub_rows` — `src/dtagent/otel/spans.py`**

Same pattern for sub-row queries. On `SnowparkSQLException`: logs `ERROR`, calls `AcquisitionProblemCollector.add_problem("sub_row_error", ...)`, yields nothing. Uses inline `from dtagent import LOG  # COMPILE_REMOVE` (consistent with `metrics.py` pattern).

**Bizevent emission — `src/dtagent/__init__.py` + `src/dtagent/agent.py`**

`AbstractDynatraceSnowAgentConnector._emit_acquisition_problems()` follows the same structure as `_emit_ingest_warnings()`. Called on both success and error paths in the agent loop (before `handle_interrupted_run`). Always calls `AcquisitionProblemCollector.reset()` in `finally`.

**Compile assembly — `src/dtagent/agent.py` + `src/dtagent/connector.py`**

Added `from snowflake.snowpark.functions import col` and `from snowflake.snowpark.exceptions import SnowparkSQLException` to `GENERAL_IMPORTS` in both entry-point files (these were previously inline `# COMPILE_REMOVE` imports that didn't survive compilation).

**Config — `conf/config-template.yml`**

Added `plugins.self_monitoring.detect_acquisition_problems: true` (default on).

**Dashboard — `docs/dashboards/self-monitoring/self-monitoring.yml`**

Added tiles 17 and 18 (row at `y=37`):

- Tile 17: `Acquisition problems over time` — `makeTimeseries` line chart by problem type (7-day window).
- Tile 18: `Acquisition problem details` — table of recent problems sorted by timestamp desc.

**Tests — `test/otel/test_acquisition_problems.py`** (12 tests, new file)

- `TestAcquisitionProblemCollector`: 7 unit tests mirroring the ingest warning collector suite.
- `TestGetTableRowsSqlErrors`: 3 tests — clean query, exception at setup, exception during iteration.
- `TestGetSubRowsSqlErrors`: 2 tests — clean sub-row fetch, exception during fetch.

## Behavioral Change

Before: `SnowparkSQLException` propagated uncaught → crashed entire agent run → all subsequent plugins silenced.
After: Exception caught at the view-access level → plugin produces 0 entries + bizevent → agent continues to next plugin.

## Performance

No measurable overhead on the happy path — exception handling is zero-cost when no exception occurs.

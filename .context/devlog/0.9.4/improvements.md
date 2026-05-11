# Improvements — 0.9.4

## Execute as Caller Migration

- **Motivation**: All stored procedures used `execute as owner` (explicitly or implicitly), meaning they ran with `DTAGENT_OWNER` privileges regardless of the calling role. This widened the privilege surface unnecessarily — callers could mutate any owner-accessible object through procedure side-effects.
- **Approach**: Switch every procedure to `execute as caller` so it inherits the invoking role's permissions. This required expanding TMP table grants from `select` to `select, truncate, insert` (plus `update` where needed) for `DTAGENT_VIEWER`.
- **Changes by file**:

  | File                                                        | Changes                                                                                                                                                                                                                                                |
  |-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | `resource_monitors.sql/060_p_refresh_resource_monitors.sql` | Grants: `select` → `select, truncate, insert` on `TMP_RESOURCE_MONITORS`, `TMP_WAREHOUSES`. Execution: `owner` → `caller`.                                                                                                                             |
  | `budgets.sql/040_p_get_budgets.sql`                         | Grants: `select` → `select, truncate, insert` on 4 TMP tables. Execution: `owner` → `caller`.                                                                                                                                                          |
  | `users.sql/051_p_get_users.sql`                             | Grants: expanded on `TMP_USERS`, `TMP_USERS_HELPER`, `EMAIL_HASH_MAP` (+ `update, delete`). Refactored `TMP_USERS_SNAPSHOT` from temporary table (created inside procedure) to pre-created transient table with grants. Execution: `owner` → `caller`. |
  | `query_history.sql/061_p_refresh_recent_queries.sql`        | Grants: `select` → `select, truncate, insert, update` on `TMP_RECENT_QUERIES`; `select` → `select, truncate, insert` on `TMP_QUERY_OPERATOR_STATS`. Execution: `owner` → `caller`.                                                                     |
  | `query_history.sql/061_p_get_acc_estimates.sql`             | Grants: `select` → `select, truncate, insert` on `TMP_QUERY_ACCELERATION_ESTIMATES`. Execution: `owner` → `caller`.                                                                                                                                    |
  | `query_history.sql/110_update_processed_queries.sql`        | Added explicit `execute as caller` (was implicit owner).                                                                                                                                                                                               |
  | `setup/100_log_processed_measurements.sql`                  | Added explicit `execute as caller` (was implicit owner).                                                                                                                                                                                               |
  | `event_log.sql/admin/071_p_cleanup_event_log.sql`           | Execution: `owner` → `caller`.                                                                                                                                                                                                                         |
  | `shares.sql/051_p_grant_imported_privileges.sql`            | Replaced with no-op stub (`execute as caller`). Real implementation moved to `shares.sql/admin/051_p_grant_imported_privileges.sql` with `execute as caller` under `DTAGENT_ADMIN` scope.                                                              |
  | `query_history.sql/061_p_query_explain_plan.off.sql`        | Deleted (disabled procedure, dead code).                                                                                                                                                                                                               |

- **Regression test**: `test/bash/test_execute_as_owner.bats` — two tests:
  1. Scans all `.sql` source files for explicit `execute as owner` usage.
  2. Verifies every `CREATE PROCEDURE` has an explicit `execute as` clause (prevents implicit owner default).
  Both tests support an exclusion list for justified exceptions (currently empty).

## Timestamp Handling Refactoring

- **Motivation**: Eliminate wasteful ns→ms→ns conversions and clarify API requirements
- **Approach**: Unified timestamp handling with smart unit detection
- **Implementation**:
  - All SQL views produce nanoseconds via `extract(epoch_nanosecond ...)`
  - Conversion to appropriate unit occurs only at API boundary
  - `validate_timestamp()` works internally in nanoseconds to preserve precision
  - Added `return_unit` parameter ("ms" or "ns") for explicit output control
  - Added `skip_range_validation` parameter for `observed_timestamp` (no time range check)
  - Created `process_timestamps_for_telemetry()` utility for standard timestamp processing pattern
- **Changes to `validate_timestamp()`**:
  - Works internally in nanoseconds throughout validation logic
  - Converts to requested unit only at the end
  - Raises `ValueError` if `return_unit` not in ["ms", "ns"]
  - Added `skip_range_validation` for observed_timestamp (preserves original value without range checks)
- **Changes to `process_timestamps_for_telemetry()`**:
  - New utility function implementing standard pattern for logs and events
  - Extracts `timestamp` and `observed_timestamp` from data dict
  - Falls back to `timestamp` value when `observed_timestamp` not provided
  - Validates `timestamp` with range checking (returns milliseconds)
  - Validates `observed_timestamp` without range checking (returns nanoseconds)
  - Returns `(timestamp_ms, observed_timestamp_ns)` tuple
  - Hardcoded units: always milliseconds for timestamp, nanoseconds for observed_timestamp
- **Removed obsolete functions**:
  - `get_timestamp_in_ms()` — replaced by `validate_timestamp(value, return_unit="ms")`
  - `validate_timestamp_ms()` — replaced by `validate_timestamp(value, return_unit="ms")`
- **Added new functions**:
  - `get_timestamp()` — returns nanoseconds from SQL query results
- **API Documentation**:
  - Added comprehensive documentation links in all telemetry classes
  - Documented Dynatrace OTLP Logs API deviation (milliseconds for `timestamp` field)
  - Documented OTLP standard requirements (nanoseconds for most timestamp fields)
- **Fallback Logic**:
  - `observed_timestamp` now correctly falls back to `timestamp` value when not provided
  - Only `event_log` plugin provides explicit `observed_timestamp` values
  - All other plugins rely on fallback mechanism

## Build System Virtual Environment

- **Change**: All `scripts/dev/` scripts now auto-activate `.venv/`
- **Implementation**: Added `source .venv/bin/activate` to script preambles
- **Impact**: Eliminates common "wrong Python" errors during development

## Documentation — Autogenerated Files

- **Change**: Updated `.github/copilot-instructions.md` with autogenerated file documentation
- **Coverage**:
  - Documentation files: `docs/PLUGINS.md`, `docs/SEMANTICS.md`, `docs/APPENDIX.md`
  - Build artifacts: `build/_dtagent.py`, `build/_send_telemetry.py`, `build/_semantics.py`, `build/_version.py`, `build/_metric_semantics.txt`
- **Guidance**: Never edit autogenerated files manually; edit source files and regenerate

## Budgets Plugin Enhancement

- **Change**: Enhanced budget data collection using `SYSTEM$SHOW_BUDGETS_IN_ACCOUNT()`
- **Previous**: Manual query construction
- **New**: Leverages Snowflake system function for comprehensive budget data
- **Impact**: More accurate and complete budget information

## Error Handling — Two-Phase Commit for Query Telemetry

- **Issue**: `STATUS.UPDATE_PROCESSED_QUERIES` was called regardless of whether the OTLP trace flush succeeded, meaning queries could be silently lost on export failures without being retried on the next cycle.
- **Root cause**: `_process_span_rows` in `src/dtagent/plugins/__init__.py` called `UPDATE_PROCESSED_QUERIES` unconditionally after `flush_traces()`.
- **Fix**: Captured the boolean return value of `flush_traces()` into `flush_succeeded` and gated the `UPDATE_PROCESSED_QUERIES` call behind `if report_status and flush_succeeded`.
- **Impact**: Queries whose spans fail to export are re-queued on the next agent run, ensuring at-least-once delivery semantics for span telemetry.

## Event Log Lookback — Configurable Window

- **Issue**: `V_EVENT_LOG` used a hardcoded `timeadd(hour, -24, current_timestamp)` lower bound, preventing operators from adjusting the lookback window without editing SQL.
- **Fix**:
  - `src/dtagent/plugins/event_log.sql/051_v_event_log.sql`: replaced literal with `CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.lookback_hours', 24)::int`.
  - `src/dtagent/plugins/event_log.config/event_log-config.yml`: added `lookback_hours: 24` (default preserves prior behaviour).
- **Impact**: Operators can increase the window for initial deployments or decrease it for high-volume environments without any SQL change.

## AI-Assisted Development Infrastructure (Vibe Coding)

- **Motivation**: Enable AI coding assistants (GitHub Copilot, OpenCode, Windsurf) to work effectively with the DSOA codebase by providing structured project context, domain knowledge, and safety guardrails — reducing onboarding time and preventing common mistakes.
- **Central instructions file** (`.github/copilot-instructions.md`, 264 lines):
  - "DSOA coding sidekick" persona definition
  - Core architecture overview and key module map (agent lifecycle, plugin system, core modules)
  - Mandatory Snowflake connection safety rules (system roles forbidden, deployment limited to `test-qa`)
  - Code style enforcement expectations (black, flake8, pylint 10.00/10, sqlfluff, markdownlint)
  - 4-phase delivery workflow (Proposal → Plan → Implement → Validate) with artifact storage in `.context/proposals/`
  - Continuous learning loop: AI updates instructions/skills after every human review to prevent recurring mistakes
  - Git tracking rules, auth patterns, plugin isolation principles, SQL/Python syntax conventions
- **OpenCode integration**:
  - `.opencode/opencode.json` (tracked) links OpenCode agent to `.github/copilot-instructions.md`
  - `.opencode/package-lock.json` (tracked) pins `@opencode-ai/plugin` v1.4.3 dependency
  - `.opencode/.gitignore` excludes local runtime artifacts (`node_modules`, `package.json`, `bun.lock`)
- **Seven domain skills** (`.opencode/skills/`, ~3,500 lines total, all tracked)
- **Private context scaffold**: `.context/` directory (gitignored per `.context/.gitignore`) provides entry points for developer-local planning artifacts
- **Security model**: Credentials/sensitive context stay local. Instructions document safe patterns (`read_secret()`, `_snowflake.py` module). AI guardrails prevent accidental role escalation or credential commits.

## Query Hierarchy Validation

- **Goal**: Confirm that nested stored procedure call chains are correctly represented as OTel parent-child spans.
- **Validation approach**:
  - `P_REFRESH_RECENT_QUERIES` sets `IS_ROOT=TRUE` for top-level calls (no `parent_query_id`) and `IS_PARENT=TRUE` for any query that has at least one child in the same batch. Leaf queries have `IS_ROOT=FALSE, IS_PARENT=FALSE`.
  - `_process_span_rows` in `src/dtagent/plugins/__init__.py` iterates only `IS_ROOT=TRUE` rows as top-level spans; child spans are fetched recursively via `Spans._get_sub_rows` using `PARENT_QUERY_ID`.
  - `ExistingIdGenerator` in `src/dtagent/otel/spans.py` propagates the root's `_TRACE_ID` and `_SPAN_ID` down the hierarchy so every sub-span shares the correct trace context.
- **New test fixture**: `test/test_data/query_history_nested_sp.ndjson` — 3-row synthetic SP chain: outer SP (root) → inner SP (mid) → leaf SELECT.
- **New test file**: `test/plugins/test_query_history_span_hierarchy.py`
  - `test_span_hierarchy`: integration test verifying 3 entries processed, 3 spans, 3 logs, 27 metrics across all `disabled_telemetry` combinations.
  - `test_is_root_only_processes_top_level`: unit test confirming only 1 root row and 2 non-root rows in the fixture.
  - `test_is_parent_flags_intermediate_nodes`: unit test asserting correct `IS_ROOT`/`IS_PARENT`/`PARENT_QUERY_ID` values for each level of the hierarchy.

## Test Infrastructure Refactoring

- **Change**: Refactored tests to use synthetic JSON fixtures
- **Previous**: Live Dynatrace API calls for validation
- **New**: Input/output validation against golden JSON files
- **Impact**: Faster, more reliable, deterministic tests

## Event Tables Cost Optimization Documentation

- **Change**: Expanded `event_log.config/config.md` from a minimal 5-line note to a full configuration reference
- **Content added**:
  - Configuration options table covering all 7 plugin settings with types, defaults, and descriptions
  - Cost optimization guidance section explaining the cost impact of `LOOKBACK_HOURS`, `MAX_ENTRIES`, `RETENTION_HOURS`, and `SCHEDULE`
  - Key guidance: `retention_hours` should be `>= lookback_hours` to prevent cleanup from removing events before they are processed
- **Files changed**:
  - `src/dtagent/plugins/event_log.config/config.md` — full configuration reference + cost guidance
  - `src/dtagent/plugins/event_log.config/readme.md` — updated to mention configurable lookback window

## Span Timestamp Handling Fix

- **Issue**: `_process_span_rows()` in `src/dtagent/plugins/__init__.py` called `_report_execution()` with `current_timestamp()` (a Snowflake lazy column expression) instead of the actual last-row timestamp.
- **Root cause**: When `STATUS.LOG_PROCESSED_MEASUREMENTS` stored this value, it received the string `'Column[current_timestamp]'` rather than a real timestamp. On the next run, `F_LAST_PROCESSED_TS` would return a malformed value, causing the `GREATEST(...)` guard in each SQL view to use the fallback lookback window — potentially re-processing spans already sent.
- **Fix**: Added `last_processed_timestamp` variable tracking `row_dict.get("TIMESTAMP", last_processed_timestamp)` within the row iteration loop, mirroring the identical pattern used by `_log_entries()`. Passed `str(last_processed_timestamp)` to `_report_execution()` instead of `current_timestamp()`.
- **Side effect removed**: Dropped the now-unused `from snowflake.snowpark.functions import current_timestamp` import — pylint flagged this as unused after the fix.
- **Impact**: Spans and traces will no longer be re-processed after an agent restart. The `F_LAST_PROCESSED_TS('event_log_spans')` guard now advances correctly after each run.
- **Affects**: `event_log` plugin (`_process_span_entries`) and any future plugin using `_process_span_rows` with `log_completion=True`

# Development Log

This file documents detailed technical changes, internal refactorings, and development notes. For user-facing highlights, see [CHANGELOG.md](CHANGELOG.md).

## Version 0.9.4 — Detailed Changes

### New Features — Technical Details

#### Pipes Monitoring Plugin

- Implemented `PipesPlugin` to monitor Snowpipe status and validation
- Uses `SYSTEM$PIPE_STATUS` function for real-time pipe monitoring
- Uses `VALIDATE_PIPE_LOAD` function for validation checks
- Delivers telemetry as logs, metrics, and events

#### Streams Monitoring Plugin

- Implemented `StreamsPlugin` to monitor Snowflake Streams
- Tracks stream staleness using `SHOW STREAMS` output
- Monitors pending changes and stream health
- Reports stale streams as warning events

#### Stage Monitoring Plugin

- Implemented `StagePlugin` to monitor staged data
- Tracks internal and external stages
- Monitors COPY INTO activities from `QUERY_HISTORY` and `COPY_HISTORY` views
- Reports on staged file sizes, counts, and load patterns

#### Data Lineage Plugin

- Implemented `DataLineagePlugin` combining static and dynamic lineage
- Static lineage from `OBJECT_DEPENDENCIES` view (DDL-based relationships)
- Dynamic lineage from `ACCESS_HISTORY` view (runtime data flow)
- Column-level lineage tracking with direct and indirect dependencies
- Lineage graphs delivered as structured events

#### Configurable Lookback Time

- Added per-plugin `lookback_hours` configuration parameter
- Previously hardcoded to 24 hours for all plugins
- Allows fine-tuning historical data catchup per use case
- Default remains 24 hours for backward compatibility

### Bug Fixes — Technical Details

#### Log ObservedTimestamp Unit Correction

- **Issue**: OTel log `observed_timestamp` field was sent in milliseconds
- **Root cause**: OTLP spec requires nanoseconds for `observed_timestamp`, but code was converting to milliseconds
- **Fix**: Modified `process_timestamps_for_telemetry()` to return `observed_timestamp_ns` in nanoseconds
- **Impact**: Logs now comply with OTLP spec
- **Note**: Dynatrace OTLP Logs API still requires milliseconds for `timestamp` field (deviation from spec)

#### Inbound Shares Reporting Flag

- **Issue**: `HAS_DB_DELETED` flag incorrectly reported for deleted shared databases in `TMP_SHARES` view
- **Root cause**: Logic error in SQL view predicate
- **Fix**: Corrected SQL logic in `shares.sql/` view definition
- **Impact**: Accurate reporting of deleted shared database status

#### Self-Monitoring Log Filtering

- **Issue**: Database name filtering logic failed to correctly identify DTAGENT_DB references
- **Root cause**: String matching logic didn't account for fully qualified names
- **Fix**: Updated filtering logic in self-monitoring plugin
- **Impact**: Self-monitoring logs now correctly exclude internal agent operations

### Improvements — Technical Details

#### Timestamp Handling Refactoring

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

#### Build System Virtual Environment

- **Change**: All `scripts/dev/` scripts now auto-activate `.venv/`
- **Implementation**: Added `source .venv/bin/activate` to script preambles
- **Impact**: Eliminates common "wrong Python" errors during development

#### Documentation — Autogenerated Files

- **Change**: Updated `.github/copilot-instructions.md` with autogenerated file documentation
- **Coverage**:
  - Documentation files: `docs/PLUGINS.md`, `docs/SEMANTICS.md`, `docs/APPENDIX.md`
  - Build artifacts: `build/_dtagent.py`, `build/_send_telemetry.py`, `build/_semantics.py`, `build/_version.py`, `build/_metric_semantics.txt`
- **Guidance**: Never edit autogenerated files manually; edit source files and regenerate

#### Budgets Plugin Enhancement

- **Change**: Enhanced budget data collection using `SYSTEM$SHOW_BUDGETS_IN_ACCOUNT()`
- **Previous**: Manual query construction
- **New**: Leverages Snowflake system function for comprehensive budget data
- **Impact**: More accurate and complete budget information

#### Error Handling — Two-Phase Commit for Query Telemetry (BDX-694 / BDX-706)

- **Issue**: `STATUS.UPDATE_PROCESSED_QUERIES` was called regardless of whether the OTLP trace flush succeeded, meaning queries could be silently lost on export failures without being retried on the next cycle.
- **Root cause**: `_process_span_rows` in `src/dtagent/plugins/__init__.py` called `UPDATE_PROCESSED_QUERIES` unconditionally after `flush_traces()`.
- **Fix**: Captured the boolean return value of `flush_traces()` into `flush_succeeded` and gated the `UPDATE_PROCESSED_QUERIES` call behind `if report_status and flush_succeeded`.
- **Impact**: Queries whose spans fail to export are re-queued on the next agent run, ensuring at-least-once delivery semantics for span telemetry.

#### Event Log Lookback — Configurable Window (BDX-706)

- **Issue**: `V_EVENT_LOG` used a hardcoded `timeadd(hour, -24, current_timestamp)` lower bound, preventing operators from adjusting the lookback window without editing SQL.
- **Fix**:
  - `src/dtagent/plugins/event_log.sql/051_v_event_log.sql`: replaced literal with `CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.lookback_hours', 24)::int`.
  - `src/dtagent/plugins/event_log.config/event_log-config.yml`: added `lookback_hours: 24` (default preserves prior behaviour).
- **Impact**: Operators can increase the window for initial deployments or decrease it for high-volume environments without any SQL change.

#### Query Hierarchy Validation (BDX-620)

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
- **Impact**: Span hierarchies for stored procedure chains are confirmed correct and regression-protected.

#### Test Infrastructure Refactoring

- **Change**: Refactored tests to use synthetic JSON fixtures
- **Previous**: Live Dynatrace API calls for validation
- **New**: Input/output validation against golden JSON files
- **Impact**: Faster, more reliable, deterministic tests

#### Event Tables Cost Optimization

- **Change**: Added guidance documentation for Event Table usage
- **Content**: Fine-tuning strategies to manage Snowflake costs
- **Location**: Plugin documentation and configuration examples
- **Impact**: Users can optimize costs based on their use case

## Version 0.9.3 — Detailed Changes

Detailed technical changes for prior versions can be added here as needed.

## Version 0.9.2 — Detailed Changes

Detailed technical changes for prior versions can be added here as needed.

## Notes

- This file is **not** auto-generated. Manual maintenance required.
- Focus on **technical implementation details**, root causes, and internal changes.
- For user-facing release notes, see [CHANGELOG.md](CHANGELOG.md).
- Entries should help future developers understand decisions and troubleshoot issues.

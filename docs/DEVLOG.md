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

- **Motivation**: The lookback window was hardcoded to `timeadd(hour, -24, current_timestamp)` in all three `event_log` SQL views. This could not be tuned per deployment without modifying SQL files.
- **Approach**: Replace the literal `-24` with a call to `CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.lookback_hours', 24)` — consistent with how `retention_hours` is already handled in `P_CLEANUP_EVENT_LOG`.
- **Files changed**:
  - `src/dtagent/plugins/event_log.sql/051_v_event_log.sql` — lookback in log view
  - `src/dtagent/plugins/event_log.sql/051_v_event_log_metrics_instrumented.sql` — lookback in metrics view
  - `src/dtagent/plugins/event_log.sql/051_v_event_log_spans_instrumented.sql` — lookback in spans view
  - `src/dtagent/plugins/event_log.config/event_log-config.yml` — added `lookback_hours: 24` config key
- **Default**: `24` hours — backward compatible, no customer action required on upgrade
- **Note**: The `F_LAST_PROCESSED_TS` guard in each view's `GREATEST(...)` clause ensures normal incremental runs are unaffected; `lookback_hours` only bounds the fallback window when no prior timestamp exists

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

#### Query Hierarchy Validation

- **Change**: Improved span hierarchy validation using `parent_query_id` and `root_query_id`
- **Implementation**: Follows OpenTelemetry propagation standards
- **Impact**: Accurate query trace hierarchies in Dynatrace

#### Test Infrastructure Refactoring

- **Change**: Refactored tests to use synthetic JSON fixtures
- **Previous**: Live Dynatrace API calls for validation
- **New**: Input/output validation against golden JSON files
- **Impact**: Faster, more reliable, deterministic tests

#### Event Tables Cost Optimization Documentation (BDX-688)

- **Change**: Expanded `event_log.config/config.md` from a minimal 5-line note to a full configuration reference
- **Content added**:
  - Configuration options table covering all 7 plugin settings with types, defaults, and descriptions
  - Cost optimization guidance section explaining the cost impact of `LOOKBACK_HOURS`, `MAX_ENTRIES`, `RETENTION_HOURS`, and `SCHEDULE`
  - Key guidance: `retention_hours` should be `>= lookback_hours` to prevent cleanup from removing events before they are processed
- **Files changed**:
  - `src/dtagent/plugins/event_log.config/config.md` — full configuration reference + cost guidance
  - `src/dtagent/plugins/event_log.config/readme.md` — updated to mention configurable lookback window

#### Span Timestamp Handling Fix (BDX-706)

- **Issue**: `_process_span_rows()` in `src/dtagent/plugins/__init__.py` called `_report_execution()` with `current_timestamp()` (a Snowflake lazy column expression) instead of the actual last-row timestamp.
- **Root cause**: When `STATUS.LOG_PROCESSED_MEASUREMENTS` stored this value, it received the string `'Column[current_timestamp]'` rather than a real timestamp. On the next run, `F_LAST_PROCESSED_TS` would return a malformed value, causing the `GREATEST(...)` guard in each SQL view to use the fallback lookback window — potentially re-processing spans already sent.
- **Fix**: Added `last_processed_timestamp` variable tracking `row_dict.get("TIMESTAMP", last_processed_timestamp)` within the row iteration loop, mirroring the identical pattern used by `_log_entries()`. Passed `str(last_processed_timestamp)` to `_report_execution()` instead of `current_timestamp()`.
- **Side effect removed**: Dropped the now-unused `from snowflake.snowpark.functions import current_timestamp` import — pylint flagged this as unused after the fix.
- **Impact**: Spans and traces will no longer be re-processed after an agent restart. The `F_LAST_PROCESSED_TS('event_log_spans')` guard now advances correctly after each run.
- **Affects**: `event_log` plugin (`_process_span_entries`) and any future plugin using `_process_span_rows` with `log_completion=True`

## Version 0.9.3 — Detailed Changes

Detailed technical changes for prior versions can be added here as needed.

## Version 0.9.2 — Detailed Changes

Detailed technical changes for prior versions can be added here as needed.

## Notes

- This file is **not** auto-generated. Manual maintenance required.
- Focus on **technical implementation details**, root causes, and internal changes.
- For user-facing release notes, see [CHANGELOG.md](CHANGELOG.md).
- Entries should help future developers understand decisions and troubleshoot issues.

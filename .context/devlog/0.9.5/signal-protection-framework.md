# Feature: Signal Protection Framework for query_history Plugin

- **Problem**: On high-volume Snowflake accounts (e.g., LPL Financial), the `query_history` plugin processes every query completed in the last 120 minutes, causing timeouts and memory exhaustion when tens of thousands of queries execute per 30-minute window. No mechanism existed to cap signals, filter by warehouse/database/user, or prioritize interesting queries.
- **Solution**: Three complementary mechanisms:
  1. **Top-N Limiting** — `max_entries` config parameter caps rows processed per run. Rows are sorted by `max_entries_sort` (default: `execution_time DESC`) so expensive queries are always captured. When the cap is hit, a self-monitoring WARNING log and bizevent are emitted with dropped count.
  2. **Include/Exclude Filters** — SQL-level filters for `include_warehouses`, `exclude_warehouses`, `include_databases`, `exclude_databases`, `include_users`, `exclude_users` reduce the result set before Python processing, saving Snowflake compute. Exclude always takes precedence.
  3. **Watermark-Based Lookback** — Replaces hardcoded 120-minute window with last-processed timestamp from `STATUS.LOG_PROCESSED_MEASUREMENTS`, capped by `max_lookback_minutes` (default: 120). Enables incremental catch-up if agent was down >120 minutes.
- **Backward Compatibility**: All defaults preserve existing behavior: `max_entries=0` (unlimited), `max_lookback_minutes=120`, `exclude_warehouses=DTAGENT_WH` (agent's own warehouse only).
- **SQL Changes**:
  - `051_v_query_history.sql`: Added watermark-based lookback using `GREATEST(COALESCE(last_watermark, max_lookback), max_lookback)` pattern. Added WHERE clauses for include/exclude filters using `SPLIT_TO_TABLE` with `TRIM` to handle comma-separated lists. Filters applied in CTE for cost efficiency.
  - `061_p_refresh_recent_queries.sql`: Changed return type from `TEXT` to `OBJECT`. Added dynamic SQL to build ORDER BY and LIMIT clauses based on `max_entries` and `max_entries_sort` config. Procedure now returns object with `status`, `total_processed`, `total_available`, `max_entries_applied`, and `max_entries_value` for self-monitoring.
- **Python Changes**:
  - `query_history.py`: Added `_call_refresh_recent_queries()` method to call procedure via `session.sql()` and parse result object. Added `_emit_overload_protection_event()` to emit WARNING log and bizevent when `max_entries_applied=true` and `total_available > total_processed`. Self-monitoring attributes include dropped count, max_entries value, and protection flags.
- **Config Schema**:
  - `query_history-config.yml`: Added `max_entries`, `max_entries_sort`, `max_lookback_minutes`, `include_warehouses`, `exclude_warehouses`, `include_databases`, `exclude_databases`, `include_users`, `exclude_users` with sensible defaults.
  - `config-template.yml`: Added plugin-level config section with all new keys.
  - `config.md`: Documented all new parameters with examples and precedence rules (exclude > include).
  - `readme.md`: Added "Signal Protection Framework" section explaining the three mechanisms and backward compatibility.
- **Testing**:
  - `test_query_history.py`: Added `test_query_history_max_entries_limiting()` to verify self-monitoring event emission when cap is applied. Added `test_query_history_backward_compatibility()` to ensure default config (max_entries=0) processes all rows unchanged. Both tests pass with mock fixtures.
- **No Procedure Signature Changes**: `P_REFRESH_RECENT_QUERIES()` has no parameters, so no upgrade script needed. Return type change (TEXT → OBJECT) is transparent to callers.
- **Files Changed**: `src/dtagent/plugins/query_history.sql/051_v_query_history.sql`, `src/dtagent/plugins/query_history.sql/061_p_refresh_recent_queries.sql`, `src/dtagent/plugins/query_history.py`, `src/dtagent/plugins/query_history.config/query_history-config.yml`, `src/dtagent/plugins/query_history.config/config.md`, `src/dtagent/plugins/query_history.config/readme.md`, `conf/config-template.yml`, `test/plugins/test_query_history.py`

# Performance and Memory Handling Improvements

- **Root cause**: On high-volume Snowflake accounts, the hot-path `_cleanup_dict` → `_pack_values_to_json_strings`
  was creating excessive intermediate allocations. `_cleanup_dict` called `pd.isna(pd.Series(v))` on every dict
  value at every recursion level — creating a pandas Series object per value (~10–50μs each). For 5000 rows × 20
  attributes × 3 recursion levels this amounted to ~300K Series allocations. Additionally, `PAYLOAD_CACHE` in the
  events exporter accumulated all events until `_max_event_count` (default 400) with no byte-size guard.

- **Phase A — Hot-path optimization** (`src/dtagent/util.py`, `src/dtagent/plugins/event_log.py`):
  - Added `_is_nan_or_none(v)` helper using IEEE 754 identity (`v != v` for float NaN) and a try/except fallback
    for NaT-like types. No pandas dependency.
  - Refactored `_cleanup_dict` from double dict-comprehension (build inner dict, then filter) to single-pass loop
    that filters NaN/None/empty-dict/empty-list and cleans values in one pass.
  - Refactored `_pack_values_to_json_strings` level-0 branch to merge the filter step into the packing loop using
    walrus operator, eliminating the second dict pass.
  - Replaced `pd.isna(ts)` in `get_timestamp` with `_is_nan_or_none(ts)`.
  - Replaced `pd.isna(v)` in `event_log.py` with `_is_nan_or_none(v)`; removed `import pandas as pd` from that file.
  - **Note**: `import pandas as pd` in `agent.py` and `connector.py` is intentional — these files contain a
    `##region GENERAL_IMPORTS` block (marked "DO NOT OPTIMIZE") that is assembled into the compiled stored procedure.

- **Phase B — Export-side memory controls** (`src/dtagent/otel/events/__init__.py`, `src/dtagent/otel/metrics.py`,
  `src/dtagent/plugins/__init__.py`, `conf/config-template.yml`):
  - Events `PAYLOAD_CACHE`: replaced `PAYLOAD_CACHE += payload` (list concatenation) with per-event `append` plus
    incremental byte estimate tracking (`_cache_byte_estimate`). Flush now triggers on either count OR byte threshold.
    After flush, byte estimate is recalculated from remaining (failed) events only.
  - Metrics: replaced `sys.getsizeof(str.encode())` with `len(str.encode())` for accurate byte counting (removed
    Python object overhead inflation). Removed now-unused `import sys` from `metrics.py`.
  - GC interval: replaced hardcoded `100` in `_log_entries` with `self._gc_interval` read from
    `otel.performance.gc_interval` config key (default 100). Stored in `Plugin.__init__`.
  - New config keys added to `conf/config-template.yml` under `otel.performance`:
    - `gc_interval: 100`
    - `spans_batch_flush_size: 50`
    - `logs_batch_flush_size: 100`
  - New `agent` top-level config section added:
    - `agent.gc_collect_interval: 100` — canonical AC key; takes precedence over `otel.performance.gc_interval`
    - `agent.memory_tracking_enabled: false` — opt-in gate for peak RSS metric emission

- **Phase C — Memory self-monitoring** (`src/dtagent/plugins/__init__.py`, `test/core/test_performance.py`,
  `src/dtagent.conf/instruments-def.yml`):
  - Added `_get_peak_memory_mb()` module-level helper using `resource.getrusage(RUSAGE_SELF).ru_maxrss`.
    Handles platform difference: macOS returns bytes, Linux returns kilobytes.
  - `_report_execution` now emits `dsoa.agent.memory.peak_rss` gauge metric after each plugin context
    completes, guarded by `is_regular_mode()`, `NOT_ENABLED` check, **and** `agent.memory_tracking_enabled`
    config flag (default `false` — opt-in to avoid overhead on accounts that don't need it).
  - `dsoa.agent.memory.peak_rss` registered in `src/dtagent.conf/instruments-def.yml` with description and unit.
  - Added `test/core/test_performance.py` with:
    - 14 unit tests for `_is_nan_or_none` covering all value types.
    - Benchmark: `_cleanup_dict` on 1000 rows must complete in <1ms/row.
    - Benchmark: full hot-path on 1000 rows must complete in <1ms/row.
    - Memory regression: full hot-path on 5000 rows must not allocate >100MB above baseline (via `tracemalloc`).

- **Phase D — Streaming row processing** (`src/dtagent/plugins/__init__.py`):
  - `_process_span_rows`: added mid-batch flush every `self._span_batch_flush_size` (default 50) processed rows.
    Flushes metrics and force-flushes tracer provider, then calls `gc.collect()`.
  - `_log_entries`: added mid-batch flush every `self._log_batch_flush_size` (default 100) processed entries.
    Flushes events, metrics, and logs, then calls `gc.collect()`.
  - Both flush sizes are configurable via `otel.performance.spans_batch_flush_size` and
    `otel.performance.logs_batch_flush_size` config keys.

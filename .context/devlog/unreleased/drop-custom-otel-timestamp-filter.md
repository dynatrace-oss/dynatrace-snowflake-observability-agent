# [Unreleased] — BDX-1395: Drop CustomOTelTimestampFilter (direct Logger.emit path)

## Phase A — Research (green)

Confirmed OTel SDK 1.39.1 `Logger.emit()` accepts `timestamp` / `observed_timestamp` as keyword
args directly — no `LogRecord` construction needed. The OTLP encoder passes `timestamp` as-is to
`time_unix_nano` in the protobuf (confirmed via `_internal/_log_encoder/__init__.py:55`). Both
fields are in nanoseconds (OTLP standard). The prior `LoggingHandler` path already emitted ns:
`record.created = ms/1000` → `LoggingHandler` → `int(record.created * 1e9)` = `ms * 1_000_000`.
The "DT requires ms" note in the class docstring was stale — the OTLP endpoint accepts standard ns.
Wire output is identical before and after. **Phase A: green.**

## Phase B — Refactor `src/dtagent/otel/logs.py`

- **Removed** `CustomOTelTimestampFilter(logging.Filter)` — 43-line class that mutated
  `record.created`/`record.msecs` to inject timestamps into the stdlib→OTel bridge.
- **Removed** `LoggingHandler` — stdlib bridge to OTel exporter no longer needed.
- `self._otel_logger` is now an OTel `Logger` from `self._otel_logger_provider.get_logger(name)`.
  Instrumentation scope name (`DTAGENT[_TAG]_OTLP`) is preserved — passed directly to `get_logger`.
- `send_log()` calls `self._otel_logger.emit(timestamp=ms*1_000_000, observed_timestamp=ns, ...)`
  directly. `timestamp` and `observed_timestamp` are popped from the attributes dict before emit
  to prevent duplication.
- Added module-level `_SEVERITY_MAP` dict: Python logging levels → `SeverityNumber`
  (`LL_TRACE=5 → TRACE`, `DEBUG`, `INFO`, `WARNING → WARN`, `ERROR`, `CRITICAL → FATAL`).
- Removed unused `get_timestamp`, `validate_timestamp` imports from `util.py` (still used by
  `process_timestamps_for_telemetry` internally — only the direct top-level imports were dropped).

## Tests

- `TestLoggerNaming.test_logger_name_matches_get_logger_call` updated to assert
  `logger_provider.get_logger()` call instead of `logging.getLogger()`.
- `TestCustomOTelTimestampFilter` (300 lines) removed — tested the deleted filter class.
- Added `TestSeverityMapping` (7 cases): Python level → `SeverityNumber` including `LL_TRACE`.
- Added `TestEmitBoundary` (10 cases): timestamp ms→ns conversion, `None` body → `"-"`,
  timestamp/observed_timestamp absent from attributes, severity_number/text, multitenancy scope.

**Wire output**: unchanged. Same protobuf, same attributes, same instrumentation scope name.
**Affects**: `src/dtagent/otel/logs.py`, `test/otel/test_logs.py`.

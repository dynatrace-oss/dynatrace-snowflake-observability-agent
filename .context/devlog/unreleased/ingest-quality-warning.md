# [Unreleased] — Ingest-Quality Warning Detection

## Motivation

DSOA sends telemetry to Dynatrace over OTLP and REST APIs, but all three export paths (OTLP logs/spans, Metrics API v2, Events/BizEvents API) previously discarded HTTP response bodies on success. This meant partial rejections (`partialSuccess.rejectedLogRecords`, `linesInvalid`, `non_persisted_attribute_keys`, `rejectedEventIngestInputCount`) were silently swallowed — operators had no visibility until they noticed missing data in dashboards, often days later.

## Implementation

**New module — `src/dtagent/otel/ingest_warnings.py`**

Introduced `IngestWarningCollector`, a thread-safe static-method collector (same pattern as `OtelManager`). Accumulates structured warning dicts during a plugin run; reset after each plugin via `_emit_ingest_warnings()`. Warning schema: `warning_type`, `exporter`, `detail`, `count`.

**OTLP export path — `src/dtagent/otel/otel_manager.py`**

`CustomLoggingSession.send()` is the single intercept point for both logs and spans. Added defensive JSON parsing on HTTP 2xx to detect `partialSuccess.rejectedLogRecords` and `rejectedSpans`. Wrapped in `except Exception` with pylint suppress — malformed responses must never crash the agent.

**Metrics API v2 — `src/dtagent/otel/metrics.py`**

`__send` inner function now parses response body on 202 for `linesInvalid > 0` and `warnings[].non_persisted_attribute_keys`. The Dynatrace Metrics API v2 is the richest source of ingest-quality feedback — attribute trimming shows up here first.

**Events/BizEvents — `src/dtagent/otel/events/__init__.py`**

`AbstractEvents._send` now checks for `rejectedEventIngestInputCount` in the 202 response body. BizEvents inherits this check automatically.

**Bizevent emission — `src/dtagent/__init__.py` + `src/dtagent/agent.py`**

`AbstractDynatraceSnowAgentConnector._emit_ingest_warnings()` reads the collector, emits one `dsoa.ingest.warning` bizevent per warning entry (guarded by `self_monitoring.detect_ingest_warnings` config and `biz_events` telemetry being allowed), then calls `IngestWarningCollector.reset()` in a `finally` block. Called on both success and error paths in the agent loop.

**Compile assembly — `src/dtagent/agent.py` + `src/dtagent/connector.py`**

Added `##INSERT src/dtagent/otel/ingest_warnings.py` after `otel_manager.py` in both entry-point files. Added `import threading` to `GENERAL_IMPORTS` in both files (required by `IngestWarningCollector._lock`).

**Config — `conf/config-template.yml`**

Added `plugins.self_monitoring.detect_ingest_warnings: true` (default on).

**Dashboard — `docs/dashboards/self-monitoring/self-monitoring.yml`**

Added tiles 15 and 16:

- Tile 15: `Ingest warnings over time` — `makeTimeseries` line chart by exporter (7-day window).
- Tile 16: `Ingest warning detail` — table of recent warnings sorted by timestamp desc.

Layout: both tiles in a new row at `y=31`, split 12+12 columns.

**Tests — `test/otel/test_ingest_warnings.py`** (17 tests, new file)

- `TestIngestWarningCollector`: 7 unit tests covering add/get/has/reset/snapshot/default/thread-safety.
- `TestCustomLoggingSessionPartialSuccess`: 4 tests for OTLP partial success parsing (clean, logs rejected, spans rejected, malformed JSON).
- `TestMetricsIngestWarnings`: 4 tests for Metrics API v2 response parsing (clean, linesInvalid, attr_trimmed, malformed).
- `TestEventsIngestWarnings`: 2 tests for Events API response parsing (clean, rejectedEventIngestInputCount).

All tests use mock HTTP responses — no live Snowflake or DT connections required.

## Performance

Response body parsing runs only on successful responses (2xx). `json.loads()` on a typical <1 KB response body adds <0.1 ms. Warning bizevent emission happens at most once per plugin run when warnings are present — negligible overhead.

## Backward Compatibility

- Config default is `true` — existing deployments get detection automatically.
- No schema changes to existing telemetry.
- No SQL changes — no upgrade scripts needed.
- No procedure signature changes.

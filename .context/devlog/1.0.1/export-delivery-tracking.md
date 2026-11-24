# Export delivery tracking (attempted / delivered records per plugin and signal)

## Why

The processed counts on the tenant are taken when a record is handed to an exporter, not when Dynatrace accepted it, and a separate delivered
number could only be joined with them in a query (timing mismatches give inaccurate rates). Both numbers now travel together in one row/payload.

## What

- `otel/export_stats.py`: `ExportStatsCollector` (static methods + lock, like `IngestWarningCollector`). Counts keyed by `(plugin, run_id, signal)`;
  `set_plugin(name, run_id)` is called by `DynatraceSnowAgent.process()` per plugin run.
- Hooks (record counts, each record attempted once regardless of retries):
  - logs / spans: `export(batch)` override in the `CustomUserAgentOTLP*Exporter` subclasses; attempted is recorded before calling the
    underlying exporter (`OtelManager.record_export_attempt`), so a batch whose export raises (e.g. request timeout) is still counted; delivered
    (`OtelManager.record_export_delivered`) = `len(batch)` on SUCCESS minus `CustomLoggingSession.rejected_records` (OTLP `partialSuccess`).
  - metrics: `Metrics._send_metrics.__send`; attempted on the first send only (`_retries == 0`), delivered on 202 minus `linesInvalid`.
  - events / davis / biz events: attempted when events are enqueued in `AbstractEvents._send_events` (resends of events kept in `PAYLOAD_CACHE` are not
    counted again), delivered in `AbstractEvents._send` (202 minus `rejectedEventIngestInputCount`) and `DavisEvents._send` (per 201).
    Events that failed to send stay queued and can be delivered while a later plugin runs, so the `(plugin, run id)` that queued each event is stored
    (`AbstractEvents._event_attribution`, keyed by `id(event)`, pruned to the events still queued) and `_record_delivered` records the delivery for
    that plugin run, never for the one that is active. `ExportStatsCollector.add_attempted/add_delivered` take an optional `attribution`. When Dynatrace
    rejects some events of a request without saying which, the shortfall is taken from the last events of the request.
- `agent.main()`: `process` / `teardown` in `try/finally`; `persist_export_stats()` runs last, so batches flushed in `teardown()` are included, and
  also when processing fails. `DynatraceSnowAgent.process()` flushes logs after every plugin so that a manual multi-plugin call attributes log exports
  correctly. All scheduled tasks run exactly one plugin per call.
- `STATUS.EXPORT_STATS (RUN_TS, RUN_ID, PLUGIN, SIGNAL, ATTEMPTED, DELIVERED)`: `init/004_schema_status.sql` and `upgrade/1.0.1/020_create_export_stats.sql`.
  Config: `plugins.self_monitoring.export_stats_enabled` (default true), `export_stats_retention_days` (default 30; pruned on write). The insert is a
  single statement and any failure is logged and swallowed.
- `heartbeat`: new context `heartbeat_exports` (`APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()`) aggregating the table over `plugins.heartbeat.window_hours`;
  dimensions `dsoa.export.plugin` / `dsoa.export.signal` (not `dsoa.run.plugin`, which is already the emitting plugin), metrics
  `dsoa.heartbeat.export.attempted` / `.delivered`. `HeartbeatPlugin._get_table_rows` applies the expected-runs enrichment to the task rows only.

## Notes

- `DavisEvents._send` keeps for resending only events that failed with an exception; events answered with a non-201 status are dropped. Unchanged.
- `DavisEvents._send` has the same unassigned-`response` failure as `Metrics` when every POST raises and retries are exhausted.
- Spotted while testing, not changed: in `Metrics._send_metrics.__send`, when every POST raises a `RequestException` the retry-exhausted branch calls
  `OtelManager.increase_current_fail_count(response)` with `response` never assigned (`UnboundLocalError` instead of the intended failure accounting).
- `test_heartbeat_exports` uses synthetic rows shaped like the procedure output (the procedure was not run against Snowflake); regenerate with live
  credentials (`-p`) once the procedure is deployed.

## Tests

`test/otel/test_export_stats.py` (collector), `test/otel/test_export_stats_hooks.py` (every exporter: success, failure, partial rejection, retries,
no double counting), `test/core/test_export_stats_persistence.py` (attribution, insert, retention, disabled, failure swallowed, `main()` ordering),
`test/plugins/test_heartbeat_telemetry.py::test_heartbeat_exports`.

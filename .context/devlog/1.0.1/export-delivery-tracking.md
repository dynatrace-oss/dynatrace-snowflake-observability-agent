# Export delivery tracking (attempted / delivered records per plugin and signal)

## Why

The processed counts on the tenant are taken when a record is handed to an exporter, not when Dynatrace accepted it, and a separate delivered
number could only be joined with them in a query (timing mismatches give inaccurate rates). Both numbers now travel together in one row/payload.

## What

- `otel/export_stats.py`: `ExportStatsCollector` (static methods + lock, like `IngestWarningCollector`). Counts keyed by `(plugin, run_id, signal)`;
  `set_plugin(name, run_id)` is called by `DynatraceSnowAgent.process()` per plugin run.
- Hooks (record counts, each record attempted once regardless of retries):
  - logs / spans: `export(batch)` override in the `CustomUserAgentOTLP*Exporter` subclasses; attempted is recorded before calling the
    underlying exporter (`OtelManager.record_export_attempt`), so a batch whose export raises (e.g. request timeout) is still counted. The `(plugin, run id)` is captured once before the export and passed to both
    counters: the batch processor exports in a background thread, so the export can finish after processing moved on to the next plugin; delivered
    (`OtelManager.record_export_delivered`) = `len(batch)` on SUCCESS minus `CustomLoggingSession.rejected_records` (OTLP `partialSuccess`).
  - metrics: `Metrics._send_metrics.__send`; attempted on the first send only (`_retries == 0`), delivered on 202 minus `linesInvalid`.
  - events / davis / biz events: attempted when events are enqueued in `AbstractEvents._send_events` (resends of events kept in `PAYLOAD_CACHE` are not
    counted again), delivered in `AbstractEvents._send` (202 minus `rejectedEventIngestInputCount`) and `DavisEvents._send` (per 201).
    Events that failed to send stay queued and can be delivered while a later plugin runs, so the `(plugin, run id)` that queued each event is stored
    (`AbstractEvents._event_attribution`, keyed by `id(event)`, pruned to the events still queued) and `_record_delivered` records the delivery for
    that plugin run, never for the one that is active. `ExportStatsCollector.add_attempted/add_delivered` take an optional `attribution`. Every request carries
    events of a single plugin run (see PR review follow-ups), so a rejection reported for a request concerns that plugin run only.
- `agent.main()`: `process` / `teardown` in `try/finally`; `persist_export_stats()` runs last, so batches flushed in `teardown()` are included, and
  also when processing fails. `DynatraceSnowAgent.process()` flushes logs and spans after every plugin (also after one that ended with an error and
  did not flush them itself) so that a manual multi-plugin call attributes log exports
  correctly. All scheduled tasks run exactly one plugin per call.
- `STATUS.EXPORT_STATS (RUN_TS, RUN_ID, PLUGIN, SIGNAL, ATTEMPTED, DELIVERED)`: `init/004_schema_status.sql` and `upgrade/1.0.1/020_create_export_stats.sql`.
  Config: `plugins.self_monitoring.export_stats_enabled` (default true), `export_stats_retention_days` (default 30; pruned on write). The insert is a
  single statement and any failure is logged and swallowed.
- `heartbeat`: new context `heartbeat_exports` (`APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()`) aggregating the rows with `REPORTED_TS is null` and `RUN_TS <= cutoff` (cut-off = now - 1 minute, so uncommitted inserts are never marked);
  dimensions `dsoa.export.plugin` / `dsoa.export.signal` (not `dsoa.run.plugin`, which is already the emitting plugin), metrics
  `dsoa.heartbeat.export.attempted` / `.delivered`. `HeartbeatPlugin._get_table_rows` applies the expected-runs enrichment to the task rows only.

## PR review follow-ups

- Outage recovery: `STATUS.EXPORT_STATS.REPORTED_TS` is the watermark. `HeartbeatPlugin` remembers the `dsoa.heartbeat.export.reported_until` cut-off of the rows
  it emitted and, after flushing, marks `RUN_TS <= cutoff` as reported only when `ExportStatsCollector.delivery_confirmed(run_id)` (something was attempted and
  every attempted signal delivered at least one record - a heuristic, so persistent partial rejections do not cause endless replays). At-least-once: a delivered
  but unmarked interval is reported twice. `plugins.heartbeat.window_hours` no longer applies to export statistics.
- Statements in `persist_export_stats` bind their values (`session.sql(..., params=[...])`, multi-row `values (?, ...), (?, ...)`) instead of interpolating
  quoted literals, and name `DTAGENT_DB.STATUS.EXPORT_STATS` (the procedure runs as caller, so the current database may be another one).
- `SEND_TELEMETRY` (`connector.main`) sets the attribution (`telemetry_sender`, exec id) in `send_data` and persists the statistics after `teardown()`.
- Events: `_send_events` splits every request by queuing plugin run (`_split_by_attribution`), so a rejection reported for a request can only concern one
  plugin run and delivery attribution is exact (it no longer assumes the rejected events are the last ones).
- Not changed: the admin-scope indicator of `F_HEARTBEAT_INSTRUMENTED` (thread resolved as non-issue by the author).

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

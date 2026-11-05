# Removal of alerting events (moved to the Data Observability app)

## Scope

- `login_history`: dropped `_prepare_event_payload_failed_login` and the `event_column_to_check` trigger; failed-login rows are now plain logs.
- `trust_center`: dropped `_prepare_event_payload_critical_risk` and the CRITICAL event trigger; all findings go to logs (`_SEVERITY` still drives log level).
- `resource_monitors`: removed the band state machine (`_compute_band`, `_plan_transition`, state read/write/cleanup), the lazy `DavisEvents` sender,
  the `credits_quota_thresholds` config (plugin config, `conf/config-template.yml`) and the `011_resource_monitors_threshold_state.sql` table definition.
  `snowflake.credits.quota.*` metrics and the generic event-timestamp events are untouched, so the plugin keeps the `events` telemetry option.
- Upgrade script `src/dtagent.sql/upgrade/1.0.1/010_drop_rm_threshold_state.sql` drops `STATUS.RESOURCE_MONITOR_THRESHOLD_STATE` (idempotent).
- `events` removed from the default telemetry lists of `login_history` and `trust_center` (it only served the removed events).

## Tests

- `test_login_history` / `test_trust_center`: now assert `events: 0` in every `disabled_telemetry` combination; `logs.json` fixtures regenerated, `events.json` / `davis_events.json` fixtures removed.
- `test_resource_monitors_multirun.py` deleted; `TestEscapeSqlStr` and `TestComputeBand` removed from `test_resource_monitors.py` (code under test no longer exists).

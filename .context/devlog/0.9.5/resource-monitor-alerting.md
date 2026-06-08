# [0.9.5] — Resource Monitor Credit Threshold Alerting

## Resource Monitor Credit Threshold Alerting — Full Implementation

**Scope**: Added proactive credit-usage threshold monitoring to the existing `resource_monitors` plugin. Fires Davis events when a resource monitor's used-percentage crosses configurable bands, and resolves them automatically on recovery.

**Architecture**:

- **Band model**: Four severity levels — `info`, `warn`, `critical`, `exhausted` — mapped to configurable percentage thresholds. Default thresholds: `[50, 80, 90, 100]`. `info` band is persisted to state table to enforce one-shot emission (fires once on first crossing, not every run). No ACTIVE/CLOSED Davis event is opened for `info`; no resolution is sent. Bands below `info` produce no events and no state.
- **State persistence** (`DTAGENT_DB.STATUS.RESOURCE_MONITOR_THRESHOLD_STATE`): Stores `(MONITOR_NAME, LAST_BAND, LAST_USED_PCT, LAST_UPDATED)` per monitor between runs. MERGE for upsert, DELETE when band drops to `None`. Created by upgrade script `src/dtagent.sql/upgrade/0.9.5/010_create_rm_threshold_state.sql` (idempotent).
- **Transition logic** (`_plan_transition`): Pure function — given previous and current band, returns zero, one, or two `(status, level)` event actions (`ACTIVE` / `CLOSED`). Alert bands only participate in open/close transitions; `info` is informational only (logged, no Davis event). `None` (below info) never opens events.
- **Davis events**: Uses `DavisEvents` exporter (instantiated lazily on first threshold crossing). Event title: `"[ACCOUNT] Resource monitor {name} credits exceeded/dropped below {threshold_pct}% threshold"` (prefix omitted for warehouse-level monitors). Properties: `event.status=ACTIVE|CLOSED`, `snowflake.resource_monitor.threshold.direction`, `.level`, `.pct`, `snowflake.credits.quota.used_pct`, `snowflake.resource_monitor.level`, `.name`.
- **Write-after-emit ordering**: State is persisted only after the Davis event is successfully flushed, preventing ghost-open events on transient errors.
- **Configuration** (`credits_quota_thresholds`): Optional per-monitor override dict keyed by monitor name. Falls back to global defaults when monitor is absent or override is invalid. Validation: must be a list of 1–4 ascending integers in (0, 100]; values ≥100 trigger the `exhausted` band.

**New files**:

- `src/dtagent/plugins/resource_monitors.sql/011_resource_monitors_threshold_state.sql` — state table DDL + grants
- `src/dtagent.sql/upgrade/0.9.5/010_create_rm_threshold_state.sql` — idempotent upgrade script
- `test/plugins/test_resource_monitors_multirun.py` — pure-function unit tests (41 cases): full `_plan_transition` matrix, `_compute_band` edge cases, threshold resolution, `_process_threshold_for_rm` with stubbed I/O

**Modified files**:

- `src/dtagent/plugins/resource_monitors.py` — threshold logic methods + wired into `process()`
- `src/dtagent/plugins/resource_monitors.config/resource_monitors-config.yml` — `credits_quota_thresholds` config block
- `src/dtagent/plugins/resource_monitors.config/instruments-def.yml` — 4 new semantic attributes
- `src/dtagent/plugins/resource_monitors.config/bom.yml` — new state table entry
- `src/dtagent/plugins/resource_monitors.config/readme.md` — updated feature list
- `conf/config-template.yml` — documented threshold config

**Deployment**: Requires upgrade scope before main deploy: `./scripts/deploy/deploy.sh test-qa --scope=upgrade --from-version=0.9.4 --options=skip_confirm` then `--scope=plugins,config`

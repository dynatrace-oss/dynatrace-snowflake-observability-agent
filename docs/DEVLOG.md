# Development Log

This file documents detailed technical changes, internal refactorings, and development notes. For user-facing highlights, see [CHANGELOG.md](CHANGELOG.md).

## [Unreleased] — BDX-1904: Fix serverless_tasks empty namespace for account-level records

### Root cause

`SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY` is an account-level billing view. DSOA's own
scheduler tasks (`_MEASUREMENT_TASK`, `_FINALIZER_TASK`) run at account scope, so `database_name`
and `schema_name` are empty strings (not NULL) in the source view. `V_SERVERLESS_TASKS` passed
these directly into `OBJECT_CONSTRUCT`, causing `db.namespace = ""` and `snowflake.schema.name = ""`
in Dynatrace. Dashboard `$Database`/`$Schema` variable filters silently excluded all internal records.
Customer serverless tasks (warehouse-based, non-DSOA) do have populated `database_name`/`schema_name`
and were unaffected. Discovered during BDX-1815 dashboard work (TI-003).

### Fix — `061_v_serverless_tasks.sql`

Three changes in the `select` projection of `V_SERVERLESS_TASKS`:

1. **NULLIF guards**: `NULLIF(sth.database_name, '')` and `NULLIF(sth.schema_name, '')` in
   `OBJECT_CONSTRUCT`. `OBJECT_CONSTRUCT` omits keys with NULL values, so empty strings become absent
   keys downstream. Python plugin, OtelManager, and Grail never see the empty string.

2. **`snowflake.task.is_internal` flag**: `IFF(task_name LIKE '%\_MEASUREMENT\_TASK' ESCAPE '\' OR
   task_name LIKE '%\_FINALIZER\_TASK' ESCAPE '\', true, false)`. The `ESCAPE` clause is required
   because `_` is a single-character wildcard in Snowflake LIKE patterns without an escape. Without it,
   `%_MEASUREMENT_TASK` would match any task ending in any character followed by `MEASUREMENT_TASK`,
   giving false positives. Pattern covers all plugin-specific variants
   (e.g. `TASKS_MEASUREMENT_TASK`, `DYNAMIC_TABLES_MEASUREMENT_TASK`).

3. **`_MESSAGE` fallback**: `COALESCE(NULLIF(database_name, ''), task_name)` replaces bare
   `database_name` concatenation. Internal tasks now log `"New Serverless Tasks entry for
   TASKS_MEASUREMENT_TASK"` instead of `"New Serverless Tasks entry for "`.

### instruments-def.yml

Added `snowflake.task.is_internal` under `dimensions:`. Example value: `false`. Context: `serverless_tasks`.

### Testing

Mock fixture `tasks_serverless.ndjson` updated: row 1 = user task (db.namespace populated, is_internal=false),
row 2 = internal task (db.namespace/snowflake.schema.name absent, is_internal=true). Stored test results
regenerated. `make lint` (sqlfluff, pylint 10.00/10) passes. No Python plugin changes required.

### Edge case noted

A customer could name their own task ending in `_MEASUREMENT_TASK` and get a false-positive `is_internal = true`.
Acceptable risk — extremely unlikely naming collision. Can be tightened to a DTAGENT-specific prefix in a
future release if needed.

---

## [Unreleased] — Snowflake Consumption Dashboard Phase B

### Dashboard Phase B: §1 Contract Capacity KPIs + §3 USD Consumption + Workflow Fix

**Scope**: Phase B of the org-level consumption dashboard. Appends tiles `"14"`–`"24"` to the
existing dashboard (UUID `6881ff48-0945-4e94-94af-2e4bb338724e`). Bumps version to 3.

**§1 Contract Capacity KPIs** (tiles 14–20, inserted at top via layout y=0..12):

- **Capacity Used (USD)** (tile 15, singleValue): `sum(snowflake.org.billing.amount)` over the
  selected timeframe. Uses `arraySum` to correctly total daily billing rows.
- **Remaining Capacity (USD)** (tile 16, singleValue): `last(capacity_balance) + last(rollover_balance)`.
  Uses `avg()` on both metrics (one row per org per day) then takes the last array value.
- **30-Day Run Rate (USD)** (tile 17, singleValue): `sum(billing.amount)` with explicit `from: now()-30d`
  to pin the window regardless of the dashboard timeframe selector.
- **YoY Burn Rate** (tile 18, table): Two `timeseries` pipes (current 30d and previous 30d) combined
  via `append` + `summarize` to produce `current_usd`, `previous_usd`, annualized run rates, and
  `pct_change`. DQL `join` across time windows is not supported, so `append` + aggregate is used.
- **Estimated Days to Overage** (tile 19, singleValue): Derived from 30-day balance burn:
  `balance_end / monthly_burn * 30`. Returns `-1` when burn rate is zero or negative (balance growing).
- **Projected Overage Date** (tile 20, table): Computes `days_to_overage` then formats as a timestamp
  string using `formatTimestamp(now() + toTimespan(...))`. Returns "No overage projected" when
  days_to_overage ≤ 0.

**§3 USD Consumption** (tiles 21–24, inserted after §2 at y=26..39):

- Markdown header tile (21) includes the credit-rate fallback note inline.
- Line chart (22): `billing.amount` by account over time.
- Bar chart (23): `billing.amount` summarized by service type.
- Table (24): total USD per account using `arraySum` (not `arrayAvg`) because billing rows are
  daily totals that should be summed, not averaged.

**Workflow fix** (`docs/workflows/org-contract-balance-warning/org-contract-balance-warning.yml`):
Replaced five non-existent `snowflake.org.balance.*.remaining` metric IDs with the real keys:
`snowflake.org.billing.free_usage_balance`, `capacity_balance`, `on_demand_consumption`,
`rollover_balance`, `overage`. Updated `metricsClient.query` selector from `:last` to `:avg:last`
to match the `avg()` aggregation used in the dashboard (one row per org per day).

**Layout strategy**: New §1 tiles use keys `"14"`–`"20"` at y=0..12. Existing §2 tiles (`"0"`–`"3"`)
shift to y=13..25. New §3 tiles use keys `"21"`–`"24"` at y=26..39. Existing §4–§6 tiles shift
accordingly. No tile keys were renumbered — only layout `y` coordinates changed.

---

## [Unreleased] — Snowflake Consumption Dashboard Phase C

### Dashboard: §7 Department / BU View

**Scope**: Phase C of the org-level consumption dashboard. Appends §7 Department / BU View
(tiles "25"–"29") to `docs/dashboards/org-costs-observability/org-costs-observability.yml`.
Coordinates with Phase B (tiles "14"–"24") which landed concurrently.

**Changes**:

- **§7 Department / BU View** (5 tiles):
  - Markdown header with inline usage note for `$bu_mapping` variable.
  - Bar chart: credits by account (`snowflake.org.credits.used`, summarized, `bu = "Unassigned"`).
  - Bar chart: USD billing by account (`snowflake.org.billing.amount`, `arraySum`, `bu = "Unassigned"`).
  - Bar chart: storage by account (`snowflake.org.storage.bytes`, avg, bytes `unitsOverrides`, `bu = "Unassigned"`).
  - Table: account-to-BU mapping view (account + bu columns, sorted by account).
- **Layout**: tiles placed at y=67–81 (after §6 Billing at y=60–67). Three bar charts side-by-side
  (8 cols each), table full-width below.
- **`readme.md`** updated: §7 tile inventory table added; BU Mapping Configuration section added
  with JSON format, example, and v1 limitation note.

**v1 BU mapping design decision**:

DQL does not support dynamic JSON key-indexing against a variable string at query time. The
`$bu_mapping` variable holds a JSON object `{"ACCOUNT": "BU"}`, but there is no native DQL
operator to look up a field value as a key in that JSON at runtime. Options considered:

1. **Hardcoded `if/matchesRegex` chain** — requires dashboard edits per customer; not scalable.
2. **Grail lookup tables** — not yet available in DSOA's target tenant tier; planned for a
   future release.
3. **`fieldsAdd bu = "Unassigned"` (chosen for v1)** — all accounts show as "Unassigned" by
   default. Customers who need BU grouping can use the `$bu_mapping` variable as documentation
   of intent and wait for the lookup-table enhancement, or apply OpenPipeline enrichment rules
   externally to add a `bu` attribute to the metric data.

The `$bu_mapping` variable is retained in the dashboard as a placeholder and configuration
anchor. Pattern-based mapping (SQL LIKE / regex) is tracked as a future enhancement.

---

## [Unreleased] — Snowflake Consumption Dashboard Phase A

### Dashboard Overhaul: Snowflake Consumption (Organization Level)

**Scope**: Phase A of the org-level consumption dashboard. Extends `docs/dashboards/org-costs-observability/`
in place (preserves deployed UUID `6881ff48-0945-4e94-94af-2e4bb338724e`). Bumps version to 2.

**Changes**:

- **Title** updated from `Org-Level Costs Observability` to `Snowflake Consumption (Organization Level)`.
- **Variables** replaced: `$Accounts` (query, multi-select, uses `fetch logs` with `dsoa.run.plugin == "org_costs"`
  to avoid empty-variable risk); `$credit_rate` (hidden text, default `"3.00"`, reserved for Phase B);
  `$bu_mapping` (hidden text, default `"{}"`, reserved for Phase C BU grouping).
- **§2 Credit Consumption** (3 tiles): line chart of credits over time by account; bar chart of credits
  by service type; table of compute + cloud_services + total credits by account.
- **§4 Storage** (3 tiles): line chart of storage bytes over time by account; bar chart by storage type;
  table of total bytes by account. All byte fields have `unitsOverrides` with `unitCategory: data`.
- **§5 Data Transfer** (2 tiles): line chart of transfer bytes over time; table by source/target cloud
  and region. Byte fields have `unitsOverrides`.
- **§6 Billing & Contract Balance** (2 tiles): billing amount line chart; Remaining Contract Balance
  tile **fixed** — old query used non-existent `snowflake.org.balance.*.remaining` metric keys.
  New query uses real keys: `snowflake.org.billing.capacity_balance`, `rollover_balance`,
  `free_usage_balance`, `on_demand_consumption`, `overage`. Uses `avg()` (not `sum()`) because
  `REMAINING_BALANCE_DAILY` emits one row per org per day.
- **`instruments-def.yml`** updated: added `snowflake.storage.type` as a declared dimension for
  `org_costs_storage` context (was emitted by the SQL view but not declared in the semantic dictionary).
- **`readme.md`** updated: new title, 3-variable table, full Phase-A tile inventory, Phase B/C roadmap notes.
- **`docs/dashboards/README.md`** updated: entry renamed and description expanded.

**Metric-name bug root cause**: The original dashboard was authored before the `org_billing_remaining_balance`
context was finalized. The metric keys `snowflake.org.balance.*.remaining` were placeholder names that
never matched the emitted keys. The correct keys are in `instruments-def.yml` under `org_billing_remaining_balance`.

**Phase plan**:

- Phase A (this change): §2 Credits, §4 Storage, §5 Data Transfer, §6 Billing/Balance fix.
- Phase B (future): §1 Contract Capacity KPIs (single-value tiles for capacity used, remaining, burn rate,
  days to overage, overage date) and §3 USD Consumption. Requires billing context data.
- Phase C (future): §6 Department/BU View using `$bu_mapping` JSON variable for account-to-BU grouping.

---

## [Unreleased] — org_costs Plugin: Organization-Level Costs and Usage

### org_costs Plugin — Full Implementation

**Scope**: New `org_costs` plugin collecting organization-level cost and usage metrics from
`SNOWFLAKE.ORGANIZATION_USAGE`. Five contexts, disabled by default, 6-hour cron schedule.

**Architecture**:

- **`src/dtagent/plugins/org_costs.py`**: Multi-context plugin following the `warehouse_usage`
  pattern. Registers five contexts via `process()` dispatching to private per-context methods.
- **Five views** (`051`–`055`):
  - `V_ORG_METERING_DAILY` — credit consumption by service type and service name
  - `V_ORG_STORAGE_DAILY` — storage bytes by storage type and account locator
  - `V_ORG_DATA_TRANSFER_DAILY` — data transfer bytes by cloud, region, and transfer type
  - `V_ORG_BILLING_USAGE_IN_CURRENCY` — billed amounts in contract currency by account and service
  - `V_ORG_BILLING_REMAINING_BALANCE` — five balance categories (free usage, capacity, on-demand,
    rollover, total)
- **Metrics** (10 total): `snowflake.org.credits.used`, `snowflake.org.credits.cloud_services`,
  `snowflake.org.storage.bytes`, `snowflake.org.transfer.bytes`, `snowflake.org.billing.amount`,
  and five `snowflake.org.balance.*.remaining` metrics.
- **Admin proc** (`admin/050_p_check_organization_usage_access.sql`): Diagnostic stored procedure
  `DTAGENT_DB.APP.P_CHECK_ORGANIZATION_USAGE_ACCESS()` that can be called manually after
  deployment to verify ORGANIZATION_USAGE access. Returns a success or failure message.
- **Deploy advisory** (`scripts/deploy/lib.sh::check_org_costs_access()`): Non-blocking warning
  emitted during `prepare_deploy_script.sh` when `org_costs` is in scope and not excluded. Reminds
  operators to verify ORGADMIN access before enabling the plugin.

**Test coverage**: Five tests in `test/plugins/test_org_costs.py` using mock NDJSON fixtures.
Each test exercises multiple `disabled_telemetry` combos and validates metric counts against
golden files in `test/test_results/`.

**Dashboards**:

- New **`Org-Level Costs Observability`** dashboard (`docs/dashboards/org-costs-observability/`):
  9 tiles covering all five metric groups. UUID `6881ff48-0945-4e94-94af-2e4bb338724e`.
- Extended **`Costs Monitoring`** dashboard with org-level credits overview section (tiles 22/23,
  version bumped to 21).

**Workflow**: New **`Org Contract Balance Warning`** (`docs/workflows/org-contract-balance-warning/`):
6-hour schedule, queries five `snowflake.org.billing.*` metrics (`capacity_balance`,
`rollover_balance`, `free_usage_balance`, `on_demand_consumption`, `overage`) and logs alert if any
drops below configurable threshold.

**Doc updates**: `docs/USECASES.md` extended with "Costs — Tier 0 — Organization-Level FinOps"
section (3 new use cases). `docs/dashboards/README.md` and `docs/workflows/README.md` updated.

---

## [Unreleased] — BDX-1969: Interactive Deployment Wizard

## [Unreleased]: Acquisition Problem Detection

### Motivation

`_get_table_rows()` in `plugins/__init__.py` and `_get_sub_rows()` in `otel/spans.py` called `session.sql()` / `session.table()` with no exception handling. A `SnowparkSQLException` (e.g. view missing, permission error, network timeout) would propagate up to `agent.py` where only `RuntimeError` was caught — `SnowparkSQLException` is not a `RuntimeError`, so it would crash the entire agent run, silencing all subsequent plugins for that execution.

### Implementation

**New class — `AcquisitionProblemCollector` in `src/dtagent/otel/ingest_warnings.py`**

Added alongside `IngestWarningCollector` in the same module. Thread-safe static-method collector, same pattern. Problem dict schema: `problem_type`, `source`, `detail`, `count`.

**`_get_table_rows` — `src/dtagent/plugins/__init__.py`**

Wrapped entire SQL execution + row iteration in `try/except SnowparkSQLException`. On exception: logs `ERROR`, calls `AcquisitionProblemCollector.add_problem("sql_error", ...)`, yields nothing (graceful degradation — plugin reports 0 entries).

**`_get_sub_rows` — `src/dtagent/otel/spans.py`**

Same pattern for sub-row queries. On `SnowparkSQLException`: logs `ERROR`, calls `AcquisitionProblemCollector.add_problem("sub_row_error", ...)`, yields nothing. Uses inline `from dtagent import LOG  # COMPILE_REMOVE` (consistent with `metrics.py` pattern).

**Bizevent emission — `src/dtagent/__init__.py` + `src/dtagent/agent.py`**

`AbstractDynatraceSnowAgentConnector._emit_acquisition_problems()` follows the same structure as `_emit_ingest_warnings()`. Called on both success and error paths in the agent loop (before `handle_interrupted_run`). Always calls `AcquisitionProblemCollector.reset()` in `finally`.

**Compile assembly — `src/dtagent/agent.py` + `src/dtagent/connector.py`**

Added `from snowflake.snowpark.functions import col` and `from snowflake.snowpark.exceptions import SnowparkSQLException` to `GENERAL_IMPORTS` in both entry-point files (these were previously inline `# COMPILE_REMOVE` imports that didn't survive compilation).

**Config — `conf/config-template.yml`**

Added `plugins.self_monitoring.detect_acquisition_problems: true` (default on).

**Dashboard — `docs/dashboards/self-monitoring/self-monitoring.yml`**

Added tiles 17 and 18 (row at `y=37`):

- Tile 17: `Acquisition problems over time` — `makeTimeseries` line chart by problem type (7-day window).
- Tile 18: `Acquisition problem details` — table of recent problems sorted by timestamp desc.

**Tests — `test/otel/test_acquisition_problems.py`** (12 tests, new file)

- `TestAcquisitionProblemCollector`: 7 unit tests mirroring the ingest warning collector suite.
- `TestGetTableRowsSqlErrors`: 3 tests — clean query, exception at setup, exception during iteration.
- `TestGetSubRowsSqlErrors`: 2 tests — clean sub-row fetch, exception during fetch.

### Behavioral Change

Before: `SnowparkSQLException` propagated uncaught → crashed entire agent run → all subsequent plugins silenced.
After: Exception caught at the view-access level → plugin produces 0 entries + bizevent → agent continues to next plugin.

### Performance

No measurable overhead on the happy path — exception handling is zero-cost when no exception occurs.

## [Unreleased] — BDX-695: Ingest-Quality Warning Detection

### Motivation

DSOA sends telemetry to Dynatrace over OTLP and REST APIs, but all three export paths (OTLP logs/spans, Metrics API v2, Events/BizEvents API) previously discarded HTTP response bodies on success. This meant partial rejections (`partialSuccess.rejectedLogRecords`, `linesInvalid`, `non_persisted_attribute_keys`, `rejectedEventIngestInputCount`) were silently swallowed — operators had no visibility until they noticed missing data in dashboards, often days later.

### Implementation

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

### Performance

Response body parsing runs only on successful responses (2xx). `json.loads()` on a typical <1 KB response body adds <0.1 ms. Warning bizevent emission happens at most once per plugin run when warnings are present — negligible overhead.

### Backward Compatibility

- Config default is `true` — existing deployments get detection automatically.
- No schema changes to existing telemetry.
- No SQL changes — no upgrade scripts needed.
- No procedure signature changes.

## [Unreleased] — Resource Monitor Credit Threshold Alerting

### Resource Monitor Credit Threshold Alerting — Full Implementation

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

### Interactive Deployment Wizard — Full Implementation

**Scope**: Story to eliminate manual config creation friction for first-time DSOA users. Deliverables: shared bash library, 4-phase interactive wizard, `deploy.sh` flag enhancements, full BATS test suite.

**Architecture**:

- **`scripts/deploy/lib.sh`** (487 lines): Shared bash library sourced by wizard and deploy.sh. Includes:
  - **Logging helpers**: `log_info`, `log_ok`, `log_warn`, `log_error` (consolidates duplicated code from `deploy_dt_assets.sh` + `deploy_test_notebook.sh` for future refactoring).
  - **Prompt helpers**: `prompt_input()` (collects input with optional default + validation fn), `prompt_yesno()` (y/n), `prompt_select_one()` (bash `select` menu), `prompt_select_multi()` (y/n per item).
  - **Validators**: `validate_dt_tenant()` (accepts `*.live.dynatrace.com`, `*.sprint.dynatracelabs.com`, `*.dev.dynatracelabs.com`; auto-corrects `.apps.dynatrace.com` → `.live.dynatrace.com`), `validate_sf_account()` (format + optional HTTPS probe to `<account>.snowflakecomputing.com`), `validate_nonempty()`, `validate_alphanumeric()`.
  - **Probes**: `probe_dt_tenant()` + `probe_sf_account()` (HTTPS reachability checks; warn-don't-block on failure per story).
  - **Config helpers**: `read_config_key()` / `write_config_key()` (wraps `yq`).
  - All functions include Google-style docstrings for maintainability.

- **`scripts/deploy/interactive_wizard.sh`** (988 lines): Standalone wizard script. Five phases:
  1. **Phase 1 — Core Config**: Prompts for DT tenant, API token (silent `read -rs`), SF account, deployment env name, optional multitenancy tag. Auto-corrects `.apps.` to `.live.`. Pre-populates from existing config if in edit mode (`--existing-config=`).
  2. **Phase 2 — Deployment Scope**: `prompt_select_one()` menu with 9 options (full/init/init+admin/post-init/config-only/apikey/upgrade/teardown/dt_assets). If upgrade selected, prompts for `--from-version`.
  3. **Phase 3 — Plugin Selection**: Q1: All/None/Selected (shown as numbered list, user selects via bash `select` y/n per plugin). Q2: Deploy disabled plugin code? Sets `plugins.deploy_disabled_plugins`. Q3: Customize plugin settings? Walks through per-plugin knobs (schedule, thresholds) for each enabled plugin.
  4. **Phase 4 — Advanced Settings**: Optional (behind `prompt_yesno` gate). Log level, procedure timeout, resource monitor quota.
  5. **Phase 5 — Telemetry Settings**: Optional. OTel enable/disable per signal type, max consecutive API fails.
  - **Config persistence**: Generates YAML via heredoc + append. Offers: ① save new `conf/config-$ENV.yml`, ② overwrite existing config, ③ print to stdout, ④ discard. `--output=<file>` skips menu and writes directly. `--dry-run` prints to stdout without writing any file.
  - **Flags**: `--env=`, `--existing-config=`, `--dry-run`, `--output=`. Works with piped stdin for testing.

- **Modified `scripts/deploy/deploy.sh`**:
  - **New args**: `--env=<ENV>` (flag-based, replaces positional), `--interactive` (launch wizard), `--defaults` (generate minimal config non-interactively from `config-template.yml`).
  - **Backward compat**: Positional `$ENV` still works; emits deprecation warning suggesting `--env=`.
  - **Auto-trigger wizard**: When `conf/config-$ENV.yml` missing and `--defaults` not set, automatically invokes wizard.
  - **Validation**: Wizard's probes check DT tenant and SF account reachability; optional API token validation via metadata endpoint (all warnings, no hard blocks).

**Testing**:

- **`test/bash/test_lib.bats`** (156 lines, 19 tests): Unit tests for lib.sh validators, prompt helpers, config key accessors. Source lib.sh directly, test functions in isolation.
- **`test/bash/test_interactive_wizard.bats`**: Integration tests. Pipe stdin answers into wizard; validate generated YAML. Covers all phases, config persistence options, `--output=` and `--dry-run` flags.
- **`test/bash/test_deploy_new_flags.bats`**: Test deploy.sh flag behavior (`--env=`, `--interactive`, `--defaults`, positional deprecation). Includes integration test for `deploy.sh --interactive` with piped stdin (EOF) to verify wizard invocation path.

**Design decisions**:

1. **No external TUI frameworks** (no fzf/gum/whiptail/dialog) — bash `select` is sufficient for plugin checklist.
2. **HTTPS probes warn, don't block** — per story spec; users can proceed even if network unreachable.
3. **Auto-correct `.apps.` to `.live.`** — common user mistake; silently fixed improves UX.
4. **Bash `select` for multi-select** — simplest pure-bash solution; each item is y/n via separate `select` invocation (follows user's design choice).
5. **Config persistence via heredoc + append** — generates YAML with a heredoc for the core block, then appends optional sections. Overwrites the target file on save; does not merge/preserve comments from existing configs.
6. **Piped stdin testing** — wizard accepts EOF gracefully; tests pipe answers + validate output, no interactive mocking needed.

**Files changed**:

- `scripts/deploy/lib.sh` (new, 487 lines)
- `scripts/deploy/interactive_wizard.sh` (new, 568 lines)
- `scripts/deploy/deploy.sh` (modified, +119 lines)
- `test/bash/test_lib.bats` (new, 156 lines)
- `test/bash/test_interactive_wizard.bats` (new, 101 lines)
- `test/bash/test_deploy_new_flags.bats` (new, 160 lines)
- `docs/CHANGELOG.md` (updated, user-facing summary)
- `docs/DEVLOG.md` (this file, technical details)

**Acceptance criteria met**:

- ✓ `./deploy.sh --env=test-qa --interactive` launches wizard
- ✓ `./deploy.sh --env=test-qa --defaults` generates config non-interactively
- ✓ `./deploy.sh test-qa --scope=...` (positional) works with deprecation warning
- ✓ Wizard generates valid YAML passing `prepare_config.sh` validation
- ✓ All BATS tests pass (32/32)
- ✓ `make lint` passes (pylint 10.00/10, shellcheck, markdownlint)
- ✓ No new runtime dependencies (bash builtins + jq/yq/curl/snow CLI only)
- ✓ Full backward compatibility (existing deploy.sh flows unchanged)

**Future work**:

- Extract log helpers from `deploy_dt_assets.sh` and `deploy_test_notebook.sh` to source lib.sh (scope creep, separate PR).
- GitHub Actions workflow generation as optional wizard output.
- SQL `USE` statement deduplication in `prepare_deploy_script.sh` (post-MVP optimization, noted in story).

## Version 0.9.5 — Detailed Changes

### Feature: Cross-Batch Span Parent Linking for query_history Plugin

- **Problem**: When a Snowflake stored procedure call chain spans multiple agent run cycles (e.g., a parent SP is processed in batch N and its child queries appear in batch N+1), the child spans had no parent context. Each batch started a fresh trace, breaking trace continuity across batches.
- **Solution**: Persist OTEL span context in `PROCESSED_QUERIES_CACHE` after each batch and inject it as parent context for child queries in subsequent batches.
- **Precedence Rule**: `event_log _SPAN_ID/_TRACE_ID` (Snowflake-native tracing) > cached parent OTEL context > fresh random IDs. This ensures Snowflake-native trace propagation always wins.
- **Schema Changes**:
  - `011_processed_queries_cache.sql`: Added `OTEL_SPAN_ID TEXT` and `OTEL_TRACE_ID TEXT` nullable columns to `PROCESSED_QUERIES_CACHE`.
  - `110_update_processed_queries.sql`: Added 4th parameter `span_context_json TEXT DEFAULT '{}'`. After inserting processed queries, updates `OTEL_SPAN_ID`/`OTEL_TRACE_ID` using `FLATTEN(PARSE_JSON(:span_context_json))`. Cache TTL now driven by `plugins.query_history.cache_ttl_hours` config (default: 4h, was hardcoded).
- **SQL Changes**:
  - `061_p_refresh_recent_queries.sql`: Added `_PARENT_OTEL_SPAN_ID` and `_PARENT_OTEL_TRACE_ID` columns to `TMP_RECENT_QUERIES`. Replaced single IS_ROOT update with 3-step logic: (1) IS_ROOT=TRUE where PARENT_QUERY_ID IS NULL, (2) IS_ROOT=TRUE where parent not in current batch AND not in cache with OTEL context, (3) UPDATE `_PARENT_OTEL_SPAN_ID`/`_PARENT_OTEL_TRACE_ID` from cache where parent IS in cache.
  - `062_v_recent_queries.sql`: Added `_PARENT_OTEL_SPAN_ID` and `_PARENT_OTEL_TRACE_ID` to SELECT.
- **Python Changes**:
  - `otel/spans.py`: Added `span_context_map: Optional[Dict[str, Tuple[str, str]]] = None` parameter to `generate_span()`. After span creation, captures `(span_id_hex, trace_id_hex)` into the map. Before span creation, injects cached parent context via `context_api.attach()` when `_PARENT_OTEL_SPAN_ID`/`_PARENT_OTEL_TRACE_ID` are present and no event_log IDs exist. Token is detached after span ends.
  - `plugins/__init__.py`: Creates `span_context_map` dict in `_process_span_rows()`, threads it through `_process_row()` → `generate_span()`. After processing, serializes as JSON `{qid: {"trace_id": t, "span_id": s}}` and passes as 4th arg to `STATUS.UPDATE_PROCESSED_QUERIES`.
- **Upgrade Scripts**:
  - `0.9.5/020_add_span_context_to_cache.sql`: ALTER TABLE to ADD COLUMN IF NOT EXISTS for both OTEL columns.
  - `0.9.5/021_drop_update_processed_queries_3arg.sql`: DROP PROCEDURE IF EXISTS for old 3-arg signature before deploying new 4-arg version (avoids Snowflake ambiguous overload error).
- **Config**:
  - Added `query_history.cache_ttl_hours` (default: 4) to `config-template.yml` and `query_history-config.yml`.
- **Testing**:
  - `test/plugins/test_query_history_cross_batch.py`: New test file with 3 tests: integration test for cross-batch span injection (all disabled_telemetry combos), unit test for precedence rule validation, unit test for `span_context_map` population.
  - `test/test_data/query_history_cross_batch.ndjson`: New fixture with 3 rows covering: child with cached parent context, child without context (fresh IDs), child with both event_log IDs and cached parent (event_log wins).
- **Files Changed**: `src/dtagent/plugins/query_history.sql/011_processed_queries_cache.sql`, `src/dtagent/plugins/query_history.sql/061_p_refresh_recent_queries.sql`, `src/dtagent/plugins/query_history.sql/062_v_recent_queries.sql`, `src/dtagent/plugins/query_history.sql/110_update_processed_queries.sql`, `src/dtagent/otel/spans.py`, `src/dtagent/plugins/__init__.py`, `src/dtagent.sql/upgrade/0.9.5/020_add_span_context_to_cache.sql`, `src/dtagent.sql/upgrade/0.9.5/021_drop_update_processed_queries_3arg.sql`, `src/dtagent/plugins/query_history.config/query_history-config.yml`, `conf/config-template.yml`, `test/plugins/test_query_history_cross_batch.py`, `test/test_data/query_history_cross_batch.ndjson`

### New Plugin: Table Health

- **Purpose**: Monitor table storage metrics (active bytes, time-travel bytes, failsafe bytes, retained-for-clone bytes, row count) to identify tables with excessive storage overhead and optimize retention policies.
- **Data source**: `SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS` joined with `SNOWFLAKE.ACCOUNT_USAGE.TABLES` for row count and clustering key.
- **Metrics**: Five gauges (`snowflake.table.active_bytes`, `snowflake.table.time_travel_bytes`, `snowflake.table.failsafe_bytes`, `snowflake.table.retained_for_clone_bytes`, `snowflake.data.rows`).
- **Configuration**: Include/exclude filtering (default: `DTAGENT_DB.%.%` and `%.PUBLIC.%`), `min_table_bytes` (default 1GB), `max_tables` (default 500).
- **Schedule**: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC).
- **Status**: Disabled by default (opt-in plugin).
- **Files**: `src/dtagent/plugins/table_health.py`, `src/dtagent/plugins/table_health.sql/`, `src/dtagent/plugins/table_health.config/`, `test/plugins/test_table_health.py`.
- **Test coverage**: Mock fixture with 2 entries, validates metric counts across disabled_telemetry combinations.

#### Phase 2: Clustering Depth Context

- **Purpose**: Report clustering quality metrics for tables with a clustering key, enabling detection of degraded clustering that increases query scan costs.
- **Architecture**: Staging-table pattern — `P_COLLECT_CLUSTERING_INFO()` iterates clustered tables from `SNOWFLAKE.ACCOUNT_USAGE.TABLES`, calls `SYSTEM$CLUSTERING_INFORMATION(table_name)` per table, and upserts results into `APP.TABLE_CLUSTERING_RESULTS`. The view `APP.V_TABLE_CLUSTERING` reads from the staging table with a 7-hour freshness gate. The agent then reads from the view in the `table_clustering` context.
- **Why staging table**: `SYSTEM$CLUSTERING_INFORMATION()` is a per-table function, not a view — it cannot be called in a set-based query. The procedure loop + staging table pattern decouples collection from telemetry emission.
- **Error handling**: Each per-table call is wrapped in `BEGIN … EXCEPTION WHEN statement_error` so that tables dropped since the last `ACCOUNT_USAGE` refresh are skipped with a `SYSTEM$LOG_WARN` entry rather than aborting the whole collection run.
- **Freshness gate**: `V_TABLE_CLUSTERING` only returns rows where `COLLECTED_AT >= DATEADD(hour, -7, current_timestamp)`. This prevents stale data from being re-emitted if the clustering task is delayed or skipped.
- **Metrics**: Four gauges — `snowflake.table.clustering.depth`, `snowflake.table.clustering.overlap`, `snowflake.table.clustering.constant_partition_ratio` (computed as `TOTAL_CONSTANT_PARTITION_COUNT / NULLIF(TOTAL_PARTITION_COUNT, 0)`), `snowflake.table.clustering.total_partitions`.
- **Schedule**: `TASK_DTAGENT_TABLE_HEALTH_CLUSTERING` runs every 6 hours at 01:00, 07:00, 13:00, 19:00 UTC — offset by 1 hour from the storage task to avoid warehouse contention.
- **Config gate**: `clustering_enabled: true` (default). Set to `false` to skip the `table_clustering` context entirely without disabling the plugin.
- **New config key**: `max_clustered_tables: 100` — limits the number of tables processed per collection run.
- **New SQL objects**: `052_t_table_clustering_results.sql`, `053_p_collect_clustering_info.sql`, `054_v_table_clustering.sql`, `802_table_health_clustering_task.sql`.
- **Test coverage**: 4 tests — both contexts, storage-only, clustering-only, clustering disabled via config.

#### Phase 3: Derived Metrics Context

- **Purpose**: Compute period-over-period growth and clustering degradation signals from historical snapshots, enabling alerting on tables that are growing rapidly or whose clustering is degrading.
- **Architecture**: Three new objects — `TABLE_HEALTH_HISTORY` (append-only snapshot table), `P_SNAPSHOT_TABLE_HEALTH()` (inserts one row per table per run by joining `V_TABLE_STORAGE` with `TABLE_CLUSTERING_RESULTS`, then prunes rows older than `history_retention_days`), and `V_TABLE_HEALTH_DERIVED` (CTE-based view using `ROW_NUMBER()` to select the two most recent snapshots per table and compute deltas).
- **Opt-in design**: `history_retention_days: 0` (default) disables both snapshot collection and the `table_health_derived` context. Set to a positive integer (e.g. `30`) to enable. The Python plugin gates the context on `history_retention_days > 0`.
- **Metrics**: Four gauges — `snowflake.table.growth_bytes` (byte delta), `snowflake.table.growth_pct` (percentage delta, null-safe), `snowflake.table.clustering.depth_change` (depth delta), `snowflake.table.clustering.degraded` (0/1 flag when depth increase exceeds `clustering_degradation_threshold`).
- **Degradation threshold**: `clustering_degradation_threshold: 2` (default). Configurable per deployment.
- **Schedule**: `TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT` runs every 6 hours at 02:00, 08:00, 14:00, 20:00 UTC — offset by 2 hours from the storage task (after clustering collection at +1h has completed).
- **New SQL objects**: `055_t_table_health_history.sql`, `056_p_snapshot_table_health.sql`, `057_v_table_health_derived.sql`, `803_table_health_snapshot_task.sql`.
- **New config keys**: `history_retention_days: 0`, `clustering_degradation_threshold: 2`, `schedule_snapshot`.
- **Test coverage**: 6 tests total — both contexts, derived context enabled, derived context disabled by default, storage-only, clustering-only, clustering disabled via config.

### Dashboard: Warehouse Efficiency Section in Costs Monitoring

- **Purpose**: Surface idle-time waste and auto-suspend misconfiguration in the existing Costs Monitoring dashboard.
  Customers waste 20–40% of warehouse spend on idle time and suboptimal auto-suspend timeouts; these tiles make
  that waste visible and actionable without requiring any agent code changes.
- **Approach**: Dashboard-only change. Eight new tiles (keys `"22"`–`"29"`) appended after the existing Resource
  Monitor Health section. One new variable `$Idle_Threshold_Pct` (text, default `"50"`) added for threshold coloring.
  Dashboard version bumped from 20 to 21.
- **Data sources** (all pre-existing telemetry):
  - `snowflake.load.running` metric (warehouse\_usage plugin, `warehouse_usage_load` context) — 5-minute load
    history intervals. `avg ≤ 0` used as idle indicator.
  - `snowflake.warehouse.clusters.started/max/min` metrics (resource\_monitors plugin) — multi-cluster utilization.
  - `snowflake.warehouse.is_auto_suspend`, `snowflake.warehouse.size`, `snowflake.warehouse.type`,
    `snowflake.warehouse.scaling_policy` attributes (resource\_monitors plugin) — configuration audit.
  - `snowflake.warehouse.event.name` / `snowflake.warehouse.event.state` dimensions (warehouse\_usage plugin) —
    RESUME\_WAREHOUSE / SUSPEND\_WAREHOUSE events for thrashing detection.
- **DQL patterns**:
  - Idle ratio (tiles 23, 26): `timeseries` over `snowflake.load.running` at 5m interval → `arrayFilter(running[], {it <= 0.0})` to count idle intervals → `idle_pct = 100 * idle_intervals / total_intervals`.
  - Credit waste (tile 26): `idle_hours = idle_intervals * 5 / 60` joined with inline `lookup` table for credits/hour by warehouse size (XS=1, S=2, M=4, L=8, XL=16, 2XL=32, 3XL=64, 4XL=128). Same lookup pattern as tile `"14"`.
  - Suggested timeout heuristic: `idle_pct > 50% → "60s"`, `> 20% → "300s"`, else `"Keep current"`. 60 s is the Snowflake minimum billing floor.
  - Multi-cluster (tiles 27, 28): `fetch events` from resource\_monitors plugin filtered to `clusters.max > 1`; `makeTimeseries` for trend, `summarize` for table.
  - Thrashing (tile 29): `fetch logs` from warehouse\_usage plugin, filter `event.state == "STARTED"` to count only initiating events (not completions), `makeTimeseries count()` by event name + warehouse.
  - All tiles use `dsoa.run.plugin` (not `dsoa.run.context`) for plugin-level filtering, consistent with multi-context plugins.
  - Serverless warehouses excluded via `filterOut snowflake.warehouse.type == "SNOWPARK-OPTIMIZED"` in tiles 25 and 26.
- **Variable filters**: All new tiles apply the standard three-filter pattern: `in(deployment.environment, array($Accounts))` + `iAny(startsWith(..., concat(array($Prefix)[], "_")))` + `in(snowflake.warehouse.name, array($Warehouses))`.
- **Layout**: New section occupies y=78–107 (rows 78–107). Tiles 23/24 share a row (idle table + trend chart). Tiles 27/28 share a row (multi-cluster trend + idle clusters table).
- **Known limitations**:
  - `snowflake.load.running = 0` means no active queries but the warehouse may still be in a provisioning or quiescing state; idle estimate is conservative (may slightly overcount).
  - Credit waste estimates assume uniform 5-minute billing intervals; actual billing uses 60-second minimum floor.
  - `$Idle_Threshold_Pct` threshold in tile 23 uses a string variable in a numeric comparator — verify rendering on tenant (DQL may require `toDouble($Idle_Threshold_Pct)`).
- **Files changed**: `docs/dashboards/costs-monitoring/costs-monitoring.yml`, `docs/dashboards/costs-monitoring/readme.md`, `docs/CHANGELOG.md`, `docs/DEVLOG.md`.

### Performance and Memory Handling Improvements

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

### Feature: Signal Protection Framework for query_history Plugin

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

### New Plugin: Cold Tables Identification

- **Purpose**: Identify tables with no recent query access (default: >90 days) to enable FinOps teams to find candidates for archiving, dropping, or tiering to lower-cost storage.
- **Data source**: `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` aggregated per table over configurable lookback window (default: 365 days).
- **Pattern**: Pattern 1 plugin (simple log + metric, single context, single schedule). Closest analog: `data_volume`.
- **Schedule**: Daily at 6 AM UTC (access patterns don't change hourly; ACCESS_HISTORY has ~2h latency).
- **SQL design**:
  - View `V_COLD_TABLES` aggregates `BASE_OBJECTS_ACCESSED` per table using LATERAL FLATTEN.
  - Watermark via `GREATEST(lookback, F_LAST_PROCESSED_TS('cold_tables'))` — standard incremental pattern.
  - Config-driven thresholds: `lookback_days` (365) and `cold_threshold_days` (90) read via `F_GET_CONFIG_VALUE` — no SQL redeploy needed to change.
  - BCR-2275 compliant: explicit column list from ACCESS_HISTORY (only `QUERY_START_TIME` and `BASE_OBJECTS_ACCESSED`).
  - `cold_status` as DIMENSION (not attribute) — enables metric filtering by cold/warm in Dynatrace.
- **Metrics**: `snowflake.table.access.count` (total accesses), `snowflake.table.days_since_last_access` (gauge).
- **Logs**: Per-table detail with cold status flag.
- **Known limitation**: Tables never accessed won't appear (ACCESS_HISTORY only has accessed tables). Follow-up: JOIN with TABLES view.
- **Files**: 11 new (Python, SQL views/tasks/procedures, config, instruments-def, BOM, readme, tests, fixtures), 3 modified (700_dtagent.sql, USECASES.md, CHANGELOG.md).

### New Plugin: Metering

- **Problem**: `event_usage` plugin reads only `EVENT_USAGE_HISTORY`, covering a single service type (`TELEMETRY_DATA_INGEST`). `METERING_HISTORY` covers all service types, enabling full FinOps visibility.
- **Solution**: New `metering` plugin reading `SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY` with `WHERE SERVICE_TYPE != 'WAREHOUSE_METERING'` to avoid duplication with `warehouse_usage`.
- **Metrics**: `snowflake.credits.used`, `snowflake.credits.used.compute`, `snowflake.credits.used.cloud_services`, `snowflake.data.size`, `snowflake.data.rows`, `snowflake.data.files` — all with `snowflake.service.type` and `snowflake.service.name` dimensions.
- **Migration**: `event_usage` disabled by default, logs deprecation warning. `snowflake.credits.used` metric name preserved for backward compatibility. Filter `snowflake.service.type == "TELEMETRY_DATA_INGEST"` reproduces old data.
- **Files**: `src/dtagent/plugins/metering.py`, `metering.sql/` (view, task, config proc), `metering.config/` (config, instruments-def, bom, readme), test fixtures and test file.
- **Removal plan**: `event_usage` will be fully removed in 0.9.6.

### Dependency Maintenance — Snowflake SDK Audit and Version Update

- **Scope**: Full audit of all four Snowflake SDK packages in `requirements.txt` against latest stable PyPI releases.
- **Findings**:
  - `snowflake==1.12.0` — already at latest stable; no change.
  - `snowflake-core==1.12.0` — already at latest stable; no change.
  - `snowflake-connector-python>=4.4.0` — already at latest stable; no change.
  - `snowflake-snowpark-python>=1.48.1` — **updated to `>=1.49.0`** (released 2026-04-13). No breaking API changes
    affecting DSOA usage patterns (`Session`, `DataFrame`, `write_pandas`, cursor operations).
- **Python version constraint**: Constraint remains `<3.14`. Initial analysis incorrectly attributed the upper bound
  to `snowflake-snowpark-python==1.49.0` (which declares `<3.15`), but the binding constraint is `snowflake==1.12.0`
  which declares `requires_python: <3.14,>=3.10`. `snowflake-core==1.12.0` has no Python upper bound. Python 3.14
  support will require a new `snowflake` package release from Snowflake. Comment corrected accordingly.
- **Protobuf constraint unchanged**: `snowflake-snowpark-python==1.49.0` still caps at `protobuf<6.34`, consistent
  with the existing `>=6.33.5,<6.34` security pin (CVE-2026-0994). Updated inline comment to reference `>=1.49.0`.
- **Compatibility verified**: `pip install -r requirements.txt` clean; `pip check` no broken deps; SDK import smoke
  test passed; 99 core tests passed (3 skipped); pylint 10.00/10.
- **Files changed**: `requirements.txt`

### Bug Fixes

#### BCR Bundle 2026\_02: Adapt to New `LOG_EVENT_LEVEL` Parameter

- **Background**: Snowflake BCR Bundle 2026\_02 (enabled week of April 6 2026) introduces a new `LOG_EVENT_LEVEL`
  parameter that decouples event table ingestion control from the existing `LOG_LEVEL` parameter. Previously,
  `LOG_LEVEL` controlled both diagnostic output and what severity of events was ingested into the event table.
  After the BCR, `LOG_EVENT_LEVEL` must also be set to ensure events reach the event table. Without this change,
  DSOA deployments on BCR-active accounts would silently lose event log telemetry for everything below the
  account-default `LOG_EVENT_LEVEL` value.
- **Detection pattern**: Both `SETUP_EVENT_TABLE()` and `002_init_db.sql` probe for the parameter using
  `SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL'` before attempting to set it. A `count(*) > 0` on `result_scan()`
  determines whether the parameter exists. The probe itself is wrapped in `EXCEPTION WHEN OTHER` so that any
  unexpected error on pre-BCR accounts is also handled gracefully.
- **`009_event_log_init.sql`** (`SETUP_EVENT_TABLE()`): When DSOA creates its own event table (the DSOA-owned
  branch), after setting `LOG_LEVEL = WARN` the procedure now also: (1) sets `ALTER ACCOUNT SET LOG_EVENT_LEVEL = INFO`
  and (2) grants `MODIFY LOG EVENT LEVEL ON ACCOUNT TO ROLE DTAGENT_VIEWER`. Both operations are guarded by the
  BCR detection flag `b_has_log_event_level`. The custom-event-table branch is intentionally left unchanged —
  when DSOA uses a pre-existing event table, the account operator controls ingestion levels.
- **`002_init_db.sql`**: A top-level `BEGIN … END` scripting block probes `SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL'
  IN DATABASE DTAGENT_DB` and, if the parameter exists, sets `ALTER DATABASE DTAGENT_DB SET LOG_EVENT_LEVEL = INFO`.
  This mirrors the existing `ALTER DATABASE DTAGENT_DB SET LOG_LEVEL = INFO` and ensures that procedures inside
  `DTAGENT_DB` emit events at INFO+ into the event table.
- **Why `INFO`, not `DEBUG`**: `LOG_LEVEL = INFO` (set in `002_init_db.sql`) controls what DSOA procedures emit.
  `LOG_EVENT_LEVEL = INFO` ensures those INFO+ emissions land in the event table. Setting `DEBUG` would flood the
  event table with internal Snowflake framework noise. The `V_EVENT_LOG` view already applies an additional filter
  (`severity_text not in ('DEBUG', 'INFO')` for DTAGENT-family DBs) to suppress DSOA self-noise from the telemetry
  pipeline, so there is no telemetry loss with `INFO`.
- **`bom.yml`**: Added `MODIFY LOG EVENT LEVEL` privilege reference with a comment noting it is only granted on
  BCR-active accounts.
- **No upgrade script needed**: `SETUP_EVENT_TABLE()` signature is unchanged; no Snowflake overload conflict.
- **Files changed**: `src/dtagent/plugins/event_log.sql/init/009_event_log_init.sql`,
  `src/dtagent.sql/init/002_init_db.sql`, `src/dtagent/plugins/event_log.config/bom.yml`

#### Deploy Pipeline: Cleanup Option for Disabled and Removed Plugins (`--options=cleanup_disabled`)

- **Background**: `inject_suspend_for_excluded_plugins()` already suspends tasks for disabled plugins. This extends the deploy pipeline with a full object cleanup option for operators who want to actively drop stale views, procedures, and tasks — not just suspend them.
- **New option**: `--options=cleanup_disabled` passed to `deploy.sh` is forwarded to `prepare_deploy_script.sh` (via a new 6th positional argument `OPTIONS_STR`). `prepare_deploy_script.sh` exposes a `has_option()` helper (mirrors the one in `deploy.sh`) to parse the options string.
- **`inject_cleanup_for_excluded_plugins()`** (new function in `prepare_deploy_script.sh`):
  - **Part 1 — disabled plugins**: For each plugin in `EXCLUDED_PLUGINS`, parses `build/30_plugins/<plugin>.sql` and emits `DROP TASK/PROCEDURE/VIEW IF EXISTS` for all objects defined there. Tasks are suspended before being dropped.
  - **Part 2 — removed plugins**: Reads `conf/removed_plugins.yml`. For each entry, emits `ALTER TASK ... SUSPEND` + `DROP TASK IF EXISTS` for every listed task name. This covers plugins fully deleted from the codebase that no longer appear in `EXCLUDED_PLUGINS`.
  - **Part 3 — orphan detection**: Injects a Snowflake `EXECUTE IMMEDIATE` block that queries `INFORMATION_SCHEMA.TASKS WHERE task_name ILIKE 'TASK_DTAGENT_%'`, filters out known active plugin tasks (enumerated from all current build artifacts), and suspends + drops any unrecognised tasks. Runs only when `cleanup_disabled` is set — avoids adding Snowflake round-trips to normal deploys where config scope speed matters.
- **`conf/removed_plugins.yml`** (new file): Tracks plugins permanently removed from the codebase. Committed in git (not gitignored — it's universal, not env-specific). Format: `removed_plugins: [{name, removed_in_version, tasks: [...]}]`. Initially empty. Agents and the plugin-development skill are updated to reference this file as a mandatory step during plugin removal.
- **Procedure extraction**: Uses `grep -oi 'PROCEDURE[[:space:]]\+...' | sed` rather than `awk` capture groups — macOS `awk` does not support `match()` with capture arrays.
- **Files changed**: `scripts/deploy/deploy.sh`, `scripts/deploy/prepare_deploy_script.sh`, `conf/removed_plugins.yml` (new), `.github/copilot-instructions.md`, `.opencode/skills/plugin-development/SKILL.md`

#### Deploy Pipeline: Expanded Tests for Task Suspension and Cleanup

- Added 3 new test cases to `test/bash/test_suspend_disabled_plugins.bats`: `disabled_by_default` mode, `--scope=config` only, and multiple plugins disabled simultaneously.
- Added new `test/bash/test_cleanup_disabled_plugins.bats` (16 test cases) covering: no-op without flag, single/multi-task drop, view/procedure drop, `removed_plugins.yml` parsing, orphan detection block, TAG support, teardown exclusion, combined options.
- **Files changed**: `test/bash/test_suspend_disabled_plugins.bats`, `test/bash/test_cleanup_disabled_plugins.bats` (new)

#### Config Upload: MERGE → DELETE + INSERT (Full Replace)

- **Root cause**: `040_update_config.sql` used `MERGE INTO CONFIG.CONFIGURATIONS` which is additive — rows present in a previous deploy but absent from the new YAML were never deleted. This meant that a plugin's `is_enabled: true` entry persisted even after the user removed it from their config YAML or switched to `disabled_by_default: true`. The stale entry overrode the new global setting, leaving the plugin enabled.
- **Fix**: Replaced the `MERGE` with a `BEGIN … DELETE FROM … INSERT INTO … END` block. The full YAML is always flattened and uploaded by `prepare_config.sh` (default + env merge), so a full table replace is safe. The `BEGIN/END` wrapper ensures atomicity — no window where the config table is empty.
- **Files changed**: `src/dtagent.sql/config/040_update_config.sql`
- **Backward compatibility**: First deploy with new code performs a full replace. If the user's YAML is complete (guaranteed by `prepare_config.sh`), no data loss. Manual edits to `CONFIG.CONFIGURATIONS` outside the deploy pipeline are not supported and will be lost on next deploy.

#### Deploy Pipeline: Automatic Task Suspension for Disabled Plugins

- **Root cause**: When a plugin is disabled, `prepare_deploy_script.sh` strips its SQL via `filter_plugin_code()`. This means the `CREATE OR REPLACE TASK` statement (which would reset the task to Snowflake's default `suspended` state) is never executed. The existing task from a prior deploy remains in `started` state, consuming warehouse credits and potentially logging errors if underlying views were dropped.
- **Fix**: Added `inject_suspend_for_excluded_plugins()` to `prepare_deploy_script.sh`. After `filter_plugin_code()` runs, this function iterates `EXCLUDED_PLUGINS`, finds each plugin's `*_task.sql` files under `src/dtagent/plugins/<name>.sql/` (recursively, to cover `admin/` subdirectories), extracts the fully-qualified task name from the `CREATE OR REPLACE TASK` statement, and appends `ALTER TASK IF EXISTS <name> SUSPEND;` to the deploy script. The function is called for all scopes except `apikey` and `teardown`.
- **Design decisions**:
  - Task names are extracted from source SQL files rather than hardcoded, so multi-task plugins (e.g. `snowpipes` with `TASK_DTAGENT_SNOWPIPES` + `TASK_DTAGENT_SNOWPIPES_HISTORY`) and admin tasks (e.g. `event_log` with `TASK_DTAGENT_EVENT_LOG_CLEANUP`) are handled automatically.
  - `ALTER TASK IF EXISTS` is used for fresh-deploy safety (task doesn't exist yet → no-op).
  - The injected SQL uses `use role DTAGENT_OWNER` context, consistent with the rest of the deploy script. Custom name / TAG substitution (applied later in the script via `sed`) correctly replaces `DTAGENT_OWNER`, `DTAGENT_DB`, and `DTAGENT_WH` in the injected block.
  - Suspension runs regardless of deploy scope — even `--scope=plugins,agents` (no config scope) will suspend disabled plugin tasks.
- **Files changed**: `scripts/deploy/prepare_deploy_script.sh`

#### Documentation: UPDATE_ALL_PLUGINS_SCHEDULE Scope Clarification

- Added a comment to `037_update_all_plugins_schedule.sql` explaining that the procedure only iterates plugins with a schedule entry in config, and that plugins absent from config are handled by `inject_suspend_for_excluded_plugins()` at deploy time.
- **Files changed**: `src/dtagent.sql/setup/037_update_all_plugins_schedule.sql`

### Tests Added

- `test/bash/test_config_full_replace.bats` — 5 tests verifying DELETE+INSERT pattern in `040_update_config.sql`.
- `test/bash/test_suspend_disabled_plugins.bats` — 8 tests covering: no exclusions → no suspend SQL; single-task plugin; multi-task plugin (snowpipes); admin-task plugin (event_log); role context; scope independence (`plugins,agents`); deploy log output; teardown scope exclusion.

### Hardening — BCR-2275: Explicit Column Lists for ACCOUNT_USAGE Views

Snowflake BCR-2275 changed their policy so new columns in `ACCOUNT_USAGE` views are no longer announced as breaking changes. DSOA SQL views that used `SELECT *` from these system views would silently ingest unexpected columns, risking memory bloat, telemetry corruption, and test fixture drift.

**Views changed:**

- `data_schemas/051_v_data_schemas.sql` — replaced `SELECT *` from `ACCESS_HISTORY` with explicit 7-column list (`QUERY_ID`, `QUERY_START_TIME`, `USER_NAME`, `PARENT_QUERY_ID`, `ROOT_QUERY_ID`, `OBJECT_MODIFIED_BY_DDL`, `OBJECTS_MODIFIED`)
- `snowpipes/054_v_snowpipes_copy_history_instrumented.sql` — replaced `SELECT *` from `COPY_HISTORY` with explicit 22-column list
- `snowpipes/055_v_snowpipes_usage_history_instrumented.sql` — replaced `SELECT h.*` from `PIPE_USAGE_HISTORY` with explicit 7-column list (`PIPE_ID`, `PIPE_NAME`, `START_TIME`, `END_TIME`, `CREDITS_USED`, `BYTES_BILLED`, `FILES_INSERTED`)

**CI gate added:** `test_views_structure.py::test_no_select_star_from_snowflake_views` — detects `SELECT *` / `SELECT alias.*` from any `SNOWFLAKE.*` source in active (non-commented) SQL code. Uses comment-stripping to avoid flagging debug queries. Precision-scoped to avoid false positives from files that reference `SNOWFLAKE.*` in separate statements.

**Existing test bug fixed:** `test_timestamp_columns` had its assertion outside the `for` loop (only checked the last file). Fixed indentation so all instrumented views are validated.

**Doc update:** Added "Never use `SELECT *` when querying Snowflake system views" rule to `PLUGIN_DEVELOPMENT.md` SQL conventions and updated the canonical view template example.

### Test Infrastructure — Technical Details

#### Resource.attributes Included in Protobuf Baseline Comparison

- **Root cause**: `_decode_object_from_protobuf` in `test/_mocks/telemetry.py` iterated
  `resource_logs`/`resource_spans` entries and extracted only record-level and scope-level attributes.
  The `resource.resource.attributes` block on each entry was never accessed, so `db.system`,
  `service.name`, `deployment.environment`, `host.name`, and all `telemetry.*` / `telemetry.sdk.*`
  resource attributes were silently discarded. Tests could pass even if these fields were missing
  or incorrect in exported telemetry.
- **Fix**: Before iterating scope entries, the decoder now reads `resource.resource.attributes`
  (guarded for `None`) and stores them as a `"resource_attributes"` key on every decoded record dict.
  The existing `__cleanup_telemetry_dict` already recurses into nested dicts and already strips
  `telemetry.exporter.version` — no changes to the cleanup function were needed.
- **Baseline update strategy**: Golden baselines (`test/test_results/**/logs.json` and
  `test/test_results/**/spans.json`) cannot be regenerated without a live Snowflake connection
  (see `docs/CONTRIBUTING.md`). All 33 affected files were updated programmatically to inject a
  stable `resource_attributes` block. The injected values match the deterministic test config in
  `test/_utils.py` (`sf_name = "test.dsoa2025"`, `deployment.environment = "TEST"`) plus the
  OTel SDK auto-populated attributes (`telemetry.sdk.*`). The OTel SDK is pinned to `1.39.1`
  in `requirements.txt`, so `telemetry.sdk.version` is stable across environments.
- **Mutation coverage verified**: Changing `db.system` from `"snowflake"` to `"mysql"` in one
  baseline causes the corresponding test to fail, confirming the new key is actively asserted.
- **Files changed**: `test/_mocks/telemetry.py`, all 30 `logs.json` + 3 `spans.json` baselines.

## Version 0.9.4 — Detailed Changes

### Bug Fixes — Technical Details

#### Dependency Security Upgrades — Dependabot CVE Remediation

- **Scope**: 7 open Dependabot alerts in `requirements.txt`, covering 5 packages.
- **Root cause for pyOpenSSL block**: `snowflake-connector-python<4.4.0` had an upper bound of `pyOpenSSL<26.0.0`,
  preventing the CVE fix. `snowflake-connector-python==4.4.0` (released 2026-03) removed that upper bound and itself
  bumped its minimum `cryptography` requirement to `>=46.0.5`.
- **Changes**:
  - `snowflake-connector-python>=4.4.0` (was `>=4.3.0`): lifts pyOpenSSL upper bound; resolves alerts #9 + #10.
  - `snowflake-snowpark-python>=1.48.1` (was `>=1.45.0`): picks up latest Snowpark SDK improvements.
  - `cryptography>=46.0.6` (was `>=46.0.5`): fixes SECT-curve subgroup attack (alert #3) and incomplete DNS
    name constraint enforcement (alert #13).
  - `requests>=2.33.0` (new pin): fixes insecure temp-file reuse in `extract_zipped_paths()` (alert #12).
  - `pyOpenSSL>=26.0.0` (new pin, replaces BLOCKED comment): fixes DTLS cookie callback buffer overflow (alert
    #10, HIGH) and TLS connection bypass via unhandled callback (alert #9, LOW).
  - `Pygments>=2.20.0` (new pin): fixes ReDoS via inefficient GUID-matching regex (alert #14, LOW). Pygments
    is a transitive dependency via `pytest` and `rich`.
  - Retained existing `urllib3>=2.6.3` and `wheel>=0.46.2` pins (no new alerts; still protective).
- **Protobuf alert #4**: advisory range is `>=6.30.0rc1,<=6.33.4` (6.x series only). Our pin `>=5.29.6,<6.0.0`
  means we are on the patched 5.x series and not affected. Alert can be dismissed as "not applicable" on GitHub.
- **Files changed**: `requirements.txt`

#### Tasks Plugin — Timestamp Fields Converted to Epoch Nanoseconds (TI-001)

- **Root cause**: `V_TASK_HISTORY` passed `th.SCHEDULED_TIME` and `th.COMPLETED_TIME` directly into the `ATTRIBUTES` OBJECT_CONSTRUCT without any conversion. Snowflake serialises `TIMESTAMP_LTZ` values as ISO 8601 datetime strings (e.g. `"2025-04-29 00:00:00.000 Z"`) inside a VARIANT/OBJECT. Every other timestamp attribute across all plugins uses `extract(epoch_nanosecond from ...)` — these two fields were the only exceptions. The `instruments-def.yml` `__example` values had been written to match the broken output rather than the intended contract.
- **Additional scope**: `V_TASK_VERSIONS` had the same bug for `LAST_COMMITTED_ON` and `LAST_SUSPENDED_ON` — passed raw into ATTRIBUTES despite the `instruments-def.yml` already documenting them with epoch-nanos examples (`"1633046400000000000"`).
- **Fix**:
  - `062_v_task_history.sql`: `th.SCHEDULED_TIME` → `CASE WHEN th.SCHEDULED_TIME IS NOT NULL THEN extract(epoch_nanosecond from th.SCHEDULED_TIME) ELSE -1 END`; same for `COMPLETED_TIME`. Sentinel `-1` is consistent with the `QUERY_START_TIME` NULL-guard already in this view.
  - `063_v_task_versions.sql`: `tv.LAST_COMMITTED_ON` / `tv.LAST_SUSPENDED_ON` → `extract(epoch_nanosecond from ...)`. No sentinel needed — these are nullable attributes, `extract()` of NULL produces NULL which is dropped from the OBJECT_CONSTRUCT.
  - `tasks.config/instruments-def.yml`: updated `__example` for `snowflake.task.run.scheduled_time` and `snowflake.task.run.completed_time` to epoch nanos strings.
- **Test fixtures updated**:
  - `test/test_data/tasks_history.ndjson`: converted `scheduled_time` values to epoch nanos integers; added `completed_time: -1` (fixtures represent SCHEDULED-state tasks with no completion yet).
  - `test/test_results/test_tasks/logs.json`: golden output updated to match.
- **Dashboard impact** (`tasks-pipelines.yml`, bumped to v26):
  - Tile 3 (Task Run Duration Trend): removed `toTimestamp()` workaround; now uses direct `toLong()` integer subtraction. Added `> 0` guards to exclude `-1` sentinel values from duration calculation.

#### Dynamic Tables — Scheduling State Empty String (TI-004)

- **Root cause**: Extracting a path from a Snowflake VARIANT column via `:path` notation returns an empty string `""` (not `NULL`) when the key exists in the JSON object but its value is an empty string or absent. `SCHEDULING_STATE` is a VARIANT column; when a dynamic table has no active reason code or message, Snowflake populates those keys with empty strings. The extracted values flowed into the `ATTRIBUTES` object and then into Dynatrace logs as `""` — causing DQL `isNull()` checks to miss them and forcing callers to add `!= ""` workaround filters.
- **Fix**: `053_v_dynamic_tables_instrumented.sql` CTE `cte_dynamic_tables` — wrapped all three VARIANT path extractions with `NULLIF(...::VARCHAR, '')`:

  ```sql
  NULLIF(SCHEDULING_STATE:state::VARCHAR, '')          as SCHEDULING_STATE_STATE,
  NULLIF(SCHEDULING_STATE:reason_code::VARCHAR, '')    as SCHEDULING_STATE_REASON_CODE,
  NULLIF(SCHEDULING_STATE:reason_message::VARCHAR, '') as SCHEDULING_STATE_REASON_MESSAGE,
  ```

  The explicit `::VARCHAR` cast is required before `NULLIF` to ensure consistent comparison — without it the VARIANT type would be compared against a VARCHAR literal which behaves inconsistently across Snowflake versions.
- **Dashboard impact** (`tasks-pipelines.yml`):
  - Tile 10 (Scheduling State Heatmap): removed `| filter snowflake.table.dynamic.scheduling.state != ""` — now redundant since `NULL` is the canonical absence value.

**Files changed:**

- `src/dtagent/plugins/tasks.sql/062_v_task_history.sql`
- `src/dtagent/plugins/tasks.sql/063_v_task_versions.sql`
- `src/dtagent/plugins/tasks.config/instruments-def.yml`
- `src/dtagent/plugins/dynamic_tables.sql/053_v_dynamic_tables_instrumented.sql`
- `test/test_data/tasks_history.ndjson`
- `test/test_results/test_tasks/logs.json`
- `docs/dashboards/tasks-pipelines/tasks-pipelines.yml`

### New Features — Technical Details

#### Dashboard and Workflow Deployment Script

- **Motivation**: Dynatrace dashboards and workflows were previously imported manually through the UI. This was error-prone,
  not reproducible, and blocked CI/CD automation of the full observability stack.
- **Solution**: New `scripts/deploy/deploy_dt_assets.sh` script uses `dtctl apply` to deploy YAML-sourced dashboards and
  workflows directly to a Dynatrace tenant.
- **YAML → dtctl envelope**: Dashboard YAMLs contain raw content (tiles, variables, layouts) without top-level `id`/`name`.
  The script wraps them in a `{name, type, content}` envelope via `jq`. If an `id` is present in the JSON (post-round-trip),
  it is popped out of `content` and placed at the envelope level — matching `dtctl`'s expected structure.
- **Asset name extraction**: Human-readable names are read from `# DASHBOARD:` / `# WORKFLOW:` comments in the YAML files
  (existing convention from `package.sh`). Falls back to directory name if comment is absent.
- **Idempotency**: First deploy creates with auto-generated ID; subsequent deploys update in place once the ID is
  stored back in the YAML.
- **`dt_assets` scope in `deploy.sh`**: Added opt-in scope at the end of `deploy.sh` (after `send_bizevent FINISHED`).
  Deliberately excluded from the default `all` scope — `dtctl` is optional and not a standard deployment dependency.
  The scope passes `--dry-run` through via `$DRY_RUN_FLAG`.
- **Error handling**: Per-asset failures are logged but do not abort the run; remaining assets continue. Exit code reflects
  overall success/failure.
- **Tests**: 16 bats tests in `test/bash/test_deploy_dt_assets.bats` covering argument validation, dtctl availability,
  scope filtering, dry-run passthrough, YAML→JSON conversion, missing directories, summary output, and
  name extraction from comments.
- **New directory**: `docs/workflows/` created with `README.md` as placeholder for upcoming workflow YAMLs.
- **Docs updated**: `docs/INSTALL.md` — new `## Deploying Dashboards and Workflows` section; `docs/dashboards/README.md` —
  added deployment script as the recommended import method.

#### Five Anomaly Detection Workflows

Five Davis AI anomaly detection workflows covering core Snowflake observability themes:

| Workflow                                | Plugin              | Analyzer                                   | Interval | Alert Condition                        |
|-----------------------------------------|---------------------|--------------------------------------------|----------|----------------------------------------|
| Credits Exhaustion Prediction           | `resource_monitors` | `GenericForecastAnalyzer`                  | 4 h      | upper-bound forecast > 100%            |
| Query Slowdown Detection                | `query_history`     | `AutoAdaptiveAnomalyDetectionAnalyzer`     | 6 h      | ABOVE (avg exec time)                  |
| Data Volume Anomaly Detection           | `data_volume`       | `SeasonalBaselineAnomalyDetectionAnalyzer` | 12 h     | ABOVE (row count spike, top 10 tables) |
| Table Performance Degradation Detection | `query_history`     | `AutoAdaptiveAnomalyDetectionAnalyzer`     | 12 h     | ABOVE (partition scan ratio)           |
| Dynamic Table Refresh Drift Detection   | `dynamic_tables`    | `AutoAdaptiveAnomalyDetectionAnalyzer`     | 6 h      | ABOVE (excess lag)                     |

**All workflows use native `timeseries` DQL** — not `fetch logs/events | makeTimeseries`. This
is required because Davis analyzers expect metric dimensions in `by:` clauses; attributes
(non-dimension fields) cannot be used in `timeseries` filters or `by:` and would cause a
`FIELD_DOES_NOT_EXIST` error at runtime.

**3-task pattern (anomaly detection workflows):**

1. `davis-analyze` task — runs a Davis analyzer against a native `timeseries` DQL query. The
   time-series appends `metric_name`, `_event_name_template`, and `_event_description_template`
   fields via `fieldsAdd` so the JS tasks have access to per-series metadata.
1. `extract_anomaly_events` JS — iterates `analyzerResult.output[]`, builds one Dynatrace event
   object per raised alert, templates dimension values into title/description via
   `{dims:field.name}` placeholders.
1. `ingest_anomaly_events` JS — calls `eventsClient.createEvent()` per event, logs success/fail
   counts.

**Credits exhaustion uses a different 3-task pattern** (forecast, not anomaly detection):

1. `detect_exhaustion` — `GenericForecastAnalyzer` forecasts `snowflake.credits.quota.used_pct`
   14 days ahead with `coverageProbability: 0.9`. Result is accessed as
   `analyzerResult.result.output[]` — each entry has `timeSeriesDataWithPredictions.records[0]`
   with `dt.davis.forecast:upper/point/lower` arrays (14 daily values) and dimension values as
   flat properties on the record.
1. `check_prediction` JS — iterates `result.output`, checks if `dt.davis.forecast:upper` exceeds
   100% anywhere in the 14-day window. Returns `{ violation: bool, violations: [] }`. Skips
   entries with `forecastQualityAssessment == 'NO_DATA'`.
1. `ingest_prediction_events` JS — fires only when `violation == true` (custom condition);
   ingests one event per violating monitor with `forecast.max_upper_pct`,
   `forecast.max_point_pct`, `forecast.day_of_crossing`, and `forecast.quality` properties.

**Event type design decision:** Defaults to `EventIngestEventType.CustomInfo` rather than
`CustomAlert`. `CustomInfo` events appear in the Dynatrace event feed and can be correlated in
notebooks/dashboards without triggering Davis problems and on-call noise. Customers who want
Davis problem correlation switch to `CustomAlert` in the `CONFIG` block at the top of
`extract_anomaly_events` (or `check_prediction` for credits exhaustion).

**Data volume — top-10 scoping:** Rather than monitoring all tables, the query computes a
mean-adjusted row-count delta (`row_count[] - arrayAvg(row_count)`), filters for tables with a
positive delta, sorts descending, and limits to 10. This focuses the seasonal detector on the
most actively changing tables and avoids training degradation from hundreds of near-static series.

**Training windows:** Credits exhaustion and data volume use 30-day windows (slower-moving
cost/quality signals); query slowdown and table degradation use 14 days (performance signals
fluctuate faster); dynamic table drift uses the default window.

**Files:**

- `docs/workflows/credits-exhaustion-prediction/credits-exhaustion-prediction.yml`
- `docs/workflows/data-volume-anomaly/data-volume-anomaly.yml`
- `docs/workflows/dynamic-table-drift/dynamic-table-drift.yml`
- `docs/workflows/query-slowdown-detection/query-slowdown-detection.yml`
- `docs/workflows/table-perf-degradation/table-perf-degradation.yml`
- Each workflow has a `readme.md` and `img/.gitkeep`
- `docs/workflows/README.md` — Available Workflows table updated with all 5 entries
- `test/tools/setup_test_workflows.sql` — synthetic Snowflake objects for end-to-end validation

#### Budgets & FinOps Dashboard

- Added `docs/dashboards/budgets-finops/budgets-finops.yml` — 13-tile dashboard (v17) across 3 sections:
  - **Section 1 — Budget Analysis**: budget spending vs limit (join query), spending trend (lineChart), spending by service type (pieChart), budget details (table with owner/resources).
  - **Section 2 — Warehouse Optimization**: warehouse sizing overview (table with threshold for unmonitored warehouses), cluster utilization over time (lineChart), resource monitor quota usage over time (lineChart).
  - **Section 3 — Warehouse Load**: running vs queued queries (lineChart), average running queries by warehouse (honeycomb), blocked queries over time (lineChart with threshold).
- Event Table Ingest Costs section removed: `ACCOUNT_USAGE.EVENT_USAGE_HISTORY` is deprecated per Snowflake docs; will be replaced by a future `metering` plugin.
- DQL variables use `fields | dedup | sort` pattern (not `summarize by:`); all variable queries include `from: now()-7d` to ensure data within the default window.

#### V_BUDGET_SPENDINGS Date Filter Fix

- **Root cause**: `V_BUDGET_SPENDINGS` filtered with `to_timestamp(MEASUREMENT_DATE) > GREATEST(timeadd(hour,-24,...), F_LAST_PROCESSED_TS(...))`. Because `MEASUREMENT_DATE` is a `DATE` column, `to_timestamp('2026-03-30')` evaluates to `2026-03-30 00:00:00`, which is always earlier than the last-processed timestamp on any intra-day run — causing today's spending rows to be excluded permanently until the next calendar day.
- **Fix**: Changed to `to_date(MEASUREMENT_DATE) >= to_date(GREATEST(...))` in `budgets.sql/072_v_budget_spendings.sql:43`.

#### Deploy TAG Substitution Fix

- **Root cause**: `prepare_deploy_script.sh` line 593 used `s/DTAGENT_/DTAGENT_${TAG}_/g` — a blanket replacement that ran *after* `prepare_configuration_ingest.sh` had already inlined config key-value pairs (including budget FQNs like `DTAGENT_DB.APP.DTAGENT_BUDGET`) as SQL string literals in `INSERT` statements. The glob pattern rewrote these string values, producing non-existent budget names such as `DTAGENT_QA_DB.APP.DTAGENT_QA_BUDGET`.
- **Fix**: Replaced the single blanket sed with eight explicit per-identifier word-boundary patterns (mirroring the `CUSTOM_NAMES_USED` branch), covering only the known SQL object identifiers: `DTAGENT_API_INTEGRATION`, `DTAGENT_API_KEY`, `DTAGENT_OWNER`, `DTAGENT_ADMIN`, `DTAGENT_VIEWER`, `DTAGENT_DB`, `DTAGENT_WH`, `DTAGENT_RS`. Config string literals containing other `DTAGENT_*` substrings are now left untouched.
- The old double-TAG de-duplication line (`s/${TAG}_${TAG}_/${TAG}_/g`) was removed — it is no longer needed with precise patterns.

#### Budget Grant Procedure Fixes (P_GRANT_BUDGET_MONITORING)

Three Snowflake-specific failure modes handled via per-grant `BEGIN/EXCEPTION` blocks:

1. **Imported/shared databases** (`SNOWFLAKE`): `GRANT USAGE ON DATABASE` is not permitted; falls back to `GRANT IMPORTED PRIVILEGES ON DATABASE`.
2. **Application schemas** (`SNOWFLAKE.LOCAL`): `GRANT USAGE ON SCHEMA` raises on application-owned schemas; caught and logged, execution continues.
3. **Application-owned budgets** (`ACCOUNT_ROOT_BUDGET`): `GRANT SNOWFLAKE.CORE.BUDGET ROLE !VIEWER` is not permitted on application-owned budgets; caught and logged. Access is covered by `GRANT APPLICATION ROLE SNOWFLAKE.BUDGET_VIEWER` granted unconditionally at account level.

#### Discoveries about Snowflake Budgets API

- `ACCOUNT_ROOT_BUDGET` does **not** support `!GET_SPENDING_LIMIT()`, `!GET_LINKED_RESOURCES()`, or `!GET_SPENDING_HISTORY()` — these instance methods only work on custom (database-scoped) budgets.
- `CREATE BUDGET IF NOT EXISTS` is unsupported DDL syntax; `CREATE BUDGET` only (re-running raises if exists, which is safe to ignore).
- `SNOWFLAKE.ACCOUNT_USAGE.EVENT_USAGE_HISTORY` is deprecated per Snowflake documentation (March 2026). Removed `event_usage` plugin from test-qa config; dashboard Event Table Ingest section deferred to a future `metering` plugin.

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

#### SNOWFLAKE.TELEMETRY.EVENTS Support

- **Issue**: When a customer account had `EVENT_TABLE = snowflake.telemetry.events` (the Snowflake-managed shared event table), `SETUP_EVENT_TABLE()` listed it in `a_no_custom_event_t` — the "not a real custom table" array — and took the `IF` branch, creating DSOA's own `DTAGENT_DB.STATUS.EVENT_LOG` table and **ignoring** the Snowflake-managed table entirely.
- **Root cause**: `'snowflake.telemetry.events'` was excluded from the view-creation path because the original `ELSE` branch attempted `GRANT SELECT ON TABLE snowflake.telemetry.events TO ROLE DTAGENT_VIEWER`, which Snowflake rejects — privileges cannot be granted on Snowflake-managed objects.
- **Fix**: Two-part change in `src/dtagent/plugins/event_log.sql/init/009_event_log_init.sql`:
  1. Removed `'snowflake.telemetry.events'` from `a_no_custom_event_t` so it falls through to the `ELSE` branch
  2. Wrapped the `GRANT SELECT` in a `BEGIN/EXCEPTION WHEN OTHER THEN SYSTEM$LOG_WARN()` block — attempts the grant and logs warnings, ignoring failures for any read-only or Snowflake-managed table; more robust than a string comparison
- **Behaviour after fix**: When `EVENT_TABLE = snowflake.telemetry.events`, DSOA creates `DTAGENT_DB.STATUS.EVENT_LOG` as a **view** over it, exactly as for any other pre-existing customer event table. All three `event_log` SQL views continue to query `DTAGENT_DB.STATUS.EVENT_LOG` unchanged — no Python changes needed.

#### Configurable Lookback Time

- **Motivation**: Lookback windows were hardcoded across SQL views in every plugin that uses `F_LAST_PROCESSED_TS`. This could not be tuned per deployment without modifying SQL files.
- **Approach**: Replace each literal with `CONFIG.F_GET_CONFIG_VALUE('plugins.<plugin>.lookback_hours', <default>)` and add `lookback_hours` to each plugin's config YAML — consistent with how `retention_hours` is already handled in `P_CLEANUP_EVENT_LOG`.
- **Pattern**: `timeadd(hour, -1*F_GET_CONFIG_VALUE('plugins.<plugin>.lookback_hours', <N>), current_timestamp)` — the `-1*` multiplier converts the positive config value to a negative offset.
- **Note**: The `F_LAST_PROCESSED_TS` guard in each view's `GREATEST(...)` clause ensures normal incremental runs are unaffected; `lookback_hours` only bounds the fallback window when no prior timestamp exists.
- **Files changed** (SQL views + config YAMLs):

| Plugin            | SQL view(s)                                                                                                                      | Default                                    |
|-------------------|----------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| `event_log`       | `051_v_event_log.sql`, `051_v_event_log_metrics_instrumented.sql`, `051_v_event_log_spans_instrumented.sql`                      | `24`h                                      |
| `login_history`   | `061_v_login_history.sql`, `061_v_sessions.sql`                                                                                  | `24`h                                      |
| `warehouse_usage` | `070_v_warehouse_event_history.sql`, `071_v_warehouse_load_history.sql`, `072_v_warehouse_metering_history.sql`                  | `24`h                                      |
| `tasks`           | `061_v_serverless_tasks.sql` → `lookback_hours` (`4`h); `063_v_task_versions.sql` → `lookback_hours_versions` (`720`h = 1 month) | separate keys, original defaults preserved |
| `event_usage`     | `051_v_event_usage.sql`                                                                                                          | `6`h                                       |
| `data_schemas`    | `051_v_data_schemas.sql`                                                                                                         | `4`h                                       |

### Bug Fixes — Technical Details (Telemetry Events)

#### Dynamic Tables Grant — Schema-Level Granularity

- **Issue**: `P_GRANT_MONITOR_DYNAMIC_TABLES()` always granted `MONITOR` at **database level**, even when the `include` pattern specified a particular schema (e.g. `PROD_DB.ANALYTICS.%`). This caused the procedure to over-grant: a user expecting grants only on `PROD_DB.ANALYTICS` received grants on all schemas in `PROD_DB`.
- **Root cause**: The CTE extracted only `split_part(value, '.', 0)` (the database part) and the schema part was never inspected.
- **Fix**: Three-pass approach in `032_p_grant_monitor_dynamic_tables.sql`:
  1. **Database pass** — `split_part(value, '.', 1) = '%'` → `GRANT … IN DATABASE`.
  2. **Schema pass** — `split_part(value, '.', 1) != '%'` and `split_part(value, '.', 2) = '%'` → `GRANT … IN SCHEMA db.schema`.
  3. **Table pass** — `split_part(value, '.', 1) != '%'` and `split_part(value, '.', 2) != '%'` → `GRANT … ON DYNAMIC TABLE db.schema.table` (no FUTURE grant — not supported by Snowflake at individual table level).
- **Grant matrix**:

  | Include pattern               | Grant level                         |
  |-------------------------------|-------------------------------------|
  | `%.%.%`                       | All databases                       |
  | `PROD_DB.%.%`                 | Database `PROD_DB`                  |
  | `PROD_DB.ANALYTICS.%`         | Schema `PROD_DB.ANALYTICS`          |
  | `PROD_DB.ANALYTICS.ORDERS_DT` | Table `PROD_DB.ANALYTICS.ORDERS_DT` |

- **Files changed**: `032_p_grant_monitor_dynamic_tables.sql`, `bom.yml`, `config.md`
- **Tests added**: `test/bash/test_grant_monitor_dynamic_tables.bats` — structural content checks covering both grant paths

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

#### Shares & Governance Dashboard — Tile 14 Redesign

- **Issue**: Tile 14 ("Shares with Deleted Database") was filtering on `snowflake.share.has_db_deleted == true`,
  which relied on `P_GET_SHARES` checking `SNOWFLAKE.ACCOUNT_USAGE.DATABASES` for each inbound share's mounted
  database. This condition could almost never fire in practice:
  1. Snowflake prevents dropping a database that still backs an active share — the publisher must revoke the
     share first, which removes it from `SHOW SHARES` on the consumer immediately.
  2. Once the share disappears from `SHOW SHARES`, `P_GET_SHARES` no longer iterates over it, so `HAS_DB_DELETED`
     is never written.
  3. Even if the consumer-side DB were somehow deleted independently, `ACCOUNT_USAGE.DATABASES` has up to 3 hours
     of latency before reflecting the deletion.
- **Root cause**: The detection mechanism was architecturally backwards — it tried to observe a Snowflake-side
  state change that is structurally blocked by Snowflake's own referential integrity constraints.
- **Fix**: Replaced the `HAS_DB_DELETED` filter approach with a **Dynatrace log-history comparison**:
  - Query all distinct `(account, context, share_name, db.namespace)` tuples seen in the last 7 days.
  - Filter to those NOT observed in the past 2 hours (the recency window covers ~4 agent run cycles at 30 min cadence).
  - Result: shares that "disappeared" from `SHOW SHARES` between agent runs, regardless of why (revocation,
    deletion, or agent going offline).
- **Why this is better**:
  - Naturally observable: the share simply stops appearing in DSOA logs when it is gone.
  - No Snowflake-side API/view latency.
  - Works for all disappearance causes simultaneously.
  - Agent offline detection is a free bonus — entire account goes dark → all its shares appear in tile 14.
- **Tile renamed**: "Shares with Deleted Database" → "Shares No Longer Observed".
- **Simulation script updated**: `test/simlulations/simulate_unhealthy_shares.sql` — Scenario B now documents
  the log-history approach; the old TMP table direct-injection shortcut has been replaced with a DQL scratch
  query for fast-track validation.
- **Dashboard version**: v18 → v19 (deployed to `579f882f-b7b7-4f78-a51f-64517849dbde`).

#### Self-Monitoring Log Filtering

- **Issue**: Database name filtering logic failed to correctly identify DTAGENT_DB references
- **Root cause**: String matching logic didn't account for fully qualified names
- **Fix**: Updated filtering logic in self-monitoring plugin
- **Impact**: Self-monitoring logs now correctly exclude internal agent operations

### Improvements — Technical Details

#### Execute as Caller Migration

- **Motivation**: All stored procedures used `execute as owner` (explicitly or implicitly), meaning they ran with `DTAGENT_OWNER` privileges regardless of the calling role. This widened the privilege surface unnecessarily — callers could mutate any owner-accessible object through procedure side-effects.
- **Approach**: Switch every procedure to `execute as caller` so it inherits the invoking role's permissions. This required expanding TMP table grants from `select` to `select, truncate, insert` (plus `update` where needed) for `DTAGENT_VIEWER`.
- **Changes by file**:

  | File                                                        | Changes                                                                                                                                                                                                                                                |
  |-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | `resource_monitors.sql/060_p_refresh_resource_monitors.sql` | Grants: `select` → `select, truncate, insert` on `TMP_RESOURCE_MONITORS`, `TMP_WAREHOUSES`. Execution: `owner` → `caller`.                                                                                                                             |
  | `budgets.sql/040_p_get_budgets.sql`                         | Grants: `select` → `select, truncate, insert` on 4 TMP tables. Execution: `owner` → `caller`.                                                                                                                                                          |
  | `users.sql/051_p_get_users.sql`                             | Grants: expanded on `TMP_USERS`, `TMP_USERS_HELPER`, `EMAIL_HASH_MAP` (+ `update, delete`). Refactored `TMP_USERS_SNAPSHOT` from temporary table (created inside procedure) to pre-created transient table with grants. Execution: `owner` → `caller`. |
  | `query_history.sql/061_p_refresh_recent_queries.sql`        | Grants: `select` → `select, truncate, insert, update` on `TMP_RECENT_QUERIES`; `select` → `select, truncate, insert` on `TMP_QUERY_OPERATOR_STATS`. Execution: `owner` → `caller`.                                                                     |
  | `query_history.sql/061_p_get_acc_estimates.sql`             | Grants: `select` → `select, truncate, insert` on `TMP_QUERY_ACCELERATION_ESTIMATES`. Execution: `owner` → `caller`.                                                                                                                                    |
  | `query_history.sql/110_update_processed_queries.sql`        | Added explicit `execute as caller` (was implicit owner).                                                                                                                                                                                               |
  | `setup/100_log_processed_measurements.sql`                  | Added explicit `execute as caller` (was implicit owner).                                                                                                                                                                                               |
  | `event_log.sql/admin/071_p_cleanup_event_log.sql`           | Execution: `owner` → `caller`.                                                                                                                                                                                                                         |
  | `shares.sql/051_p_grant_imported_privileges.sql`            | Replaced with no-op stub (`execute as caller`). Real implementation moved to `shares.sql/admin/051_p_grant_imported_privileges.sql` with `execute as caller` under `DTAGENT_ADMIN` scope.                                                              |
  | `query_history.sql/061_p_query_explain_plan.off.sql`        | Deleted (disabled procedure, dead code).                                                                                                                                                                                                               |

- **Regression test**: `test/bash/test_execute_as_owner.bats` — two tests:
  1. Scans all `.sql` source files for explicit `execute as owner` usage.
  2. Verifies every `CREATE PROCEDURE` has an explicit `execute as` clause (prevents implicit owner default).
  Both tests support an exclusion list for justified exceptions (currently empty).

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

#### Error Handling — Two-Phase Commit for Query Telemetry

- **Issue**: `STATUS.UPDATE_PROCESSED_QUERIES` was called regardless of whether the OTLP trace flush succeeded, meaning queries could be silently lost on export failures without being retried on the next cycle.
- **Root cause**: `_process_span_rows` in `src/dtagent/plugins/__init__.py` called `UPDATE_PROCESSED_QUERIES` unconditionally after `flush_traces()`.
- **Fix**: Captured the boolean return value of `flush_traces()` into `flush_succeeded` and gated the `UPDATE_PROCESSED_QUERIES` call behind `if report_status and flush_succeeded`.
- **Impact**: Queries whose spans fail to export are re-queued on the next agent run, ensuring at-least-once delivery semantics for span telemetry.

#### Event Log Lookback — Configurable Window

- **Issue**: `V_EVENT_LOG` used a hardcoded `timeadd(hour, -24, current_timestamp)` lower bound, preventing operators from adjusting the lookback window without editing SQL.
- **Fix**:
  - `src/dtagent/plugins/event_log.sql/051_v_event_log.sql`: replaced literal with `CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.lookback_hours', 24)::int`.
  - `src/dtagent/plugins/event_log.config/event_log-config.yml`: added `lookback_hours: 24` (default preserves prior behaviour).
- **Impact**: Operators can increase the window for initial deployments or decrease it for high-volume environments without any SQL change.

#### AI-Assisted Development Infrastructure (Vibe Coding)

- **Motivation**: Enable AI coding assistants (GitHub Copilot, OpenCode, Windsurf) to work effectively with the DSOA codebase by providing structured project context, domain knowledge, and safety guardrails — reducing onboarding time and preventing common mistakes.
- **Central instructions file** (`.github/copilot-instructions.md`, 264 lines):
  - "DSOA coding sidekick" persona definition
  - Core architecture overview and key module map (agent lifecycle, plugin system, core modules)
  - Mandatory Snowflake connection safety rules (system roles forbidden, deployment limited to `test-qa`)
  - Code style enforcement expectations (black, flake8, pylint 10.00/10, sqlfluff, markdownlint)
  - 4-phase delivery workflow (Proposal → Plan → Implement → Validate) with artifact storage in `.github/context/proposals/`
  - Continuous learning loop: AI updates instructions/skills after every human review to prevent recurring mistakes
  - Git tracking rules, auth patterns, plugin isolation principles, SQL/Python syntax conventions
- **OpenCode integration**:
  - `.opencode/opencode.json` (tracked) links OpenCode agent to `.github/copilot-instructions.md`
  - `.opencode/package-lock.json` (tracked) pins `@opencode-ai/plugin` v1.4.3 dependency
  - `.opencode/.gitignore` excludes local runtime artifacts (`node_modules`, `package.json`, `bun.lock`)
- **Seven domain skills** (`.opencode/skills/`, ~3,500 lines total, all tracked):
  1. **`plugin-development`** (737 lines): full plugin lifecycle — scaffolding, SQL/Python/config triad patterns, `instruments-def.yml` authoring (with `__description`/`__example`), testing patterns (mock/live modes, `disabled_telemetry` combinations, include/exclude filtering), BOM authoring
  2. **`dynatrace-dashboard`** (786 lines): dashboard creation — DQL best practices (lessons learned from debugging), tile patterns, metric/attribute reference via `instruments-def.yml`, `dtctl` deploy workflow, YAML format conventions, variable filtering patterns
  3. **`dynatrace-workflow`** (192 lines): workflow YAML authoring — trigger types (cron/event), task patterns, `dtctl` deployment, manual trigger testing
  4. **`qa-runner`** (859 lines): AI-guided QA walkthrough — version discovery automation, deployment guidance, notebook deployment, DQL auto-evaluation via MCP Dynatrace query tools, interactive test checklist, QA signoff report generation
  5. **`snowflake-synthetic`** (450 lines): synthetic test data setup — Snowflake object creation for telemetry validation, DSOA-independence principle, environment reference for `test-qa`
  6. **`pr-reviewer`** (357 lines): PR review automation — structured review phases, GraphQL thread fetching, triage methodology, review quality criteria
  7. **`dashboard-docs`** (203 lines): dashboard documentation standards — narrative-first style, section structure, screenshot placement rules, mandatory sections
- **Semantic telemetry as AI context**:
  - `src/dtagent.conf/instruments-def.yml` (global definitions) and 16 per-plugin `instruments-def.yml` files serve dual purpose:
    1. Auto-generate `docs/SEMANTICS.md` and `build/_semantics.py` (primary purpose)
    2. Provide AI agents with structured semantic understanding (`__description`, `__example`, `__context_names`) for every metric/attribute/dimension to enable correct DQL query authoring without trial-and-error
  - Enables AI agents to write semantically correct queries without consulting external docs
- **Private context scaffold**:
  - `.github/context/` directory (gitignored per root `.gitignore`) provides entry points for developer-local planning artifacts:
    - `.github/context/.gitkeep` (tracked): preserves directory structure
    - `.github/context/ai-memory/` (gitignored): for AI session memories across tool invocations
    - `.github/context/dev-notes/` (gitignored): for developer planning and analysis
    - `.github/context/pm-notes/` (gitignored): for PM/product analysis
    - `.github/context/prompts/` (gitignored): for reusable prompt engineering templates
    - `.github/context/windsurf_plans/` (gitignored): for Windsurf-specific implementation plans
  - Content is intentionally never committed — only directory structure ships, allowing each developer to connect their own knowledge base without exposing sensitive information
  - Skills reference `proposals/` subdirectory as working directory for Phase 1 delivery artifacts
- **Multi-tool strategy**:
  - Same `.github/copilot-instructions.md` is consumed natively by GitHub Copilot and referenced by OpenCode via `opencode.json` config
  - Windsurf agents can optionally use `.github/context/windsurf_plans/` for local planning
  - Avoids tool-specific lock-in while maintaining a single source of truth for project context and conventions
- **Files shipped in repository** (git-tracked): `.github/copilot-instructions.md`, `.opencode/opencode.json`, `.opencode/package-lock.json`, 7× `.opencode/skills/*/SKILL.md`, `.github/context/.gitkeep`
- **Security model**: Credentials/sensitive context stay local (`.github/context/` gitignored). Instructions document safe patterns (`read_secret()`, `_snowflake.py` module). AI guardrails prevent accidental role escalation or credential commits.

#### Query Hierarchy Validation

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

#### Event Tables Cost Optimization Documentation

- **Change**: Expanded `event_log.config/config.md` from a minimal 5-line note to a full configuration reference
- **Content added**:
  - Configuration options table covering all 7 plugin settings with types, defaults, and descriptions
  - Cost optimization guidance section explaining the cost impact of `LOOKBACK_HOURS`, `MAX_ENTRIES`, `RETENTION_HOURS`, and `SCHEDULE`
  - Key guidance: `retention_hours` should be `>= lookback_hours` to prevent cleanup from removing events before they are processed
- **Files changed**:
  - `src/dtagent/plugins/event_log.config/config.md` — full configuration reference + cost guidance
  - `src/dtagent/plugins/event_log.config/readme.md` — updated to mention configurable lookback window

#### Span Timestamp Handling Fix

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

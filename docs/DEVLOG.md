# Development Log

This file documents detailed technical changes, internal refactorings, and development notes. For user-facing highlights, see [CHANGELOG.md](CHANGELOG.md).

## Version 0.9.4 — Detailed Changes

### Bug Fixes — Technical Details

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
- Dashboard deployed at ID `64b09f3f-1faa-49c8-98ba-7aa496af8cdf` on `aym57094.sprint`.

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

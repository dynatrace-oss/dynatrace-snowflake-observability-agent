# Budgets & FinOps Dashboard and Related Fixes

## Budgets & FinOps Dashboard

- Added `docs/dashboards/budgets-finops/budgets-finops.yml` — 13-tile dashboard (v17) across 3 sections:
  - **Section 1 — Budget Analysis**: budget spending vs limit (join query), spending trend (lineChart), spending by service type (pieChart), budget details (table with owner/resources).
  - **Section 2 — Warehouse Optimization**: warehouse sizing overview (table with threshold for unmonitored warehouses), cluster utilization over time (lineChart), resource monitor quota usage over time (lineChart).
  - **Section 3 — Warehouse Load**: running vs queued queries (lineChart), average running queries by warehouse (honeycomb), blocked queries over time (lineChart with threshold).
- Event Table Ingest Costs section removed: `ACCOUNT_USAGE.EVENT_USAGE_HISTORY` is deprecated per Snowflake docs; will be replaced by a future `metering` plugin.
- DQL variables use `fields | dedup | sort` pattern (not `summarize by:`); all variable queries include `from: now()-7d` to ensure data within the default window.

## V_BUDGET_SPENDINGS Date Filter Fix

- **Root cause**: `V_BUDGET_SPENDINGS` filtered with `to_timestamp(MEASUREMENT_DATE) > GREATEST(timeadd(hour,-24,...), F_LAST_PROCESSED_TS(...))`. Because `MEASUREMENT_DATE` is a `DATE` column, `to_timestamp('2026-03-30')` evaluates to `2026-03-30 00:00:00`, which is always earlier than the last-processed timestamp on any intra-day run — causing today's spending rows to be excluded permanently until the next calendar day.
- **Fix**: Changed to `to_date(MEASUREMENT_DATE) >= to_date(GREATEST(...))` in `budgets.sql/072_v_budget_spendings.sql:43`.

## Deploy TAG Substitution Fix

- **Root cause**: `prepare_deploy_script.sh` line 593 used `s/DTAGENT_/DTAGENT_${TAG}_/g` — a blanket replacement that ran *after* `prepare_configuration_ingest.sh` had already inlined config key-value pairs (including budget FQNs like `DTAGENT_DB.APP.DTAGENT_BUDGET`) as SQL string literals in `INSERT` statements. The glob pattern rewrote these string values, producing non-existent budget names such as `DTAGENT_QA_DB.APP.DTAGENT_QA_BUDGET`.
- **Fix**: Replaced the single blanket sed with eight explicit per-identifier word-boundary patterns (mirroring the `CUSTOM_NAMES_USED` branch), covering only the known SQL object identifiers: `DTAGENT_API_INTEGRATION`, `DTAGENT_API_KEY`, `DTAGENT_OWNER`, `DTAGENT_ADMIN`, `DTAGENT_VIEWER`, `DTAGENT_DB`, `DTAGENT_WH`, `DTAGENT_RS`. Config string literals containing other `DTAGENT_*` substrings are now left untouched.
- The old double-TAG de-duplication line (`s/${TAG}_${TAG}_/${TAG}_/g`) was removed — it is no longer needed with precise patterns.

## Budget Grant Procedure Fixes (P_GRANT_BUDGET_MONITORING)

Three Snowflake-specific failure modes handled via per-grant `BEGIN/EXCEPTION` blocks:

1. **Imported/shared databases** (`SNOWFLAKE`): `GRANT USAGE ON DATABASE` is not permitted; falls back to `GRANT IMPORTED PRIVILEGES ON DATABASE`.
2. **Application schemas** (`SNOWFLAKE.LOCAL`): `GRANT USAGE ON SCHEMA` raises on application-owned schemas; caught and logged, execution continues.
3. **Application-owned budgets** (`ACCOUNT_ROOT_BUDGET`): `GRANT SNOWFLAKE.CORE.BUDGET ROLE !VIEWER` is not permitted on application-owned budgets; caught and logged. Access is covered by `GRANT APPLICATION ROLE SNOWFLAKE.BUDGET_VIEWER` granted unconditionally at account level.

## Discoveries about Snowflake Budgets API

- `ACCOUNT_ROOT_BUDGET` does **not** support `!GET_SPENDING_LIMIT()`, `!GET_LINKED_RESOURCES()`, or `!GET_SPENDING_HISTORY()` — these instance methods only work on custom (database-scoped) budgets.
- `CREATE BUDGET IF NOT EXISTS` is unsupported DDL syntax; `CREATE BUDGET` only (re-running raises if exists, which is safe to ignore).
- `SNOWFLAKE.ACCOUNT_USAGE.EVENT_USAGE_HISTORY` is deprecated per Snowflake documentation (March 2026). Removed `event_usage` plugin from test-qa config; dashboard Event Table Ingest section deferred to a future `metering` plugin.

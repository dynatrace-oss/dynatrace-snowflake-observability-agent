# Bug Fixes: Dynamic Tables Grant, Log Timestamp, and Shares Dashboard

## Dynamic Tables Grant — Schema-Level Granularity

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

## Log ObservedTimestamp Unit Correction

- **Issue**: OTel log `observed_timestamp` field was sent in milliseconds
- **Root cause**: OTLP spec requires nanoseconds for `observed_timestamp`, but code was converting to milliseconds
- **Fix**: Modified `process_timestamps_for_telemetry()` to return `observed_timestamp_ns` in nanoseconds
- **Impact**: Logs now comply with OTLP spec
- **Note**: Dynatrace OTLP Logs API still requires milliseconds for `timestamp` field (deviation from spec)

## Inbound Shares Reporting Flag

- **Issue**: `HAS_DB_DELETED` flag incorrectly reported for deleted shared databases in `TMP_SHARES` view
- **Root cause**: Logic error in SQL view predicate
- **Fix**: Corrected SQL logic in `shares.sql/` view definition
- **Impact**: Accurate reporting of deleted shared database status

## Shares & Governance Dashboard — Tile 14 Redesign

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

## Self-Monitoring Log Filtering

- **Issue**: Database name filtering logic failed to correctly identify DTAGENT_DB references
- **Root cause**: String matching logic didn't account for fully qualified names
- **Fix**: Updated filtering logic in self-monitoring plugin
- **Impact**: Self-monitoring logs now correctly exclude internal agent operations

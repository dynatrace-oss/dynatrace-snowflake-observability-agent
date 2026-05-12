# New Plugin: Cold Tables Identification

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

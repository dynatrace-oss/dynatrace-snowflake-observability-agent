# New Plugin: Table Health

## Phase 1: Table Storage Metrics

- **Purpose**: Monitor table storage metrics (active bytes, time-travel bytes, failsafe bytes, retained-for-clone bytes, row count) to identify tables with excessive storage overhead and optimize retention policies.
- **Data source**: `SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS` joined with `SNOWFLAKE.ACCOUNT_USAGE.TABLES` for row count and clustering key.
- **Metrics**: Five gauges (`snowflake.table.active_bytes`, `snowflake.table.time_travel_bytes`, `snowflake.table.failsafe_bytes`, `snowflake.table.retained_for_clone_bytes`, `snowflake.data.rows`).
- **Configuration**: Include/exclude filtering (default: `DTAGENT_DB.%.%` and `%.PUBLIC.%`), `min_table_bytes` (default 1GB), `max_tables` (default 500).
- **Schedule**: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC).
- **Status**: Disabled by default (opt-in plugin).
- **Files**: `src/dtagent/plugins/table_health.py`, `src/dtagent/plugins/table_health.sql/`, `src/dtagent/plugins/table_health.config/`, `test/plugins/test_table_health.py`.
- **Test coverage**: Mock fixture with 2 entries, validates metric counts across disabled_telemetry combinations.

## Phase 2: Clustering Depth Context

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

## Phase 3: Derived Metrics Context

- **Purpose**: Compute period-over-period growth and clustering degradation signals from historical snapshots, enabling alerting on tables that are growing rapidly or whose clustering is degrading.
- **Architecture**: Three new objects — `TABLE_HEALTH_HISTORY` (append-only snapshot table), `P_SNAPSHOT_TABLE_HEALTH()` (inserts one row per table per run by joining `V_TABLE_STORAGE` with `TABLE_CLUSTERING_RESULTS`, then prunes rows older than `history_retention_days`), and `V_TABLE_HEALTH_DERIVED` (CTE-based view using `ROW_NUMBER()` to select the two most recent snapshots per table and compute deltas).
- **Opt-in design**: `history_retention_days: 0` (default) disables both snapshot collection and the `table_health_derived` context. Set to a positive integer (e.g. `30`) to enable. The Python plugin gates the context on `history_retention_days > 0`.
- **Metrics**: Four gauges — `snowflake.table.growth_bytes` (byte delta), `snowflake.table.growth_pct` (percentage delta, null-safe), `snowflake.table.clustering.depth_change` (depth delta), `snowflake.table.clustering.degraded` (0/1 flag when depth increase exceeds `clustering_degradation_threshold`).
- **Degradation threshold**: `clustering_degradation_threshold: 2` (default). Configurable per deployment.
- **Schedule**: `TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT` runs every 6 hours at 02:00, 08:00, 14:00, 20:00 UTC — offset by 2 hours from the storage task (after clustering collection at +1h has completed).
- **New SQL objects**: `055_t_table_health_history.sql`, `056_p_snapshot_table_health.sql`, `057_v_table_health_derived.sql`, `803_table_health_snapshot_task.sql`.
- **New config keys**: `history_retention_days: 0`, `clustering_degradation_threshold: 2`, `schedule_snapshot`.
- **Test coverage**: 6 tests total — both contexts, derived context enabled, derived context disabled by default, storage-only, clustering-only, clustering disabled via config.

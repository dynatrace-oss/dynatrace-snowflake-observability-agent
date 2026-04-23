This plugin enables tracking table storage metrics and clustering depth in Snowflake through reported metrics.

## Table Storage Context

The `table_storage` context reports the following information for each table:

- active bytes (data currently stored in the table),
- time travel bytes (data maintained for Time Travel),
- failsafe bytes (data maintained for Failsafe),
- retained for clone bytes (data retained for cloning),
- number of rows in the table, and
- clustering key definition (if any).

The plugin supports include/exclude filtering to target specific tables and can be configured with minimum table size
and maximum table count constraints.

## Table Clustering Context

The `table_clustering` context reports clustering depth metrics for tables that have a clustering key defined.
It is enabled by default and can be disabled via `clustering_enabled: false`.

The following information is reported:

- average clustering depth (lower is better — 1.0 means perfectly clustered),
- average partition overlap (lower is better),
- constant partition ratio (fraction of partitions fully within one clustering key range — higher is better), and
- total partition count.

Clustering information is collected by the `P_COLLECT_CLUSTERING_INFO()` stored procedure, which calls
`SYSTEM$CLUSTERING_INFORMATION()` per table and stores results in the `TABLE_CLUSTERING_RESULTS` staging table.
The clustering task runs every 6 hours, offset by 1 hour from the storage task to avoid warehouse contention.

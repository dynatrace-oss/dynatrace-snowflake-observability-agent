# Snowflake Query Deep Dive

Advanced query analytics for DBAs and FinOps teams covering eight use cases:
costly repeated queries, table performance degradation, query acceleration analysis,
multi-level query analysis, external function performance, query origin & security,
query cost attribution, and cross-region data transfer monitoring.

## Dashboard ID

`9dbac33a-25ba-4192-b748-c8b6fe561c3b`

## Required Plugin

`query_history`

## DPO Themes

Performance · Security · Costs

## Variables

| Variable | Dimension | Default | Description |
|---|---|---|---|
| `$Accounts` | `deployment.environment` | `*` (all) | Filter to one or more Snowflake accounts |
| `$Warehouse` | `snowflake.warehouse.name` | `*` (all) | Filter by warehouse |
| `$Database` | `db.namespace` | `*` (all) | Filter by database context |
| `$User` | `db.user` | `*` (all) | Filter by Snowflake user |
| `$Operation` | `db.operation.name` | `*` (all) | Filter by SQL operation type (SELECT, INSERT, etc.) |
| `$TopN` | n/a | `10` | Controls how many series the Section 2 charts display (5 / 10 / 25 / 50) |
| `$TenantURL` | n/a | `https://aym57094.sprint.apps.dynatracelabs.com` | Base URL of your Dynatrace tenant — used to construct Distributed Tracing deeplinks in Section 4. Update this to your own tenant URL before using the dashboard. |

The first five variables support multi-select. Every data tile applies them consistently.
`$TopN` and `$TenantURL` are single-select static variables.

## Sections and Tiles

### Section 1 — Costly Repeated Queries

Identifies query patterns (grouped by `snowflake.query.hash`) that accumulate
the most resource consumption across repeated executions.

**Top 20 queries by total bytes scanned** (table)
Ranks query hashes by the sum of `snowflake.data.scanned` across all executions.
Includes execution count and average elapsed time to distinguish high-frequency
cheap queries from low-frequency expensive ones.
A representative query text (`query_text`) is included as the last column — hidden
by default to keep the table readable. See [Viewing query text](#viewing-query-text)
below.

**Top 20 queries by spill volume** (table)
Ranks query hashes by combined local + remote spill (`snowflake.data.spilled.local` +
`snowflake.data.spilled.remote`). High spill indicates memory pressure that can
be resolved by reducing result set sizes, improving joins, or upsizing the warehouse.
Query text is included as the last hidden column. See [Viewing query text](#viewing-query-text)
below.

**Bytes scanned over time by database** (bar chart)
Trends total bytes scanned per database over the selected timeframe. Sudden increases
in a specific database signal a new or modified query pattern worth investigating.

### Section 2 — Table Performance Degradation

Per-table metrics that reveal whether micro-partition clustering is degrading
and whether data is being served from cache or always re-read from storage.

**Partition scan ratio by table** (line chart)
Plots `snowflake.partitions.scanned / snowflake.partitions.total` per table over time.
A ratio approaching 1.0 means nearly all partitions are scanned — a strong signal
the table needs re-clustering on the most-filtered column(s).
Zero-denominator rows are filtered out to avoid division errors.

**Spill volumes by table** (line chart)
Trends local and remote spill (`snowflake.data.spilled.local`,
`snowflake.data.spilled.remote`) per table. Persistent remote spill on a specific
table indicates queries against that table regularly exhaust warehouse memory.

**Cache hit rate by table** (line chart)
Plots `snowflake.data.scanned_from_cache * 100` (percentage) per table. Low cache
hit rates for frequently-read tables suggest those tables are rarely re-queried within
the warehouse result cache window, or that queries vary enough to prevent cache reuse.

### Section 3 — Query Acceleration

Lists queries where Snowflake has flagged acceleration eligibility and tracks
bytes actually offloaded to the query acceleration service.

**Acceleration-eligible queries** (table)
Shows queries where `snowflake.query.accel_est.status == "eligible"` with their
estimated speedup times at various scale factors
(`snowflake.query.accel_est.estimated_query_times`) and the upper limit scale factor.
Sort by `total_elapsed_ms` to prioritise the most expensive eligible queries.

**Acceleration bytes scanned over time by warehouse** (line chart)
Trends bytes scanned by the acceleration service
(`snowflake.acceleration.data.scanned`) per warehouse. Growth here indicates
increasing adoption of the service and can be correlated with execution time
improvements on those warehouses.

### Section 4 — Multi-level Query Analysis

Spans emitted by the `query_history` plugin carry parent-child relationships and
operator-level plan data. Use these tiles to trace procedure call chains and identify
the costliest plan operators.

**Root queries with child queries** (table)
Lists root spans (no `snowflake.query.parent_id`) that have at least one child span,
joined via a `lookup` on `snowflake.query.id`. Shows the query text, number of children,
elapsed time, user, warehouse, database, and operation. A **Trace** column provides a
direct deeplink into Distributed Tracing so you can inspect the full parent-child call
tree. The deeplink is constructed from the `$TenantURL` variable — update it to your
tenant URL before clicking. Sorted by elapsed time descending.

**Operator-level stats (slow queries)** (table)
Shows spans that carry `span.events` with embedded operator statistics (populated only
for queries exceeding `slow_queries_threshold`, default 100 ms). The `operator_stats`
column contains a parsed JSON array of per-operator stats (input/output rows, memory
usage). The `span.events` column holds the raw event array for deeper inspection.
Sorted by elapsed time descending.

### Section 5 — External Functions

Monitors queries that invoke external (remote) functions, tracking invocation
frequency and data volumes to surface latency and bandwidth costs.

**External function invocations over time by warehouse** (line chart)
Trends the total number of remote function calls (`snowflake.external_functions.invocations`)
per warehouse. Spikes indicate new or changed workloads relying on external services.

**External function data volumes by warehouse** (table)
Summarises bytes sent/received and rows sent/received per warehouse and database
across all external function calls. Use this to identify the most data-intensive
remote function consumers.

### Section 6 — Query Origin & Security

Breaks down queries by how they were submitted and who submitted them, supporting
anomalous-access investigation and client application auditing.

**Queries by client application** (pie chart)
Distribution of query counts by `client.application.id`. Unexpected application IDs
or a sudden growth of a new application may indicate unauthorised tooling or a
misconfigured integration.

**Queries by authentication type** (pie chart)
Distribution of query counts by `authentication.type` (e.g., `PASSWORD`, `OAUTH`,
`KEY_PAIR`, `MFA`). A large proportion of PASSWORD-authenticated queries from service
accounts is a security risk and should trigger rotation or migration to key-pair auth.

### Section 7 — Cost Attribution & Data Transfer

Attributes compute and cloud services credits to specific actors and identifies
cross-region transfer costs.

**Cloud services credits by user and role (top 10)** (treemap)
Shows the top 10 user+role combinations by total `snowflake.credits.cloud_services`
consumed. Each rectangle is sized by credit volume; the label shows user and role.
Hover for exact values. Focus optimisation efforts on the largest rectangles.

**Cloud services credits by warehouse** (donut chart)
Ranks warehouses by total cloud services credits, showing up to 10 named slices with
remaining warehouses grouped into "Other". Warehouses with unexpectedly high cloud
services credit consumption often have poorly-optimised queries or excessive
metadata operations.

**Cross-region data transfer by region and cloud** (treemap)
Visualises outbound and inbound transfer volumes broken down by region and cloud
provider. Only records with non-zero transfer volumes are included. Sized by
`outbound_bytes`. Use this to quantify egress costs and identify data pipelines
moving large volumes across regions or clouds.

## Technical Notes

- All numeric metrics (`snowflake.data.scanned`, `snowflake.time.total_elapsed`, etc.)
  are stored as strings in Dynatrace. All queries use `toDouble()` before aggregation.
- Section 4 tiles use `fetch spans` instead of `fetch logs`. The `query_history` plugin
  emits spans for operator-level plan data.
- The `$Warehouse`, `$Database`, `$User`, and `$Operation` variable filters use the
  null-or-match pattern (`isNull(x) or in(x, array($Var))`) so records without those
  dimensions are still shown when the variable is set to the wildcard default `*`.
- The `$Accounts` filter uses a strict `in()` because `deployment.environment` is always
  populated for query_history records.
- The `$TenantURL` variable must be set to your Dynatrace tenant base URL for the
  Distributed Tracing deeplinks in Section 4 (tile: Root queries with child queries) to
  work correctly. The format is `https://<tenant-id>.apps.dynatracelabs.com` or your
  custom domain. The default value is pre-set for the test-qa environment.
- Operator stats in tile 13 are only populated for queries that exceed `slow_queries_threshold`
  (default 100 ms in test-qa). Ensure this threshold is set appropriately for your environment.
- Default timeframe: last 24 hours. Auto-refresh: every 5 minutes.

## Viewing Query Text

The two top-20 query tables (Section 1) include a `query_text` column containing a
representative sample of the SQL for each query hash (via `takeFirst(db.query.text)`).
This column is **hidden by default** to keep the table compact, since query SQL can be
very long.

There are two ways to read it:

**Option 1 — View record details (recommended)**
Right-click any row (or click the `⋮` row menu) and select **View record details**.
A side panel opens showing all fields for that row, including the full `query_text`.
This is the cleanest way to read long SQL without disrupting the table layout.

**Option 2 — Show the column**
Click the column visibility icon (grid icon, top-right of the table tile) and toggle
`query_text` on. The column appears at the far right. You can drag it or resize it.
Note: very long queries will truncate in the cell; use Option 1 for the full text.

![View record details menu showing query_text](img/query-text-record-details.png)

> Add a screenshot to `img/query-text-record-details.png` showing the row context menu
> with "View record details" selected and the side panel displaying `query_text`.

## Screenshots

Screenshots are stored in the `img/` directory.

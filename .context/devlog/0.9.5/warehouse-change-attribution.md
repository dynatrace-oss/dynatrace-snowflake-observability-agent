# [0.9.5] — Warehouse Change Attribution (Experimental) for query_history

## Motivation

Customers asked for structured, queryable attribution for warehouse and resource-monitor changes
(who changed what, when, with which property delta) without parsing `db.query.text` server-side.
Today DSOA already forwards `ALTER_WAREHOUSE` / `CREATE_WAREHOUSE` / `DROP_WAREHOUSE` rows from
`SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` with actor, role, query id, and raw SQL — but the structured
payload Snowflake records in `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` (object domain, id, name,
operation, property delta) was discarded.

## Phase B — Plugin changes

- **`051_v_query_history.sql`** — `cte_access_history` extended with five new aggregated columns
  (`ddl_target_domain`, `ddl_target_id`, `ddl_target_name`, `ddl_operation`, `ddl_properties`)
  pulled from `ah.object_modified_by_ddl`. Each column is wrapped in
  `CASE WHEN CONFIG.F_GET_CONFIG_VALUE('plugins.query_history.track_ddl_changes', FALSE) THEN … END`
  so the feature is fully off (all NULL) by default. Uses `any_value()` to coerce the per-row payload
  through the `group by all` aggregation. The columns are projected into the main `V_QUERY_HISTORY`
  SELECT and consumed by `080_v_query_history_instrumented.sql`.

- **AH-lag handling** — `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` is populated by Snowflake up to
  ~3 hours after the DDL statement. For database-object DDL, the original hold-back strategy was
  implemented: when `track_ddl_changes=true`, rows where `ah.ddl_operation IS NULL` are filtered
  out until AH catches up, ensuring a single enriched event. `cache_ttl_hours` default is 4 h,
  comfortably above the 3 h AH lag.
  **[QA 2026-05-25 correction]:** Warehouse and resource-monitor DDL types were initially included
  in the hold-back filter, but this caused those rows to be suppressed indefinitely — Snowflake
  never populates `OBJECT_MODIFIED_BY_DDL` for warehouse-level DDL. The hold-back was removed for
  warehouse/resource-monitor query types; those rows now emit without DDL attributes (all five
  `snowflake.object.*` attributes NULL). See QA Finding section and
  `.context/devlog/0.9.5/warehouse-ddl-limitation.md`.

- **Top-N signal-protection exemption** — when `max_entries > 0`, the existing `QUALIFY`
  clause prunes by `execution_time DESC`. Warehouse DDL is sub-second and would be pruned out
  of high-volume accounts. Extended the `QUALIFY` to short-circuit `TRUE` when
  `track_ddl_changes=true AND ah.ddl_operation IS NOT NULL`, so DDL events are always preserved.

- **`080_v_query_history_instrumented.sql`** — five new keys added to the `ATTRIBUTES`
  `OBJECT_CONSTRUCT` immediately before the operator-stats placeholders:
  `snowflake.object.type`, `snowflake.object.id`, `snowflake.object.name`,
  `snowflake.object.ddl.operation`, `snowflake.object.ddl.properties`. Attribute names align
  exactly with those already emitted by the `data_schemas` plugin (sources of truth:
  `data_schemas.sql/051_v_data_schemas.sql:87-92`), so downstream consumers (dashboards, workflows,
  DQL) can filter uniformly across plugins without conditional logic.

- **`110_update_processed_queries.sql`** — unchanged. The view-level holdback at point of read
  means rows pending AH catchup never enter the `query_ids` list passed to this procedure.
  Cache lifecycle is therefore unmodified.

## Phase C — Dynatrace artifacts

- **`package/dashboards/Warehouse Change Detection.json`** — new dashboard with tiles covering
  the change timeline (Shape A: `db.operation.name` regex on `db.query.text`), the structured
  change table (Shape B: filter on `isNotNull(snowflake.object.ddl.operation)`), and a
  sensitive-property drift tile filtering `snowflake.object.ddl.properties` for high-impact keys
  (`WAREHOUSE_SIZE`, `SCALING_POLICY`, `RESOURCE_MONITOR`, `AUTO_SUSPEND`, `MIN_CLUSTER_COUNT`,
  `MAX_CLUSTER_COUNT`).

- **`docs/workflows/warehouse-sensitive-change-alert/`** — new workflow that detects warehouse DDL
  via `db.operation.name` filtering (`ALTER_WAREHOUSE`, `CREATE_WAREHOUSE`, `DROP_WAREHOUSE`,
  `ALTER_RESOURCE_MONITOR`) and scans `db.query.text` for sensitive property keywords
  (`WAREHOUSE_SIZE`, `SCALING_POLICY`, `RESOURCE_MONITOR`, `AUTO_SUSPEND`, `MIN_CLUSTER_COUNT`,
  `MAX_CLUSTER_COUNT`). Raises a Davis event per sensitive change.
  **[QA 2026-05-25 correction]:** Initial design filtered on `snowflake.object.ddl.operation` /
  `snowflake.object.type` — this was incorrect since warehouse DDL never populates
  `OBJECT_MODIFIED_BY_DDL`. Corrected before release to use `db.operation.name` + `db.query.text`.
  See QA Finding section.

## Configuration

- New config key `plugins.query_history.track_ddl_changes` (bool, default `false`). Marked
  EXPERIMENTAL in the plugin readme. Added to `query_history-config.yml`, `conf/config-template.yml`,
  and `instruments-def.yml`.

## Testing

- New mock fixture `test/test_data/query_history_ddl.ndjson` with 4 DDL rows
  (CREATE/ALTER/DROP `WAREHOUSE`, ALTER `Resource Monitor`) carrying the five
  `snowflake.object.*` attributes inline in the `ATTRIBUTES` JSON.

- New test class `TestQueryHistDdl` in `test/plugins/test_query_history.py` asserting the
  plugin emits one log / span per DDL row through the standard pipeline. The mock harness
  replays already-instrumented view rows and therefore validates only the OTel-export contract;
  the SQL view changes (CTE join, QUALIFY exemption, AH-lag holdback) are exercised via live
  Customer-Zero testing.

## Open items deferred to live QA

- `ALTER RESOURCE MONITOR` coverage in `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` — needs live
  validation; mock fixture asserts shape only.
- `ALTER WAREHOUSE SUSPEND` / `RESUME` are session operations and are not expected to populate
  `OBJECT_MODIFIED_BY_DDL`; consumers should fall back to `db.operation.name` for those.
- Customer Zero will run the nine-statement DDL test plan documented in
  `.context/proposals/0.9.5/` and confirm the dashboard tiles render with live data.

## QA Finding — 2026-05-25 (ses_ant3b)

**`ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` does NOT capture warehouse-level DDL.**

Confirmed during live QA: `ALTER WAREHOUSE` and `CREATE WAREHOUSE` do not populate
`OBJECT_MODIFIED_BY_DDL`. Only database-object DDL (tables, views, procedures, etc.) appears
there. The hold-back logic in `V_QUERY_HISTORY` (which waited for `ddl_operation IS NOT NULL`
for warehouse DDL types) was suppressing those rows indefinitely.

**Fix applied (branch: fix/0.9.5/warehouse-ddl-finding):**

- Removed the hold-back filter for warehouse/resource-monitor DDL types from
  `051_v_query_history.sql`. These rows are now emitted without DDL attributes.
- Updated `warehouse-sensitive-change-alert` workflow to use `db.operation.name` +
  `db.query.text` keyword scanning instead of `snowflake.object.ddl.operation`.
- See `.context/devlog/0.9.5/warehouse-ddl-limitation.md` for full analysis.

## Future work

If customer adoption shows the feature is high-signal, factor it into a dedicated plugin
(`warehouse_change` / `ddl_audit`) so it can own its own schedule, cache, and metrics independent
of `query_history`.

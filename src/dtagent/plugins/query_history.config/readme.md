This plugin provides information on what SQL queries were run, by whom, when, and their performance. This information is extracted from the `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` view, combined with details such as related objects or estimated costs from `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY`. For the slowest queries, additional information is retrieved from the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

By default, this plugin executes every 30 minutes and analyzes queries that finished within the last 2 hours and have not already been processed.

Among the information it provides are:

- the IDs of processed queries,
- runtimes of processed queries,
- numbers of credits used by processed queries,
- number of bytes scanned during the completion of a query, and
- number of partitions scanned during the completion of a query.

Each query execution is reported as a log line and span, with a hierarchy of spans made from the relation to parent queries. If the query profile was retrieved with `QUERY_OPERATOR_STATS`, it is delivered as span events and additional log lines. This plugin also delivers many metrics based on telemetry information provided by Snowflake.

## Signal Protection Framework

On high-volume Snowflake accounts, the plugin supports signal protection to prevent overload and timeout issues. Three complementary mechanisms are available:

1. **Top-N Limiting** — Set `max_entries` to cap the number of queries processed per run. Queries are prioritized by `max_entries_sort` (default: execution time, descending) so the most expensive queries are always captured. When the cap is hit, a self-monitoring warning log and bizevent are emitted with the count of dropped rows.

2. **Include/Exclude Filters** — Use `include_warehouses`, `exclude_warehouses`, `include_databases`, `exclude_databases`, `include_users`, and `exclude_users` to filter queries at the SQL view level, reducing Snowflake compute cost. Exclude filters always take precedence over include filters.

3. **Watermark-Based Lookback** — The plugin uses the last-processed timestamp from `STATUS.LOG_PROCESSED_MEASUREMENTS` to avoid reprocessing queries. The `max_lookback_minutes` parameter caps the maximum catch-up window (default: 120 minutes), ensuring the plugin catches up incrementally if the agent was down for an extended period.

All defaults preserve backward compatibility: `max_entries=0` (unlimited), `max_lookback_minutes=120`, and `exclude_warehouses=DTAGENT_WH` (exclude the agent's own warehouse only).

**Note:** To correlate query spans with Snowflake's Snowtrail trace_id and span_id, the `event_log` plugin must be enabled. When enabled, this plugin will automatically extract trace context from the `STATUS.EVENT_LOG` table and include it in the span telemetry, allowing for distributed tracing correlation between your application and Snowflake queries.

## Query Text Obfuscation

The plugin can obfuscate query text before it is sent to Dynatrace, reducing the risk of accidentally exposing credentials, tokens, or PII. Obfuscation is controlled by the `obfuscation_mode` configuration key and applied to both the `db.query.text` attribute on spans and the `snowflake.error.message` attribute on failed queries.

Three modes are available:

- **`off`** (default) — query text is sent to Dynatrace unchanged. Preserves full diagnostic visibility.
- **`literals`** — single-quoted string literals and standalone numeric literals are replaced with `?` placeholders. SQL structure, keywords, table names, and column names are preserved. Best-effort: may not handle all edge cases (e.g. dollar-quoted strings, escaped quotes). Not a security boundary — use `full` for strict privacy requirements.
- **`full`** — the entire text is replaced with `[OBFUSCATED]`. No query content reaches Dynatrace. Error type and line/position info in `snowflake.error.message` are also lost.

### Query syntax error redaction

During init (`--scope=init` or `--scope=all`), DSOA sets:

```sql
ALTER ACCOUNT SET ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE;
```

This Snowflake account parameter controls whether the full query text appears in error messages for queries that fail due to syntax or parsing errors. DSOA enables it so that failed queries can be diagnosed via `snowflake.error.message` on spans and logs. The `obfuscation_mode` setting is applied to `snowflake.error.message` as well, so choosing `literals` or `full` will also obfuscate this field.

To disable unredacted syntax errors:

- **Before first deploy:** remove the `ALTER ACCOUNT SET ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = TRUE;` line from `009_query_history_init.sql` before running deploy with `--scope=init`.
- **After deploy:** run `ALTER ACCOUNT SET ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR = FALSE;` as `ACCOUNTADMIN`.

DSOA only applies this parameter when the init script runs. Deploys that exclude `--scope=init` (e.g. `--scope=plugins,config`) will not re-apply it.

## Query Cost Attribution (`query_cost_attribution` context)

The `query_cost_attribution` context adds per-query compute credit attribution sourced from `SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY` (QAH). When enabled, it:

1. Adds `snowflake.credits.attributed_compute` and `snowflake.credits.query_acceleration` metrics to every query span where QAH data is available.
2. Emits aggregated cost summary metrics grouped by warehouse, user, and query tag via `APP.V_QUERY_COST_ATTRIBUTION_SUMMARY`.

### 8-hour latency caveat

QAH has an ~8-hour latency versus QUERY_HISTORY's ~45-minute latency. For queries processed within the first 8 hours, cost fields will be NULL and no credit metrics are emitted for those spans. There is no backfill pass — once a query ID is in `PROCESSED_QUERIES_CACHE`, it will not be re-processed to pick up cost data later.

### Enabling the context

This context is **disabled by default**. To enable, set `enabled: true` in the plugin configuration:

```yaml
plugins:
  query_history:
    query_cost_attribution:
      enabled: true           # required to activate; disabled by default due to 8h QAH latency
      summary_window_hours: 24  # lookback window for the aggregated cost summary
```

### Privilege requirements

Access to `QUERY_ATTRIBUTION_HISTORY` requires the `USAGE_VIEWER` or `GOVERNANCE_VIEWER` database role on the `SNOWFLAKE` database. Grant it to the DTAGENT agent role:

```sql
GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE DTAGENT_VIEWER;
```

If the required privilege is missing, the plugin logs a warning and skips the `query_cost_attribution` context without affecting the main `query_history` context.

### Example DQL queries

Top 10 costliest queries by compute credits this week:

```dql
fetch spans
| filter isNotNull(snowflake.credits.attributed_compute)
| sort snowflake.credits.attributed_compute desc
| limit 10
```

Compute cost trend by warehouse (last 7 days):

```dql
timeseries snowflake.credits.attributed_compute, by: { snowflake.warehouse.name }
| timeframe: now()-7d to now()
```

Cost breakdown by query tag:

```dql
fetch logs
| filter dsoa.run.context == "query_cost_attribution"
| summarize total_credits = sum(snowflake.credits.attributed_compute), by: { snowflake.query.tag }
| sort total_credits desc
```

## DDL Change Attribution (Experimental)

When the `track_ddl_changes` configuration flag is enabled, the plugin extracts the
structured DDL payload Snowflake records in `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` and
surfaces it as five additional attributes on the corresponding `query_history` event:

- `snowflake.object.type` — `objectDomain` (e.g. `Warehouse`, `Resource Monitor`)
- `snowflake.object.id` — Snowflake-internal object identifier
- `snowflake.object.name` — fully qualified object name
- `snowflake.object.ddl.operation` — `CREATE` / `ALTER` / `DROP` / `UNDROP` / `REPLACE`
- `snowflake.object.ddl.properties` — JSON delta of changed properties

Enable it with:

```sql
CALL CONFIG.SET_CONFIG('plugins.query_history.track_ddl_changes', true);
```

Use this when you need structured, queryable warehouse / resource-monitor change
attribution in Dynatrace (who changed what, when, what was the delta) without parsing
`db.query.text` server-side. Compatible Dynatrace artifacts ship in
`package/dashboards/Warehouse Change Detection.json` and
`docs/workflows/warehouse-sensitive-change-alert/`.

### Caveats

- **Experimental.** The flag is off by default; the feature may be refactored into a
  dedicated plugin in a future release.
- **AH lag.** `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` is populated by Snowflake up to
  ~3 hours after the original DDL statement. When the flag is on, the plugin holds back
  warehouse and resource-monitor DDL rows from the standard pipeline until that catchup
  occurs and emits a single enriched event. This means warehouse/resource-monitor change
  alerts in Dynatrace can lag the actual change by up to ~3 hours. The default
  `cache_ttl_hours: 4` is sufficient to cover this window — do not lower it below 3 when
  using `track_ddl_changes`.
- **Coverage.** `ALTER WAREHOUSE … SUSPEND` and `ALTER WAREHOUSE … RESUME` are treated
  by Snowflake as session operations rather than DDL and may not populate
  `OBJECT_MODIFIED_BY_DDL`; consumers that need those signals should fall back to the
  raw `db.operation.name` attribute on `query_history` events.
- **Naming overlap.** The five attribute names match those already emitted by the
  `data_schemas` plugin for table / schema / database DDL — the namespaces deliberately
  align so downstream filters work uniformly across plugins.

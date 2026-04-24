# Plugins

- [Core Objects](#core_bom_sec)
- [Active Queries](#active_queries_info_sec)
- [Budgets](#budgets_info_sec)
- [Cold Tables](#cold_tables_info_sec)
- [Data Schemas](#data_schemas_info_sec)
- [Data Volume](#data_volume_info_sec)
- [Dynamic Tables](#dynamic_tables_info_sec)
- [Event Log](#event_log_info_sec)
- [Event Usage](#event_usage_info_sec)
- [Login History](#login_history_info_sec)
- [Metering](#metering_info_sec)
- [Org Costs](#org_costs_info_sec)
- [Query History](#query_history_info_sec)
- [Resource Monitors](#resource_monitors_info_sec)
- [Shares](#shares_info_sec)
- [Snowpipes](#snowpipes_info_sec)
- [Tasks](#tasks_info_sec)
- [Trust Center](#trust_center_info_sec)
- [Users](#users_info_sec)
- [Warehouse Usage](#warehouse_usage_info_sec)<a name="core_bom_sec"></a>

## Core Snowflake Objects

The Dynatrace Snowflake Observability Agent creates and uses the following Snowflake objects.

### Objects delivered by the agent

| Name                                                              | Type                        | Language | Comment                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------------------- | --------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DTAGENT_DB                                                        | database                    |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_OWNER                                                     | role                        |          | role that owns all SnowAgent artifacts (database, schemas, tables, procedures, tasks)                                                                                                                                                                                         |
| DTAGENT_ADMIN                                                     | role                        |          | (Optional - created only when admin scope is installed and core.snowflake.roles.admin is not set to "-") Role that handles elevated administrative operations (role grants, ownership transfers, privilege management). When disabled, admin deployment scope cannot be used. |
| DTAGENT_VIEWER                                                    | role                        |          | role that executes regular telemetry collection and processing operations                                                                                                                                                                                                     |
| DTAGENT_WH                                                        | warehouse                   |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_RS                                                        | resource monitor            |          | (Optional - created only when core.snowflake.resource_monitor.name is not set to "-") Resource monitor for controlling credit consumption. When disabled, no resource monitoring will be applied to the warehouse.                                                            |
| DTAGENT_API_INTEGRATION                                           | external access integration |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.PUBLIC                                                 | schema                      |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG                                                 | schema                      |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.CONFIGURATIONS                                  | table                       |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.DTAGENT_API_KEY                                 | secret                      |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE                            | network rule                |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS()                    | procedure                   |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.UPDATE_ALL_PLUGINS_SCHEDULE()                   | procedure                   |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE(varchar,array)           | procedure                   |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.P_UPDATE_RESOURCE_MONITOR(int)                  | procedure                   |          | Optional (controlled by core.snowflake.resource_monitor.name). Only created when resource monitor is enabled                                                                                                                                                                  |
| DTAGENT_DB.STATUS                                                 | schema                      |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG                      | table                       |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS(text,text,text,text) | function                    |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.APP                                                    | schema                      |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE(text,variant)                | function                    |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS(text)                       | function                    |          |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.APP.SEND_TELEMETRY(variant,object)                     | procedure                   | python   |                                                                                                                                                                                                                                                                               |
| DTAGENT_DB.APP.DTAGENT(array)                                     | procedure                   | python   |                                                                                                                                                                                                                                                                               |

### Objects referenced by the agent

| Name                        | Type             | Privileges                                    | Granted to     | Comment                                                                                                                                                                                            |
| --------------------------- | ---------------- | --------------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SNOWFLAKE                   | application      | IMPORTED PRIVILEGES ON DATABASE               | DTAGENT_VIEWER |                                                                                                                                                                                                    |
| ACCOUNT                     | account          | MONITOR, MONITOR USAGE, MONITOR EXECUTION     | DTAGENT_VIEWER |                                                                                                                                                                                                    |
| ACCOUNT                     | account          | MODIFY SESSION LOG LEVEL                      | DTAGENT_VIEWER |                                                                                                                                                                                                    |
| ACCOUNT                     | account          | MANAGE GRANTS, EXECUTE TASK                   | DTAGENT_ADMIN  | Optional (controlled by core.snowflake.roles.admin). Only granted when admin role is enabled                                                                                                       |
| ACCOUNT                     | account          | EXECUTE TASK                                  | DTAGENT_VIEWER |                                                                                                                                                                                                    |
| DATABASE DTAGENT_DB         | database         | OPERATE on all TASKS, OPERATE on future TASKS | DTAGENT_VIEWER |                                                                                                                                                                                                    |
| RESOURCE MONITOR DTAGENT_RS | resource monitor | MODIFY, OWNERSHIP                             | DTAGENT_OWNER  | Optional (controlled by core.snowflake.resource_monitor.name). Only granted when resource monitor is enabled. Required for dynamic credit quota updates via P_UPDATE_RESOURCE_MONITOR() procedure. |

<a name="active_queries_info_sec"></a>

## The Active Queries plugin

This plugin lists currently running queries and tracks the status of queries that have finished since the last check. It reports finding
from `INFORMATION_SCHEMA.QUERY_HISTORY()` function.

Provides details on compilation and running (until now) time of the currently running query or recently finished ones.

By default information on all queries is reported as logs and metrics.

Active queries can be reported in two different modes:

- Fast mode - only reports currently active queries. Chosen with `PLUGINS.ACTIVE_QUERIES.FAST_MODE` set to `true`.
- Normal mode - reports queries with start timestamp up to 15 minutes from the current time. Chosen with `PLUGINS.ACTIVE_QUERIES.FAST_MODE`
  set to `false`.

Additionally, you can decide to monitor details for queries only with selected execution status, by using the
`PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` configuration parameter; by default: no additional filters are applied with
`PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` set to empty (`[]`). Multiple statuses can be chosen (for example:
`["RUNNING", "QUEUED"]`). This filtering will be applied on top of the chosen mode.

> **HINT:** Please note that Snowflake's `INFORMATION_SCHEMA.QUERY_HISTORY()` function can return up to 10000 most recent queries.
> Therefore, if you decide to monitor queries other than just those currently `RUNNING` or being `QUEUED`, on a heavily loaded Snowflake
> account, there might be more than 10000 queries reported within the default 10-min interval between executing the `active_queries` plugin.
> Hence, if you see that the following query returns 10000 at any point, you may want to adjust the schedule of the `active_queries` plugin
> to avoid data loss.

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "active_queries"
| filter deployment.environment == "YOUR_ENV"
| sort timestamp asc
| summarize {
  timestamp = takeFirst(timestamp),
  start = takeFirst(timestamp),
  end = takeLast(timestamp),
  timeframe = timeframe(from: takeFirst(timestamp), to:takeLast(timestamp)),
  count = count()
}, by: {
  dsoa.run.id
}
```

If you have any concerns about getting correct results reported by this plugin, please refer to
[Root Cause Analysis: Missing Long-Running Queries](docs/debug/active-queries-faq/readme.md).

[Show semantics for this plugin](SEMANTICS.md#active_queries_semantics_sec)

### Active Queries default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  active_queries:
    schedule: USING CRON */6 * * * * UTC
    is_disabled: false
    fast_mode: true
    report_execution_status: []
    telemetry:
      - logs
      - metrics
      - spans
      - biz_events
```

> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be
> granted `MONITOR` privileges on all warehouses. By default, when the `admin` scope is installed, this is ensured through the periodic
> execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task. The schedule for
> this special task can be configured using the `PLUGINS.QUERY_HISTORY.SCHEDULE_GRANTS` configuration option. Since this procedure runs with
> the elevated privileges of the `DTAGENT_ADMIN` role (which is only created when the `admin` scope is installed), you may choose to:

### Active Queries Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Active Queries` plugin

| Name                                           | Type      |
| ---------------------------------------------- | --------- |
| DTAGENT_DB.APP.F_GET_FINISHED_QUERIES()        | procedure |
| DTAGENT_DB.APP.F_GET_RUNNING_QUERIES()         | procedure |
| DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES     | task      |
| DTAGENT_DB.CONFIG.UPDATE_ACTIVE_QUERIES_CONF() | procedure |

#### Objects referenced by the `Active Queries` plugin

| Name                             | Type     | Privileges |
| -------------------------------- | -------- | ---------- |
| INFORMATION_SCHEMA.QUERY_HISTORY | function | USAGE      |

<a name="budgets_info_sec"></a>

## The Budgets plugin

This plugin enables monitoring of Snowflake budgets, resources linked to them, and their expenditures. It sets up and manages the Dynatrace
Snowflake Observability Agent's own budget.

All budgets the agent has been granted access to are reported as logs and metrics; this includes their details, spending limit, and recent
expenditures. The plugin runs once a day and excludes already reported expenditures.

> **Note**: This plugin is **disabled by default** because custom budget monitoring requires per-budget privilege grants. The account budget
> (visible via `SNOWFLAKE.BUDGET_VIEWER`) is accessible automatically once enabled. For custom budgets, use `P_GRANT_BUDGET_MONITORING()`
> (requires admin scope) or grant privileges manually — see below.

[Show semantics for this plugin](SEMANTICS.md#budgets_semantics_sec)

### Budgets default configuration

This plugin is **disabled by default**; you need to explicitly set `IS_ENABLED` to `true` to enable it.

```yaml
plugins:
  budgets:
    is_disabled: true
    quota: 10
    schedule: USING CRON 30 0 * * * UTC
    monitored_budgets: []
    schedule_grants: USING CRON 30 */12 * * * UTC
    telemetry:
      - logs
      - metrics
      - events
      - biz_events
```

| Parameter           | Type   | Default                        | Description                                                                                                                                                                                                                |
| ------------------- | ------ | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quota`             | int    | `10`                           | Credit quota for the agent's own `DTAGENT_BUDGET`.                                                                                                                                                                         |
| `schedule`          | string | `USING CRON 30 0 * * * UTC`    | Cron schedule for the budgets collection task.                                                                                                                                                                             |
| `monitored_budgets` | list   | `[]`                           | Fully-qualified custom budget names to monitor, e.g. `["MY_DB.MY_SCHEMA.MY_BUDGET"]`. Names are automatically uppercased; only standard unquoted Snowflake identifiers are supported (`[A-Za-z_][A-Za-z0-9_$]*` per part). |
| `schedule_grants`   | string | `USING CRON 30 */12 * * * UTC` | Cron schedule for `TASK_DTAGENT_BUDGETS_GRANTS` (admin scope only).                                                                                                                                                        |

### Enabling the Budgets plugin

1. Set `is_enabled` to `true` in your configuration file.
1. For **account budget only** (no custom budgets): no additional grants needed — `SNOWFLAKE.BUDGET_VIEWER` is already granted.
1. For **custom budgets**: configure `monitored_budgets` and run `P_GRANT_BUDGET_MONITORING()` (admin scope required), or grant privileges
   manually (see below).

### Granting access to custom budgets manually

For each custom budget `<DB>.<SCHEMA>.<BUDGET_NAME>`, grant the following to `DTAGENT_VIEWER`:

```sql
grant usage on database <DB> to role DTAGENT_VIEWER;
grant usage on schema <DB>.<SCHEMA> to role DTAGENT_VIEWER;
grant snowflake.core.budget role <DB>.<SCHEMA>.<BUDGET_NAME>!VIEWER to role DTAGENT_VIEWER;
```

### Budgets Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Budgets` plugin

| Name                                       | Type                  | Comment                                                                                   |
| ------------------------------------------ | --------------------- | ----------------------------------------------------------------------------------------- |
| ACCOUNT_BUDGET_ADMIN                       | role                  |                                                                                           |
| ACCOUNT_BUDGET_MONITOR                     | role                  |                                                                                           |
| BUDGET_OWNER                               | role                  |                                                                                           |
| DTAGENT_DB.APP.DTAGENT_BUDGET              | snowflake.core.budget |                                                                                           |
| DTAGENT_DB.APP.TMP_BUDGETS                 | transient table       |                                                                                           |
| DTAGENT_DB.APP.TMP_BUDGETS_LIMITS          | transient table       |                                                                                           |
| DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES       | transient table       |                                                                                           |
| DTAGENT_DB.APP.TMP_BUDGET_SPENDING         | transient table       |                                                                                           |
| DTAGENT_DB.APP.P_GET_BUDGETS()             | procedure             |                                                                                           |
| DTAGENT_DB.APP.V_BUDGET_SPENDINGS          | view                  |                                                                                           |
| DTAGENT_DB.APP.V_BUDGET_DETAILS            | view                  |                                                                                           |
| DTAGENT_DB.CONFIG.UPDATE_BUDGETS_CONF()    | procedure             |                                                                                           |
| DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS        | task                  |                                                                                           |
| DTAGENT_DB.APP.P_GRANT_BUDGET_MONITORING() | procedure             | Optional (admin scope). Grants DTAGENT_VIEWER privileges on configured monitored_budgets. |
| DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS | task                  | Optional (admin scope). Periodically calls P_GRANT_BUDGET_MONITORING().                   |

#### Objects referenced by the `Budgets` plugin

| Name                           | Type        | Privileges                      | Granted to             | Comment                                                                                                |
| ------------------------------ | ----------- | ------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------ |
| SNOWFLAKE                      | application | IMPORTED PRIVILEGES ON DATABASE | ACCOUNT_BUDGET_ADMIN   |                                                                                                        |
| SNOWFLAKE.BUDGET_ADMIN         | role        | APPLICATION ROLE                | ACCOUNT_BUDGET_ADMIN   |                                                                                                        |
| SNOWFLAKE.BUDGET_VIEWER        | role        | APPLICATION ROLE                | ACCOUNT_BUDGET_MONITOR |                                                                                                        |
| SNOWFLAKE.BUDGET_CREATOR       | role        | DATABASE ROLE                   | BUDGET_OWNER           |                                                                                                        |
| ACCOUNT_BUDGET_ADMIN           | role        | ROLE                            | DTAGENT_ADMIN          |                                                                                                        |
| ACCOUNT_BUDGET_MONITOR         | role        | ROLE                            | DTAGENT_VIEWER         |                                                                                                        |
| BUDGET_OWNER                   | role        | ROLE                            | DTAGENT_ADMIN          |                                                                                                        |
| SYSTEM$SHOW_BUDGETS_IN_ACCOUNT | function    | USAGE                           |                        | Called in P_GET_BUDGETS() via PARSE_JSON(SYSTEM$SHOW_BUDGETS_IN_ACCOUNT()); requires BUDGET_ADMIN role |
| SNOWFLAKE.CORE.BUDGET          | command     | USAGE                           |                        |                                                                                                        |
| $budget!GET_LINKED_RESOURCES   | procedure   | USAGE                           |                        | We call this procedure on each budget defined in Snowflake                                             |
| $budget!GET_SPENDING_LIMIT     | procedure   | USAGE                           |                        | We call this procedure on each budget defined in Snowflake                                             |
| $budget!GET_SPENDING_HISTORY   | procedure   | USAGE                           |                        | We call this procedure on each budget defined in Snowflake                                             |
| SNOWFLAKE.USAGE_VIEWER         | role        | DATABASE ROLE                   | DTAGENT_VIEWER         | Optional (admin scope). Required for custom budget monitoring via P_GRANT_BUDGET_MONITORING().         |

<a name="cold_tables_info_sec"></a>

## The Cold Tables plugin

This plugin enables identification of "cold" tables — tables that have not been accessed by queries for a configurable period (default: 90
days). It helps FinOps teams and Snowflake administrators identify candidates for archiving, dropping, or tiering to lower-cost storage.

The following information is reported:

- table access frequency (total count within lookback window),
- timestamp of the most recent query that accessed the table,
- number of days since last access,
- cold/warm classification based on access recency.

## Configuration

Default schedule: daily at 6 AM UTC (access patterns don't change hourly).

Configurable parameters:

- `lookback_days` (default: 365) — number of days to look back in ACCESS_HISTORY
- `cold_threshold_days` (default: 90) — tables with no access in this many days are flagged as "cold"

Example configuration:

```yaml
plugins:
  cold_tables:
    schedule: USING CRON 0 6 * * * UTC
    lookback_days: 365
    cold_threshold_days: 90
    is_disabled: false
    telemetry:
      - metrics
      - logs
```

## Known Limitations

- **Never-accessed tables not included:** ACCESS_HISTORY only contains tables that have been accessed. Tables that have never been accessed
  will not appear in the results. To identify truly never-accessed tables, a follow-up enhancement would join with
  `INFORMATION_SCHEMA.TABLES` or `ACCOUNT_USAGE.TABLES`.
- **ACCESS_HISTORY latency:** Up to 2 hours. Daily schedule is appropriate for this latency.

## Querying in Dynatrace

### Logs — per-table detail

```dql
fetch logs
| filter db.system == "snowflake" and dsoa.run.plugin == "cold_tables"
| filter snowflake.table.cold_status == "cold"
| sort timestamp desc
| limit 50
```

### Metrics — access count by table

```dql
timeseries avg(snowflake.table.access.count),
  by: {db.namespace, db.collection.name, snowflake.table.cold_status}
| filter db.system == "snowflake"
```

### Metrics — days since last access

```dql
timeseries avg(snowflake.table.days_since_last_access),
  by: {db.namespace, db.collection.name}
| filter db.system == "snowflake"
| filter snowflake.table.days_since_last_access > 90
```

### Self-monitoring — plugin performance

```dql
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "cold_tables"
| fields timestamp, dsoa.run.id, cold_tables.entries, cold_tables.log_lines, cold_tables.metrics
| sort timestamp desc
```

[Show semantics for this plugin](SEMANTICS.md#cold_tables_semantics_sec)

### Cold Tables default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  cold_tables:
    schedule: USING CRON 0 6 * * * UTC
    lookback_days: 365
    cold_threshold_days: 90
    is_disabled: false
    telemetry:
      - metrics
      - logs
```

| Key                                       | Type   | Default                    | Description                                                                       |
| ----------------------------------------- | ------ | -------------------------- | --------------------------------------------------------------------------------- |
| `plugins.cold_tables.lookback_days`       | int    | `365`                      | How far back (in days) the plugin scans `ACCESS_HISTORY` to count table accesses. |
| `plugins.cold_tables.cold_threshold_days` | int    | `90`                       | Tables not accessed within this many days are classified as `cold`.               |
| `plugins.cold_tables.schedule`            | string | `USING CRON 0 6 * * * UTC` | Cron schedule for the cold tables collection task.                                |
| `plugins.cold_tables.is_disabled`         | bool   | `false`                    | Set to `true` to disable this plugin entirely.                                    |
| `plugins.cold_tables.telemetry`           | list   | `["metrics", "logs"]`      | Telemetry types to emit. Remove items to suppress specific output types.          |

### Cold Tables Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Cold Tables` plugin

| Name                                        | Type      |
| ------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_COLD_TABLES                | view      |
| DTAGENT_DB.CONFIG.UPDATE_COLD_TABLES_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_COLD_TABLES     | task      |

#### Objects referenced by the `Cold Tables` plugin

| Name                                   | Type | Privileges |
| -------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY | view | SELECT     |

<a name="data_schemas_info_sec"></a>

## The Data Schemas plugin

Enables monitoring of data schema changes. Reports events on recent modifications to objects (tables, schemas, databases) made by DDL
queries, within a configurable lookback window (default: 4 hours, see `plugins.data_schemas.lookback_hours`).

[Show semantics for this plugin](SEMANTICS.md#data_schemas_semantics_sec)

### Data Schemas default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  data_schemas:
    lookback_hours: 4
    schedule: USING CRON 0 0,8,16 * * * UTC
    is_disabled: false
    exclude: []
    include:
      - "%"
    telemetry:
      - events
      - biz_events
```

| Key                                   | Type   | Default                         | Description                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------- | ------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.data_schemas.lookback_hours` | int    | `4`                             | How far back (in hours) the plugin looks for DDL-based schema changes on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Default is `4`h to account for the up-to-3-hour data ingestion delay in `ACCESS_HISTORY`. |
| `plugins.data_schemas.schedule`       | string | `USING CRON 0 0,8,16 * * * UTC` | Cron schedule for the data schemas collection task.                                                                                                                                                                                                                                                                                                                                                                                          |
| `plugins.data_schemas.is_disabled`    | bool   | `false`                         | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                                                               |
| `plugins.data_schemas.include`        | list   | `["%"]`                         | List of object name patterns to include (SQL `LIKE` syntax). Default includes all objects.                                                                                                                                                                                                                                                                                                                                                   |
| `plugins.data_schemas.exclude`        | list   | `[]`                            | List of object name patterns to exclude (SQL `LIKE` syntax). Takes precedence over `include`.                                                                                                                                                                                                                                                                                                                                                |
| `plugins.data_schemas.telemetry`      | list   | `["events", "biz_events"]`      | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                                                                     |

### Data Schemas Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Data Schemas` plugin

| Name                                         | Type      |
| -------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_DATA_SCHEMAS                | view      |
| DTAGENT_DB.CONFIG.UPDATE_DATA_SCHEMAS_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_DATA_SCHEMAS     | task      |

#### Objects referenced by the `Data Schemas` plugin

| Name                                   | Type | Privileges |
| -------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY | view | SELECT     |

<a name="data_volume_info_sec"></a>

## The Data Volume plugin

This plugin enables tracking the volume of data (in bytes and rows) stored in Snowflake through reported metrics. Additionally, it sends
events when there are changes in table structure (DDL) or content.

The following information is reported:

- table type,
- timestamp of the last data update and the time elapsed since then,
- timestamp of the last DDL and the time elapsed since then,
- number of bytes in the table, and
- number of rows in the table.

[Show semantics for this plugin](SEMANTICS.md#data_volume_semantics_sec)

### Data Volume default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  data_volume:
    include:
      - DTAGENT_DB.%.%
      - "%.PUBLIC.%"
    exclude:
      - "%.INFORMATION_SCHEMA.%"
      - "%.%.TMP_%"
    schedule: USING CRON 30 0,4,8,12,16,20 * * * UTC
    is_disabled: false
    telemetry:
      - metrics
      - biz_events
```

### Data Volume Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Data Volume` plugin

| Name                                        | Type      |
| ------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_DATA_VOLUME                | view      |
| DTAGENT_DB.CONFIG.UPDATE_DATA_VOLUME_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_DATA_VOLUME     | task      |

#### Objects referenced by the `Data Volume` plugin

| Name                           | Type | Privileges |
| ------------------------------ | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.TABLES | view | SELECT     |

<a name="dynamic_tables_info_sec"></a>

## The Dynamic Tables plugin

This plugin enables tracking availability and performance of running Snowflake dynamic table refreshes, via logs and a set of metrics.
Additionally, there are events sent when dynamic tables refresh tasks are executed.

The telemetry is based on checking 3 functions:

- `INFORMATION_SCHEMA.DYNAMIC_TABLES()`,
- `INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY()`, and
- `INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY()`.

[Show semantics for this plugin](SEMANTICS.md#dynamic_tables_semantics_sec)

### Dynamic Tables default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  dynamic_tables:
    include:
      - "%.%.%"
    exclude:
      - DTAGENT_DB.%.%
    schedule: USING CRON */30 * * * * UTC
    schedule_grants: USING CRON 30 */12 * * * UTC
    is_disabled: false
    telemetry:
      - metrics
      - logs
      - biz_events
```

> **IMPORTANT**: For this plugin to function correctly, `MONITOR on DYNAMIC TABLES` must be granted to the `DTAGENT_VIEWER` role. By
> default, when the `admin` scope is installed, this is handled by the `P_GRANT_MONITOR_DYNAMIC_TABLES()` procedure, which is executed with
> the elevated privileges of the `DTAGENT_ADMIN` role (created only when the `admin` scope is installed), via the
> `APP.TASK_DTAGENT_DYNAMIC_TABLES_GRANTS` task. The schedule for this task can be configured separately using the
> `PLUGINS.DYNAMIC_TABLES.SCHEDULE_GRANTS` configuration option.

The grant granularity is derived automatically from the `include` pattern:

| Include pattern               | Grant level | SQL issued                                                 |
| ----------------------------- | ----------- | ---------------------------------------------------------- |
| `%.%.%` or `PROD_DB.%.%`      | Database    | `GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN DATABASE …` |
| `PROD_DB.ANALYTICS.%`         | Schema      | `GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN SCHEMA …`   |
| `PROD_DB.ANALYTICS.ORDERS_DT` | Table       | `GRANT MONITOR ON DYNAMIC TABLE …` (no FUTURE grant)       |

Alternatively, you may choose to grant the required permissions manually, using the appropriate
`GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN …` statement, depending on the desired granularity.

### Dynamic Tables Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Dynamic Tables` plugin

| Name                                                        | Type      | Comment                                                                                            |
| ----------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------- |
| DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES()             | procedure |                                                                                                    |
| DTAGENT_DB.APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED   | view      |                                                                                                    |
| DTAGENT_DB.APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED | view      |                                                                                                    |
| DTAGENT_DB.APP.V_DYNAMIC_TABLES_INSTRUMENTED                | view      |                                                                                                    |
| DTAGENT_DB.CONFIG.UPDATE_DYNAMIC_TABLES_CONF()              | procedure |                                                                                                    |
| DTAGENT_DB.APP.TASK_DTAGENT_DYNAMIC_TABLES                  | task      |                                                                                                    |
| DTAGENT_DB.APP.TASK_DTAGENT_DYNAMIC_TABLES_GRANTS           | task      | (Admin scope only) Admin task owned by DTAGENT_ADMIN to grant MONITOR privileges on dynamic tables |

#### Objects referenced by the `Dynamic Tables` plugin

| Name                                                  | Type          | Privileges | Granted to     | Comment                                                                                                                  |
| ----------------------------------------------------- | ------------- | ---------- | -------------- | ------------------------------------------------------------------------------------------------------------------------ |
| SHOW DATABASES                                        | command       | USAGE      |                |                                                                                                                          |
| ALL DYNAMIC TABLES IN DATABASE $database              | dynamic table | MONITOR    | DTAGENT_VIEWER | Granted when include pattern has wildcard schema (e.g. DB.%.%)                                                           |
| ALL FUTURE DYNAMIC TABLES IN DATABASE $database       | dynamic table | MONITOR    | DTAGENT_VIEWER | Granted when include pattern has wildcard schema (e.g. DB.%.%)                                                           |
| ALL DYNAMIC TABLES IN SCHEMA $database.$schema        | dynamic table | MONITOR    | DTAGENT_VIEWER | Granted when include pattern has specific schema (e.g. DB.ANALYTICS.%)                                                   |
| ALL FUTURE DYNAMIC TABLES IN SCHEMA $database.$schema | dynamic table | MONITOR    | DTAGENT_VIEWER | Granted when include pattern has specific schema (e.g. DB.ANALYTICS.%)                                                   |
| DYNAMIC TABLE $database.$schema.$table                | dynamic table | MONITOR    | DTAGENT_VIEWER | Granted when include pattern specifies an exact table name (e.g. DB.ANALYTICS.ORDERS_DT); no FUTURE grant at table level |
| INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY      | function      | USAGE      | DTAGENT_VIEWER |                                                                                                                          |
| INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY        | function      | USAGE      | DTAGENT_VIEWER |                                                                                                                          |
| INFORMATION_SCHEMA.DYNAMIC_TABLES                     | function      | USAGE      | DTAGENT_VIEWER |                                                                                                                          |

<a name="event_log_info_sec"></a>

## The Event Log plugin

This plugin delivers to Dynatrace data reported by Snowflake Trail in the `EVENT TABLE`.

By default, it runs every 30 minutes and processes only new entries since the last run (bounded by a configurable lookback window of 24
hours), omitting entries that:

- were already delivered,
- have scope set to `DTAGENT_OTLP` (internal log recording entries sent over the OpenTelemetry protocol), or
- have importance below `WARN` for any `DTAGENT_*_DB` instance, i.e., only warnings or errors from Dynatrace Snowflake Observability Agent
  instances are reported.

By default, it produces log entries containing the following information:

- timestamp of the entry to Snowflake Trail,
- timestamp the plugin observed the entry,
- content,
- type of record, and
- trace of the entry.

Metric entries (`RECORD_TYPE = 'METRIC'`) are sent via Dynatrace Metrics API v2. Metrics that were identified during development time will
have their semantics included already in the Dynatrace Snowflake Observability Agent semantic dictionary; semantics for any new metric will
be copied from information provided by Snowflake Trail.

Span entries (`RECORD_TYPE = 'SPAN'`) are send via OpenTelemetry Trace API, with trace ID and span ID set as reported by Snowflake Trail.

Unless [OpenTelemetry-compliant attribute names](https://opentelemetry.io/docs/specs/semconv/attributes-registry/), such as `code.function`,
are reported in the event log table, Snowflake prefixes all internal telemetry names with `snow.`. Dynatrace Snowflake Observability Agent
passes all telemetry under the original names provided by Snowflake in the event log table. The only exception is the `SCOPE` column, where
attribute names are short (like `name`) and Dynatrace Snowflake Observability Agent reports them with `snowflake.event.scope.` prefix, e.g.,
`snowflake.event.scope.name`.

[Show semantics for this plugin](SEMANTICS.md#event_log_semantics_sec)

### Event Log default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  event_log:
    max_entries: 10000
    lookback_hours: 24
    retention_hours: 24
    schedule: USING CRON */30 * * * * UTC
    schedule_cleanup: USING CRON 0 * * * * UTC
    is_disabled: false
    cross_tenant_monitoring: true
    databases: []
    telemetry:
      - metrics
      - logs
      - biz_events
      - spans
```

| Key                                  | Type   | Default                                      | Description                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------ | ------ | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.event_log.max_entries`      | int    | `10000`                                      | Maximum number of event log entries fetched per run. Acts as a safety cap to avoid long-running queries.                                                                                                                                                                                                                                                                                        |
| `plugins.event_log.lookback_hours`   | int    | `24`                                         | How far back (in hours) the plugin looks for new events on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Increase for initial setup; decrease to reduce query cost. |
| `plugins.event_log.retention_hours`  | int    | `24`                                         | How long (in hours) the cleanup task retains entries in `STATUS.EVENT_LOG`. Only applies if this agent instance owns the event table.                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule`         | string | `USING CRON */30 * * * * UTC`                | Cron schedule for the main event log processing task.                                                                                                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule_cleanup` | string | `USING CRON 0 * * * * UTC`                   | Cron schedule for the cleanup task that removes old entries from `STATUS.EVENT_LOG`.                                                                                                                                                                                                                                                                                                            |
| `plugins.event_log.is_disabled`      | bool   | `false`                                      | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                  |
| `plugins.event_log.telemetry`        | list   | `["metrics", "logs", "biz_events", "spans"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                        |

### Cost Optimization Guidance

The event log plugin queries `STATUS.EVENT_LOG` on every run. The following settings directly affect compute cost:

- **`lookback_hours`**: This window defines how far back the plugin reads on each run. If no prior processed timestamp is available (first
  run, or after a reset), the plugin starts from `now - lookback_hours`. During normal operation the plugin starts from the more recent of
  the last processed timestamp and `now - lookback_hours`, capping catch-up after long gaps. A large lookback window can cause heavy queries
  after a reset — consider starting with `12` or `24` and increasing only if needed.
- **`max_entries`**: Hard cap on rows processed per run. The default (`10000`) protects against runaway queries. If your Snowflake account
  generates very high event volumes, lower this value and rely on the schedule frequency to catch up incrementally.
- **`retention_hours`**: Shorter retention reduces the size of `STATUS.EVENT_LOG`, which improves scan performance. Set this higher than
  `lookback_hours` to avoid situations where the cleanup removes events before the plugin can process them. The recommended ratio is
  `retention_hours >= lookback_hours`.
- **`schedule`**: Running more frequently (e.g., every 5 minutes) increases credit usage. The default every-30-minutes cadence balances
  freshness against cost. For high-volume accounts, consider running less frequently with higher `max_entries`.

> **IMPORTANT**: A dedicated cleanup task, `APP.TASK_DTAGENT_EVENT_LOG_CLEANUP`, ensures that the `EVENT_LOG` table contains only data no
> older than the duration you define with the `plugins.event_log.retention_hours` configuration option. You can schedule this task
> separately using the `plugins.event_log.schedule_cleanup` configuration option, run the cleanup procedure `APP.P_CLEANUP_EVENT_LOG()`
> manually, or manage the retention of data in the `EVENT_LOG` table yourself.

> **INFO**: The `EVENT_LOG` table cleanup process works only if this specific instance of Dynatrace Snowflake Observability Agent set up the
> table.

### Cross-Tenant Monitoring

By default (`plugins.event_log.cross_tenant_monitoring: true`) the plugin also reports `WARN`/`ERROR` log entries, metrics, and spans
originating from **other** `DTAGENT_*_DB` instances visible in the same event table. This allows one DSOA deployment to surface health
issues from sibling deployments without logging into Snowflake directly.

In case you would like to enable cross-tenant monitoring on **only one DSOA tenant**, e.g., to avoid duplicate reporting across deployments,
you need to set `cross_tenant_monitoring: false` in all other tenants.

```yaml
plugins:
  event_log:
    cross_tenant_monitoring: false # disable on tenants that should report only their own WARN/ERROR self-monitoring entries
```

### Database Filtering

Use `plugins.event_log.databases` to restrict event log monitoring to specific databases. The list accepts SQL `LIKE` patterns (`%` matches
any sequence of characters, `_` matches any single character). When the list is absent or empty, **all databases** are included.

```yaml
plugins:
  event_log:
    databases:
      - MYAPP_DB # exact match
      - ANALYTICS% # all databases starting with ANALYTICS_
```

### Event Log Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Event Log` plugin

| Name                                            | Type       | Comment                                                                                                                                                                                                                                |
| ----------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DTAGENT_DB.STATUS.EVENT_LOG                     | table/view | Dynatrace Snowflake Observability Agent can setup an event table if one does not exist. It creates a view over an existing event log table if that table was not setup by the actual Dynatrace Snowflake Observability Agent instance. |
| DTAGENT_DB.APP.SETUP_EVENT_TABLE()              | procedure  |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG()            | procedure  |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.F_EVENT_LOG_INCLUDE(VARCHAR)     | function   |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.V_EVENT_LOG                      | view       |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.V_EVENT_LOG_SPANS_INSTRUMENTED   | view       |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.V_EVENT_LOG_METRICS_INSTRUMENTED | view       |                                                                                                                                                                                                                                        |
| DTAGENT_DB.CONFIG.UPDATE_EVENT_LOG_CONF()       | procedure  |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG           | task       |                                                                                                                                                                                                                                        |
| DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP   | task       | (Admin scope only) Cleanup task owned by DTAGENT_ADMIN to remove old event log entries                                                                                                                                                 |

#### Objects referenced by the `Event Log` plugin

| Name            | Type    | Privileges               | Granted to     | Comment                                                                                                                                                                                          |
| --------------- | ------- | ------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| SHOW PARAMETERS | command | USAGE                    |                | We call `show PARAMETERS like 'EVENT_TABLE' in ACCOUNT` to determine if event table is already setup, and whether this is a table setup by this Dynatrace Snowflake Observability Agent instance |
| ACCOUNT         | account | MODIFY SESSION LOG LEVEL | DTAGENT_VIEWER |                                                                                                                                                                                                  |
| ACCOUNT         | account | MODIFY LOG EVENT LEVEL   | DTAGENT_VIEWER | Granted only on accounts that support Snowflake BCR Bundle 2026_02+ (LOG_EVENT_LEVEL parameter). On pre-BCR accounts this privilege is not available and the grant is skipped gracefully.        |
| $event_table    | table   | SELECT, DELETE           | DTAGENT_VIEWER | This is in case an event log table was not setup by this Dynatrace Snowflake Observability Agent instance                                                                                        |

<a name="event_usage_info_sec"></a>

## The Event Usage plugin

> **Deprecated:** This plugin is deprecated as of 0.9.5 and will be removed in 0.9.6. Use the [metering](../metering.config/readme.md)
> plugin instead, which covers all Snowflake service types via `METERING_HISTORY`. To reproduce the same data, filter by
> `service_type == "TELEMETRY_DATA_INGEST"`.

This plugin delivers information regarding the history of data loaded into Snowflake event tables. It reports telemetry from the
`EVENT_USAGE_HISTORY` view.

Log entries include:

- timestamps: start and end time of the event,
- bytes ingested during the event (also reported as `snowflake.data.ingested` metric),
- credits consumed during the event (also reported as `snowflake.credits.used` metric).

[Show semantics for this plugin](SEMANTICS.md#event_usage_semantics_sec)

### Event Usage default configuration

This plugin is **disabled by default**; you need to explicitly set `IS_ENABLED` to `true` to enable it.

```yaml
plugins:
  event_usage:
    lookback_hours: 6
    schedule: USING CRON 0 * * * * UTC
    is_disabled: true
    telemetry:
      - metrics
      - logs
      - biz_events
```

| Key                                  | Type   | Default                             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------ | ------ | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.event_usage.lookback_hours` | int    | `6`                                 | How far back (in hours) the plugin looks for event usage history on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Default is `6`h to account for the up-to-3-hour data ingestion delay in `EVENT_USAGE_HISTORY`. |
| `plugins.event_usage.schedule`       | string | `USING CRON 0 * * * * UTC`          | Cron schedule for the event usage collection task.                                                                                                                                                                                                                                                                                                                                                                                           |
| `plugins.event_usage.is_disabled`    | bool   | `false`                             | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                                                               |
| `plugins.event_usage.telemetry`      | list   | `["metrics", "logs", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                                                                     |

### Event Usage Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Event Usage` plugin

| Name                                        | Type      |
| ------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_EVENT_USAGE_HISTORY        | view      |
| DTAGENT_DB.CONFIG.UPDATE_EVENT_USAGE_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_EVENT_USAGE     | task      |

#### Objects referenced by the `Event Usage` plugin

| Name                                        | Type | Privileges |
| ------------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.EVENT_USAGE_HISTORY | view | SELECT     |

<a name="login_history_info_sec"></a>

## The Login History plugin

Provides detail about logins history as well as sessions history in form of logs. The log entries include information on:

- users id who is regarded by the log,
- potential error codes,
- type of Snowflake connection,
- timestamp of logging in,
- environment the client used during the session,
- timestamp of the start of the session,
- timestamp of the end of the session,
- reason of ending the session, and
- version used by the client.

Additionally, when login error is reported, a `CUSTOM_ALERT` event is sent.

[Show semantics for this plugin](SEMANTICS.md#login_history_semantics_sec)

### Login History default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  login_history:
    lookback_hours: 24
    schedule: USING CRON */30 * * * * UTC
    is_disabled: false
    telemetry:
      - logs
      - biz_events
```

| Key                                    | Type   | Default                       | Description                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------- | ------ | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.login_history.lookback_hours` | int    | `24`                          | How far back (in hours) the plugin looks for login and session events on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. |
| `plugins.login_history.schedule`       | string | `USING CRON */30 * * * * UTC` | Cron schedule for the login history collection task.                                                                                                                                                                                                                                                                                               |
| `plugins.login_history.is_disabled`    | bool   | `false`                       | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                     |
| `plugins.login_history.telemetry`      | list   | `["logs", "biz_events"]`      | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                           |

### Login History Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Login History` plugin

| Name                                          | Type      |
| --------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_LOGIN_HISTORY                | view      |
| DTAGENT_DB.APP.V_SESSIONS                     | view      |
| DTAGENT_DB.CONFIG.UPDATE_LOGIN_HISTORY_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_LOGIN_HISTORY     | task      |

#### Objects referenced by the `Login History` plugin

| Name                                  | Type | Privileges |
| ------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.SESSIONS      | view | SELECT     |

<a name="metering_info_sec"></a>

## The Metering plugin

This plugin reports credit consumption across all Snowflake service types using the `METERING_HISTORY` view. It replaces the narrower
`event_usage` plugin which only covered `EVENT_USAGE_HISTORY` (telemetry data ingest).

What data is collected:

- credits consumed (total, compute, and cloud services) per service type and entity,
- bytes, rows, and files processed per service type,
- start and end timestamps for each metering window.

`WAREHOUSE_METERING` rows are excluded to avoid duplication with the `warehouse_usage` plugin.

Key use cases:

- FinOps cost attribution across all Snowflake service types (auto-clustering, pipes, serverless tasks, AI services, replication, etc.),
- trend analysis and anomaly detection on credit consumption,
- capacity planning based on historical metering data.

## The Metering Configuration

| Key                               | Type   | Default                             | Description                                                                                                                                                |
| --------------------------------- | ------ | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.metering.lookback_hours` | int    | `6`                                 | How far back (in hours) the plugin looks for metering history on each run. Default is `6`h to account for up-to-3-hour data latency in `METERING_HISTORY`. |
| `plugins.metering.schedule`       | string | `USING CRON 0 * * * * UTC`          | Cron schedule for the metering collection task.                                                                                                            |
| `plugins.metering.is_disabled`    | bool   | `false`                             | Set to `true` to disable this plugin entirely.                                                                                                             |
| `plugins.metering.telemetry`      | list   | `["metrics", "logs", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                   |

## Querying Metering Data in Dynatrace

```dql
// All metering logs
fetch logs
| filter db.system == "snowflake" and dsoa.run.context == "metering"
| sort timestamp desc | limit 50

// Credits by service type
timeseries sum(snowflake.credits.used), by: {snowflake.service.type}

// Event table ingest only (backward compat with event_usage)
timeseries sum(snowflake.credits.used), by: {snowflake.service.type}
| filter snowflake.service.type == "TELEMETRY_DATA_INGEST"
```

## Migration from event_usage

The `event_usage` plugin is deprecated as of 0.9.5. To migrate:

1. Enable `metering` plugin (enabled by default).
1. Disable `event_usage` plugin (disabled by default as of 0.9.5).
1. Update any DQL queries that filter by `dsoa.run.plugin == "event_usage"` to use `dsoa.run.plugin == "metering"`.
1. To reproduce the exact same data as `event_usage`, add `snowflake.service.type == "TELEMETRY_DATA_INGEST"` filter.

[Show semantics for this plugin](SEMANTICS.md#metering_semantics_sec)

### Metering default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  metering:
    lookback_hours: 6
    schedule: USING CRON 0 * * * * UTC
    is_disabled: false
    telemetry:
      - metrics
      - logs
      - biz_events
```

### Metering Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Metering` plugin

| Name                                     | Type      |
| ---------------------------------------- | --------- |
| DTAGENT_DB.APP.V_METERING_HISTORY        | view      |
| DTAGENT_DB.CONFIG.UPDATE_METERING_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_METERING     | task      |

#### Objects referenced by the `Metering` plugin

| Name                                     | Type | Privileges |
| ---------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY | view | SELECT     |

<a name="org_costs_info_sec"></a>

## The Org Costs plugin

The `org_costs` plugin delivers cross-account FinOps telemetry from `SNOWFLAKE.ORGANIZATION_USAGE` views. It provides organization-wide
credit consumption, storage usage, data transfer costs, USD billing, and contract balance data — enabling multi-account cost visibility in
Dynatrace.

## Prerequisites

Access to `SNOWFLAKE.ORGANIZATION_USAGE` views requires one of the following grants. This plugin is **disabled by default**
(`is_disabled: true`) and must be explicitly enabled after completing the prerequisite step.

### Option A — Database role (recommended)

```sql
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.ORGANIZATION_USAGE_VIEWER TO ROLE DTAGENT_VIEWER;
```

### Option B — ORGADMIN role (legacy fallback for older tenants)

```sql
USE ROLE ACCOUNTADMIN;
GRANT ROLE ORGADMIN TO ROLE DTAGENT_OWNER;
```

## Contexts

| Context                         | Source view                                      | Telemetry     |
| ------------------------------- | ------------------------------------------------ | ------------- |
| `org_costs_metering`            | `ORGANIZATION_USAGE.METERING_DAILY_HISTORY`      | metrics, logs |
| `org_costs_storage`             | `ORGANIZATION_USAGE.STORAGE_DAILY_HISTORY`       | metrics, logs |
| `org_costs_data_transfer`       | `ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY` | metrics, logs |
| `org_billing_usage_in_currency` | `ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY`     | metrics, logs |
| `org_billing_remaining_balance` | `ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY`     | metrics, logs |

## Schedule

Runs every 6 hours (`USING CRON 0 */6 * * * UTC`). Source data has approximately 2 hours of latency; daily-granularity views update once per
day.

## Metrics emitted

### org_costs_metering

| Metric                                            | Unit    | Description                                 |
| ------------------------------------------------- | ------- | ------------------------------------------- |
| `snowflake.org.credits.used`                      | credits | Total credits used by account per day       |
| `snowflake.org.credits.compute`                   | credits | Compute credits used per day                |
| `snowflake.org.credits.cloud_services`            | credits | Cloud services credits used per day         |
| `snowflake.org.credits.adjustment_cloud_services` | credits | Cloud services credit adjustment (10% rule) |

### org_costs_storage

| Metric                        | Unit | Description                                 |
| ----------------------------- | ---- | ------------------------------------------- |
| `snowflake.org.storage.bytes` | Byte | Storage bytes used per storage type per day |

### org_costs_data_transfer

| Metric                         | Unit | Description                                      |
| ------------------------------ | ---- | ------------------------------------------------ |
| `snowflake.org.transfer.bytes` | Byte | Bytes transferred between clouds/regions per day |

### org_billing_usage_in_currency

| Metric                         | Unit     | Description                                         |
| ------------------------------ | -------- | --------------------------------------------------- |
| `snowflake.org.billing.amount` | currency | Billing amount in currency per service type per day |

### org_billing_remaining_balance

| Metric                                        | Unit     | Description                                    |
| --------------------------------------------- | -------- | ---------------------------------------------- |
| `snowflake.org.billing.capacity_balance`      | currency | Remaining contracted capacity balance          |
| `snowflake.org.billing.rollover_balance`      | currency | Remaining rollover balance                     |
| `snowflake.org.billing.free_usage_balance`    | currency | Remaining free usage balance                   |
| `snowflake.org.billing.on_demand_consumption` | currency | On-demand consumption charged against contract |
| `snowflake.org.billing.overage`               | currency | Overage charged beyond contracted capacity     |

## Enablement

1. Complete the prerequisite grant (Option A or B above).
1. Set `plugins.org_costs.is_disabled: false` in your configuration.
1. Deploy: `./scripts/deploy/deploy.sh <env> --scope=plugins,config --options=skip_confirm`

## Troubleshooting

- **No data for a new account:** Organization-level views may not reflect new accounts for up to 24 hours after creation.
- **Empty results:** Verify the prerequisite grant was applied and the plugin is enabled.
- **Stale data:** Daily-granularity views update once per day; data may appear up to 26 hours old (2h Snowflake latency + 6h collection
  cadence + daily boundary).

[Show semantics for this plugin](SEMANTICS.md#org_costs_semantics_sec)

### Org Costs default configuration

This plugin is **disabled by default**; you need to explicitly set `IS_ENABLED` to `true` to enable it.

```yaml
plugins:
  org_costs:
    lookback_hours: 48
    schedule: USING CRON 0 */6 * * * UTC
    is_disabled: true
    telemetry:
      - logs
      - metrics
      - biz_events
    contexts:
      org_costs_metering:
        is_disabled: true
      org_costs_storage:
        is_disabled: true
      org_costs_data_transfer:
        is_disabled: true
      org_billing_usage_in_currency:
        is_disabled: true
      org_billing_remaining_balance:
        is_disabled: true
```

| Key                                                                    | Type   | Default                             | Description                                                                                                                                                                                                        |
| ---------------------------------------------------------------------- | ------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `plugins.org_costs.lookback_hours`                                     | int    | `48`                                | How far back (in hours) the plugin looks for organization usage data on each run. A 48-hour window accommodates Snowflake's ~2-hour view latency and ensures no daily records are missed across collection cycles. |
| `plugins.org_costs.schedule`                                           | string | `USING CRON 0 */6 * * * UTC`        | Cron schedule for the org costs collection task (every 6 hours).                                                                                                                                                   |
| `plugins.org_costs.is_disabled`                                        | bool   | `true`                              | Set to `false` to enable this plugin. Requires `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` database role granted to `DTAGENT_VIEWER` (see readme).                                                                       |
| `plugins.org_costs.telemetry`                                          | list   | `["logs", "metrics", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                           |
| `plugins.org_costs.contexts.org_costs_metering.is_disabled`            | bool   | `true`                              | Set to `false` to enable metering context (daily credit consumption).                                                                                                                                              |
| `plugins.org_costs.contexts.org_costs_storage.is_disabled`             | bool   | `true`                              | Set to `false` to enable storage context (daily storage bytes by type).                                                                                                                                            |
| `plugins.org_costs.contexts.org_costs_data_transfer.is_disabled`       | bool   | `true`                              | Set to `false` to enable data transfer context (bytes transferred between clouds/regions).                                                                                                                         |
| `plugins.org_costs.contexts.org_billing_usage_in_currency.is_disabled` | bool   | `true`                              | Set to `false` to enable billing usage context (daily billing amount in currency).                                                                                                                                 |
| `plugins.org_costs.contexts.org_billing_remaining_balance.is_disabled` | bool   | `true`                              | Set to `false` to enable remaining balance context (contract balance metrics).                                                                                                                                     |

### Org Costs Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Org Costs` plugin

| Name                                           | Type      |
| ---------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_ORG_METERING_DAILY            | view      |
| DTAGENT_DB.APP.V_ORG_STORAGE_DAILY             | view      |
| DTAGENT_DB.APP.V_ORG_DATA_TRANSFER_DAILY       | view      |
| DTAGENT_DB.APP.V_ORG_BILLING_USAGE_IN_CURRENCY | view      |
| DTAGENT_DB.APP.V_ORG_BILLING_REMAINING_BALANCE | view      |
| DTAGENT_DB.CONFIG.UPDATE_ORG_COSTS_CONF()      | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_ORG_COSTS          | task      |

#### Objects referenced by the `Org Costs` plugin

| Name                                                     | Type | Privileges |
| -------------------------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY      | view | SELECT     |
| SNOWFLAKE.ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY     | view | SELECT     |
| SNOWFLAKE.ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY     | view | SELECT     |
| SNOWFLAKE.ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY | view | SELECT     |
| SNOWFLAKE.ORGANIZATION_USAGE.STORAGE_DAILY_HISTORY       | view | SELECT     |

<a name="query_history_info_sec"></a>

## The Query History plugin

This plugin provides information on what SQL queries were run, by whom, when, and their performance. This information is extracted from the
`SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` view, combined with details such as related objects or estimated costs from
`SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY`. For the slowest queries, additional information is retrieved from the `QUERY_OPERATOR_STATS` and
`SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

By default, this plugin executes every 30 minutes and analyzes queries that finished within the last 2 hours and have not already been
processed.

Among the information it provides are:

- the IDs of processed queries,
- runtimes of processed queries,
- numbers of credits used by processed queries,
- number of bytes scanned during the completion of a query, and
- number of partitions scanned during the completion of a query.

Each query execution is reported as a log line and span, with a hierarchy of spans made from the relation to parent queries. If the query
profile was retrieved with `QUERY_OPERATOR_STATS`, it is delivered as span events and additional log lines. This plugin also delivers many
metrics based on telemetry information provided by Snowflake.

**Note:** To correlate query spans with Snowflake's Snowtrail trace_id and span_id, the `event_log` plugin must be enabled. When enabled,
this plugin will automatically extract trace context from the `STATUS.EVENT_LOG` table and include it in the span telemetry, allowing for
distributed tracing correlation between your application and Snowflake queries.

[Show semantics for this plugin](SEMANTICS.md#query_history_semantics_sec)

### Query History default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  query_history:
    schedule_grants: USING CRON */30 * * * * UTC
    schedule: USING CRON */30 * * * * UTC
    is_disabled: false
    slow_queries_threshold: 10000
    slow_queries_to_analyze_limit: 50
    telemetry:
      - metrics
      - logs
      - biz_events
      - spans
```

The plugin can be configured to retrieve query plan and acceleration estimates for the slowest queries. This analysis uses telemetry from
the `QUERY_OPERATOR_STATS` and `SYSTEM$ESTIMATE_QUERY_ACCELERATION` functions.

The following options control this behavior:

- `PLUGINS.QUERY_HISTORY.SLOW_QUERIES_THRESHOLD`: The execution time threshold in milliseconds. Queries running longer than this are
  considered slow and eligible for analysis. Default: `10000` (10 seconds).
- `PLUGINS.QUERY_HISTORY.MAX_SLOWEST_QUERIES`: The maximum number of slowest queries to analyze. Default: `50`.

> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be
> granted `MONITOR` privileges on all warehouses. By default, when the `admin` scope is installed, this is ensured through the periodic
> execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task. The schedule for
> this special task can be configured using the `PLUGINS.QUERY_HISTORY.SCHEDULE_GRANTS` configuration option. Since this procedure runs with
> the elevated privileges of the `DTAGENT_ADMIN` role (which is only created when the `admin` scope is installed), you may choose to:
>
> - Skip the `admin` scope entirely and manually grant `MONITOR` privileges on warehouses to `DTAGENT_VIEWER`
> - Install the `admin` scope and disable the automated grant task, then manually manage `MONITOR` privileges

### Query History Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Query History` plugin

| Name                                                     | Type            | Comment                                                                                        |
| -------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------- |
| DTAGENT_DB.STATUS.PROCESSED_QUERIES_CACHE                | table           |                                                                                                |
| DTAGENT_DB.STATUS.UPDATE_PROCESSED_QUERIES(text,int,int) | procedure       |                                                                                                |
| DTAGENT_DB.APP.TMP_RECENT_QUERIES                        | transient table |                                                                                                |
| DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS                  | transient table |                                                                                                |
| DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES          | transient table |                                                                                                |
| DTAGENT_DB.APP.V_QUERY_HISTORY                           | view            |                                                                                                |
| DTAGENT_DB.APP.V_QUERY_HISTORY_INSTRUMENTED              | view            |                                                                                                |
| DTAGENT_DB.APP.V_RECENT_QUERIES                          | view            |                                                                                                |
| DTAGENT_DB.APP.P_GET_ACCELERATION_ESTIMATES()            | procedure       |                                                                                                |
| DTAGENT_DB.APP.P_REFRESH_RECENT_QUERIES()                | procedure       |                                                                                                |
| DTAGENT_DB.CONFIG.UPDATE_QUERY_HISTORY_CONF()            | procedure       |                                                                                                |
| DTAGENT_DB.APP.P_MONITOR_WAREHOUSES()                    | procedure       | (Admin scope only) Procedure owned by DTAGENT_ADMIN to grant MONITOR privilege on warehouses   |
| DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY                | task            |                                                                                                |
| DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS         | task            | (Admin scope only) Admin task owned by DTAGENT_ADMIN to grant MONITOR privileges on warehouses |

#### Objects referenced by the `Query History` plugin

| Name                                   | Type              | Privileges |
| -------------------------------------- | ----------------- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY | view              | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY  | view              | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.SESSIONS       | view              | SELECT     |
| SYSTEM$ESTIMATE_QUERY_ACCELERATION     | function          | USAGE      |
| GET_QUERY_OPERATOR_STATS               | function          | USAGE      |
| ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR   | account parameter | ALTER      |
| SHOW WAREHOUSES                        | command           | USAGE      |

<a name="resource_monitors_info_sec"></a>

## The Resource Monitors plugin

This plugin reports the state of resource monitors and analyzes the conditions of warehouses. All necessary information found by the plugin
is delivered through metrics and logs. Additionally, events are sent when changes in the state of a resource monitor or warehouse are
detected.

By default, it executes every 30 minutes and resumes the analysis from where it left off. Before collecting the data, the state of all
resource monitors is refreshed.

This plugin:

- logs the current state of each resource monitor and warehouse,
- logs an error if an account-level monitor setup is missing,
- logs a warning if a warehouse is not monitored at all, and
- sends events on all new activities of monitors and warehouses.

[Show semantics for this plugin](SEMANTICS.md#resource_monitors_semantics_sec)

### Resource Monitors default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  resource_monitors:
    schedule: USING CRON */30 * * * * UTC
    is_disabled: false
    telemetry:
      - logs
      - metrics
      - events
      - biz_events
```

### Resource Monitors Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Resource Monitors` plugin

| Name                                              | Type            |
| ------------------------------------------------- | --------------- |
| DTAGENT_DB.APP.TMP_RESOURCE_MONITORS              | transient table |
| DTAGENT_DB.APP.TMP_WAREHOUSES                     | transient table |
| DTAGENT_DB.APP.V_RESOURCE_MONITORS                | view            |
| DTAGENT_DB.APP.V_WAREHOUSES                       | view            |
| DTAGENT_DB.APP.P_REFRESH_RESOURCE_MONITORS()      | procedure       |
| DTAGENT_DB.CONFIG.UPDATE_RESOURCE_MONITORS_CONF() | procedure       |
| DTAGENT_DB.APP.TASK_DTAGENT_RESOURCE_MONITORS     | task            |

#### Objects referenced by the `Resource Monitors` plugin

| Name                   | Type    | Privileges |
| ---------------------- | ------- | ---------- |
| SHOW RESOURCE MONITORS | command | USAGE      |
| SHOW WAREHOUSES        | command | USAGE      |

<a name="shares_info_sec"></a>

## The Shares plugin

This plugin enables tracking shares, both inbound and outbound, present in a Snowflake account, or a subset of those subject to
configuration. Apart from reporting basic information on each share, as delivered from `SHOW SHARES`, this plugin also:

- logs lists tables that were shared with the current account (inbound share),
- logs objects shared from this account (outbound share),
- sends events when a share is created,
- sends events when an object is granted to a share, and
- sends events when a table is shared, updated, or modified (DDL).

By default, shares are monitored every 60 minutes. It is possible to exclude certain shares (or parts of them) from tracking detailed
information.

[Show semantics for this plugin](SEMANTICS.md#shares_semantics_sec)

### Shares default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  shares:
    schedule: USING CRON */30 * * * * UTC
    is_disabled: false
    exclude_from_monitoring: []
    exclude:
      - ""
    include:
      - "%.%.%"
    telemetry:
      - logs
      - events
      - biz_events
```

### Shares Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Shares` plugin

| Name                                                   | Type            |
| ------------------------------------------------------ | --------------- |
| DTAGENT_DB.APP.TMP_SHARES                              | transient table |
| DTAGENT_DB.APP.TMP_OUTBOUND_SHARES                     | transient table |
| DTAGENT_DB.APP.TMP_INBOUND_SHARES                      | transient table |
| DTAGENT_DB.APP.V_SHARE_EVENTS                          | view            |
| DTAGENT_DB.APP.V_INBOUND_SHARE_TABLES                  | view            |
| DTAGENT_DB.APP.V_OUTBOUND_SHARE_TABLES                 | view            |
| DTAGENT_DB.APP.P_GET_SHARES()                          | procedure       |
| DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(VARCHAR)    | procedure       |
| DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(VARCHAR, VARCHAR) | procedure       |
| DTAGENT_DB.CONFIG.UPDATE_SHARES_CONF()                 | procedure       |
| DTAGENT_DB.APP.TASK_DTAGENT_SHARES                     | task            |

#### Objects referenced by the `Shares` plugin

| Name                                       | Type    | Privileges                      | Granted to     | Comment                                                                                                              |
| ------------------------------------------ | ------- | ------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------- |
| $shared_database                           | share   | IMPORTED PRIVILEGES ON DATABASE | DTAGENT_VIEWER |                                                                                                                      |
| $shared_database.INFORMATION_SCHEMA.TABLES | view    | SELECT                          | DTAGENT_VIEWER |                                                                                                                      |
| ACCOUNT                                    | account | IMPORT SHARE                    | DTAGENT_VIEWER | We just need to read the metadata about the shares and objects being shared wish there was a way with less privilege |
| SHOW SHARES                                | command | USAGE                           |                |                                                                                                                      |
| SHOW GRANTS TO SHARE $share                | command | USAGE                           |                |                                                                                                                      |

<a name="snowpipes_info_sec"></a>

## The Snowpipes plugin

This plugin enables monitoring of Snowflake Snowpipes, tracking real-time pipe status, ingestion latency, throughput, costs, and load
errors.

The plugin uses a **dual-schedule architecture**:

- **Fast mode** (every 5 minutes, no warehouse): `SHOW PIPES` + `SYSTEM$PIPE_STATUS()` for real-time status, backlog, and latency.
- **Deep mode** (hourly, warehouse required): `ACCOUNT_USAGE.COPY_HISTORY` and `PIPE_USAGE_HISTORY` for volume, cost, errors, throughput,
  and per-file latency.

The `MONITOR` privilege on pipes is required for `SYSTEM$PIPE_STATUS()`. When the `admin` scope is installed, this is handled automatically
by `P_GRANT_MONITOR_SNOWPIPES()`.

[Show semantics for this plugin](SEMANTICS.md#snowpipes_semantics_sec)

### Snowpipes default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  snowpipes:
    include:
      - "%.%.%"
    exclude:
      - DTAGENT_DB.%.%
    schedule: USING CRON */5 * * * * UTC
    schedule_history: USING CRON 0 * * * * UTC
    schedule_grants: USING CRON 30 */12 * * * UTC
    lookback_hours: 4
    lookback_hours_usage: 6
    is_disabled: false
    telemetry:
      - metrics
      - logs
      - events
      - biz_events
```

> **IMPORTANT**: For this plugin to function correctly, `MONITOR on PIPES` must be granted to the `DTAGENT_VIEWER` role (required for
> `SYSTEM$PIPE_STATUS()`). By default, when the `admin` scope is installed, this is handled by the `P_GRANT_MONITOR_SNOWPIPES()` procedure,
> which is executed with the elevated privileges of the `DTAGENT_ADMIN` role (created only when the `admin` scope is installed), via the
> `APP.TASK_DTAGENT_SNOWPIPES_GRANTS` task. The schedule for this task can be configured separately using the
> `PLUGINS.SNOWPIPES.SCHEDULE_GRANTS` configuration option.

The grant granularity is derived automatically from the `include` pattern:

| Include pattern             | Grant level | SQL issued                                        |
| --------------------------- | ----------- | ------------------------------------------------- |
| `%.%.%` or `PROD_DB.%.%`    | Database    | `GRANT MONITOR ON ALL/FUTURE PIPES IN DATABASE …` |
| `PROD_DB.ANALYTICS.%`       | Schema      | `GRANT MONITOR ON ALL/FUTURE PIPES IN SCHEMA …`   |
| `PROD_DB.ANALYTICS.MY_PIPE` | Pipe        | `GRANT MONITOR ON PIPE …` (no FUTURE grant)       |

Alternatively, you may choose to grant the required permissions manually, using the appropriate `GRANT MONITOR ON ALL/FUTURE PIPES IN …`
statement, depending on the desired granularity.

### Configuration keys

| Key                                      | Default                               | Description                                       |
| ---------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| `plugins.snowpipes.include`              | `['%.%.%']`                           | Pipe name patterns to include (fully qualified)   |
| `plugins.snowpipes.exclude`              | `[DTAGENT_DB.%.%]`                    | Pipe name patterns to exclude                     |
| `plugins.snowpipes.schedule`             | `USING CRON */5 * * * * UTC`          | Fast-mode schedule (SHOW PIPES + PIPE_STATUS)     |
| `plugins.snowpipes.schedule_history`     | `USING CRON 0 * * * * UTC`            | Deep-mode schedule (COPY_HISTORY + USAGE_HISTORY) |
| `plugins.snowpipes.schedule_grants`      | `USING CRON 30 */12 * * * UTC`        | Admin grant task schedule                         |
| `plugins.snowpipes.lookback_hours`       | `4`                                   | Lookback window for COPY_HISTORY (hours)          |
| `plugins.snowpipes.lookback_hours_usage` | `6`                                   | Lookback window for PIPE_USAGE_HISTORY (hours)    |
| `plugins.snowpipes.is_disabled`          | `false`                               | Disable the plugin                                |
| `plugins.snowpipes.telemetry`            | `[metrics, logs, events, biz_events]` | Enabled telemetry types                           |

### Snowpipes Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Snowpipes` plugin

| Name                                                  | Type            | Comment                                                                                   |
| ----------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------- |
| DTAGENT_DB.APP.TMP_SNOWPIPES_RESULT                   | transient table |                                                                                           |
| DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED()             | procedure       |                                                                                           |
| DTAGENT_DB.APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED  | view            |                                                                                           |
| DTAGENT_DB.APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED | view            |                                                                                           |
| DTAGENT_DB.APP.P_GRANT_MONITOR_SNOWPIPES()            | procedure       |                                                                                           |
| DTAGENT_DB.CONFIG.UPDATE_SNOWPIPES_CONF()             | procedure       |                                                                                           |
| DTAGENT_DB.APP.TASK_DTAGENT_SNOWPIPES                 | task            | Fast-mode (\*/5)                                                                          |
| DTAGENT_DB.APP.TASK_DTAGENT_SNOWPIPES_HISTORY         | task            | Deep-mode (hourly)                                                                        |
| DTAGENT_DB.APP.TASK_DTAGENT_SNOWPIPES_GRANTS          | task            | (Admin scope only) Admin task owned by DTAGENT_ADMIN to grant MONITOR privileges on pipes |

#### Objects referenced by the `Snowpipes` plugin

| Name                                       | Type     | Privileges                   | Granted to     | Comment                                                                                                              |
| ------------------------------------------ | -------- | ---------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------- |
| SHOW PIPES                                 | command  | USAGE                        |                |                                                                                                                      |
| SYSTEM$PIPE_STATUS                         | function | MONITOR (per pipe)           |                |                                                                                                                      |
| SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY       | view     | SELECT (IMPORTED PRIVILEGES) |                |                                                                                                                      |
| SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY | view     | SELECT (IMPORTED PRIVILEGES) |                |                                                                                                                      |
| SNOWFLAKE.ACCOUNT_USAGE.PIPES              | view     | SELECT (IMPORTED PRIVILEGES) |                | Joined in V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED to resolve UUID PIPE_NAME to human-readable FQN                     |
| ALL PIPES IN DATABASE $db                  | pipe     | MONITOR                      | DTAGENT_VIEWER | Granted when include pattern has wildcard schema (e.g. DB.%.%)                                                       |
| ALL FUTURE PIPES IN DATABASE $db           | pipe     | MONITOR                      | DTAGENT_VIEWER | Granted when include pattern has wildcard schema (e.g. DB.%.%)                                                       |
| ALL PIPES IN SCHEMA $db.$schema            | pipe     | MONITOR                      | DTAGENT_VIEWER | Granted when include pattern has specific schema (e.g. DB.ANALYTICS.%)                                               |
| ALL FUTURE PIPES IN SCHEMA $db.$schema     | pipe     | MONITOR                      | DTAGENT_VIEWER | Granted when include pattern has specific schema (e.g. DB.ANALYTICS.%)                                               |
| PIPE $db.$schema.$pipe                     | pipe     | MONITOR                      | DTAGENT_VIEWER | Granted when include pattern specifies an exact pipe name (e.g. DB.ANALYTICS.MY_PIPE); no FUTURE grant at pipe level |

<a name="tasks_info_sec"></a>

## The Tasks plugin

This plugin provides detailed information on the usage and performance of tasks within a Snowflake account. It leverages three key
functions/views from Snowflake:

- `TASK_HISTORY`: Delivers the history of task usage for the entire Snowflake account, a specified task, or task graph.
- `TASK_VERSIONS`: Enables retrieval of the history of task versions, with entries indicating the tasks that comprised a task graph and
  their properties at a given time.
- `SERVERLESS_TASK_HISTORY`: Provides information on the serverless task usage history, including the serverless task name and credits
  consumed by serverless task usage.

In short, the plugin delivers, as logs by default, information on:

- timestamps of the task execution,
- warehouse ID the task is performed on,
- database ID the task is performed on,
- credits used (as metric).

Additionally, an event is sent when a new task graph version is created. By default, the plugin executes every 90 minutes.

[Show semantics for this plugin](SEMANTICS.md#tasks_semantics_sec)

### Tasks default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  tasks:
    lookback_hours: 4
    lookback_hours_versions: 720
    schedule: USING CRON 30 * * * * UTC
    is_disabled: false
    telemetry:
      - logs
      - metrics
      - events
      - biz_events
```

| Key                                     | Type   | Default                                       | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------------------- | ------ | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.tasks.lookback_hours`          | int    | `4`                                           | How far back (in hours) the plugin looks for serverless task history on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Default is `4`h to account for the up-to-3-hour data ingestion delay in `SERVERLESS_TASK_HISTORY`.                                                                 |
| `plugins.tasks.lookback_hours_versions` | int    | `720`                                         | How far back (in hours) the plugin looks for task version history on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours_versions`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours_versions`, so it never reads data older than the lookback window. Default is `720`h (30 days) — task graph versions change infrequently and a longer window ensures new deployments catch all recent version changes. |
| `plugins.tasks.schedule`                | string | `USING CRON 30 * * * * UTC`                   | Cron schedule for the tasks collection task.                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `plugins.tasks.is_disabled`             | bool   | `false`                                       | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `plugins.tasks.telemetry`               | list   | `["logs", "metrics", "events", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                                                                                                                                             |

> **Note**: `lookback_hours` and `lookback_hours_versions` serve different data sources with different update frequencies.
> `SERVERLESS_TASK_HISTORY` is updated frequently (per task run), while `TASK_VERSIONS` only changes when a task graph is modified — hence
> the much longer default for versions.

### Tasks Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Tasks` plugin

| Name                                  | Type      |
| ------------------------------------- | --------- |
| DTAGENT_DB.APP.V_SERVERLESS_TASKS     | view      |
| DTAGENT_DB.APP.V_TASK_VERSIONS        | view      |
| DTAGENT_DB.APP.V_TASK_HISTORY         | view      |
| DTAGENT_DB.CONFIG.UPDATE_TASKS_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_TASKS     | task      |

#### Objects referenced by the `Tasks` plugin

| Name                                            | Type     | Privileges |
| ----------------------------------------------- | -------- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY | view     | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.TASK_VERSIONS           | view     | SELECT     |
| INFORMATION_SCHEMA.TASK_HISTORY()               | function | USAGE      |

<a name="trust_center_info_sec"></a>

## The Trust Center plugin

Delivers new findings reported (within the last 24 hours) by Snowflake Trust Center as log entries. For findings with `CRITICAL` severity,
`CUSTOM_ALERT` event is sent to Dynatrace.

This plugin provides information on:

- scanner name, description, and packages details,
- number of entities at risk as a metric, plus
- details on those entities as `snowflake.entity.details` log attribute.

[Show semantics for this plugin](SEMANTICS.md#trust_center_semantics_sec)

### Trust Center default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  trust_center:
    schedule: USING CRON 30 */12 * * * UTC
    log_details: false
    is_disabled: false
    telemetry:
      - metrics
      - logs
      - events
      - biz_events
```

### Trust Center Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Trust Center` plugin

| Name                                         | Type      |
| -------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS       | view      |
| DTAGENT_DB.APP.V_TRUST_CENTER_METRICS        | view      |
| DTAGENT_DB.APP.V_TRUST_CENTER_INSTRUMENTED   | view      |
| DTAGENT_DB.CONFIG.UPDATE_TRUST_CENTER_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_TRUST_CENTER     | task      |

#### Objects referenced by the `Trust Center` plugin

| Name                            | Type | Privileges       | Granted to     |
| ------------------------------- | ---- | ---------------- | -------------- |
| SNOWFLAKE.TRUST_CENTER_VIEWER   | role | APPLICATION ROLE | DTAGENT_VIEWER |
| SNOWFLAKE.TRUST_CENTER.FINDINGS | view | SELECT           | DTAGENT_VIEWER |

<a name="users_info_sec"></a>

## The Users plugin

Focuses on providing a broad overview of the users in the system. The data is downloaded from `USERS`, `LOGIN_HISTORY`, and
`GRANTS_TO_USERS` views. By default, sends all e-mails hashed (to send them in cleartext, switch `PLUGINS.USERS.IS_HASHED` to `false`). It
is possible to create a table with emails-to-hash map which can be accessed at `STATUS.EMAIL_HASH_MAP` by setting
`PLUGINS.USERS.RETAIN_EMAIL_HASH_MAP` to `true`. The core functionality of the plugin is to report all active users and those that have been
removed since last run, with one log line per user. This information is provided by default, regardless of other enabled modes. Role
monitoring includes three possible modes:

- `DIRECT_ROLES` - users with comma-separated list of roles directly granted to the user, with roles that have been removed since last run;
- `ALL_ROLES` - users with comma-separated list of all roles granted to the user;
- `ALL_PRIVILEGES` - users with all privileges granted per user.

Role monitoring mode can be defined at `PLUGINS.USERS.ROLES_MONITORING_MODE` configuration option. More detailed monitoring modes will
impact performance, caution is recommended with more advanced modes.

It is possible to choose more than one mode at a time, which will result in multiple analyses being performed.

The plugin reports on:

- date of last successful login of a user,
- user's default and directly granted roles, and
- user account details.

[Show semantics for this plugin](SEMANTICS.md#users_semantics_sec)

### Users default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  users:
    schedule: USING CRON 0 0 * * * UTC
    is_disabled: false
    is_hashed: true
    retain_email_hash_map: false
    roles_monitoring_mode: []
    telemetry:
      - logs
      - events
      - biz_events
```

### Users Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Users` plugin

| Name                                                     | Type            | Comment                                                                                                                                                            |
| -------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| DTAGENT_DB.APP.TMP_USERS                                 | transient table |                                                                                                                                                                    |
| DTAGENT_DB.APP.TMP_USERS_HELPER                          | transient table |                                                                                                                                                                    |
| DTAGENT_DB.APP.V_USERS_INSTRUMENTED                      | view            |                                                                                                                                                                    |
| DTAGENT_DB.APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED       | view            |                                                                                                                                                                    |
| DTAGENT_DB.APP.V_USERS_ALL_ROLES_INSTRUMENTED            | view            |                                                                                                                                                                    |
| DTAGENT_DB.APP.V_USERS_DIRECT_ROLES_INSTRUMENTED         | view            |                                                                                                                                                                    |
| DTAGENT_DB.APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED | view            |                                                                                                                                                                    |
| DTAGENT_DB.APP.TMP_USERS_SNAPSHOT                        | transient table |                                                                                                                                                                    |
| DTAGENT_DB.STATUS.EMAIL_HASH_MAP                         | transient table | Optional (controlled by plugins.users.retain_email_hash_map). Created only when retain_email_hash_map is enabled; persists email→SHA-256 hash mappings across runs |
| DTAGENT_DB.APP.P_GET_USERS()                             | procedure       |                                                                                                                                                                    |
| DTAGENT_DB.CONFIG.UPDATE_USERS_CONF()                    | procedure       |                                                                                                                                                                    |
| DTAGENT_DB.APP.TASK_DTAGENT_USERS                        | task            |                                                                                                                                                                    |

#### Objects referenced by the `Users` plugin

| Name                                    | Type | Privileges |
| --------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.USERS           | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY   | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.ROLES           | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES | view | SELECT     |

<a name="warehouse_usage_info_sec"></a>

## The Warehouse Usage plugin

The `warehouse usage` plugin delivers detailed information regarding warehouses' credit usage, workload, and events triggered on them. This
plugin provides telemetry based on the `WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, and `WAREHOUSE_METERING_HISTORY` views.

It sends:

- metrics on hourly credit usage of warehouses,
- metrics on query load values for executed queries,
- log entries on warehouse events, such as creating, dropping, altering, resizing, resuming, or suspending a cluster or the entire
  warehouse.

[Show semantics for this plugin](SEMANTICS.md#warehouse_usage_semantics_sec)

### Warehouse Usage default configuration

To disable this plugin, set `IS_DISABLED` to `true`.

In case the global property `PLUGINS.DISABLED_BY_DEFAULT` is set to `true`, you need to explicitly set `IS_ENABLED` to `true` to enable
selected plugins; `IS_DISABLED` is not checked then.

```yaml
plugins:
  warehouse_usage:
    lookback_hours: 24
    schedule: USING CRON 0 * * * * UTC
    is_disabled: false
    telemetry:
      - logs
      - metrics
      - biz_events
```

| Key                                      | Type   | Default                             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ---------------------------------------- | ------ | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.warehouse_usage.lookback_hours` | int    | `24`                                | How far back (in hours) the plugin looks for warehouse events, load, and metering history on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Applies to all three views (`WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, `WAREHOUSE_METERING_HISTORY`). |
| `plugins.warehouse_usage.schedule`       | string | `USING CRON 0 * * * * UTC`          | Cron schedule for the warehouse usage collection task.                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `plugins.warehouse_usage.is_disabled`    | bool   | `false`                             | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `plugins.warehouse_usage.telemetry`      | list   | `["logs", "metrics", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                                                                                                                |

### Warehouse Usage Bill of Materials

The following tables list the Snowflake objects that this plugin delivers data from or references.

#### Objects delivered by the `Warehouse Usage` plugin

| Name                                            | Type      |
| ----------------------------------------------- | --------- |
| DTAGENT_DB.APP.V_WAREHOUSE_EVENT_HISTORY        | view      |
| DTAGENT_DB.APP.V_WAREHOUSE_LOAD_HISTORY         | view      |
| DTAGENT_DB.APP.V_WAREHOUSE_METERING_HISTORY     | view      |
| DTAGENT_DB.CONFIG.UPDATE_WAREHOUSE_USAGE_CONF() | procedure |
| DTAGENT_DB.APP.TASK_DTAGENT_WAREHOUSE_USAGE     | task      |

#### Objects referenced by the `Warehouse Usage` plugin

| Name                                               | Type | Privileges |
| -------------------------------------------------- | ---- | ---------- |
| SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY   | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY     | view | SELECT     |
| SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY | view | SELECT     |

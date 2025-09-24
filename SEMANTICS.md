# Semantic Dictionary

* [Shared semantics](#core_semantics_sec)
* [Active Queries](#active_queries_semantics_sec)
* [Budgets](#budgets_semantics_sec)
* [Data Schemas](#data_schemas_semantics_sec)
* [Data Volume](#data_volume_semantics_sec)
* [Dynamic Tables](#dynamic_tables_semantics_sec)
* [Event Log](#event_log_semantics_sec)
* [Event Usage](#event_usage_semantics_sec)
* [Login History](#login_history_semantics_sec)
* [Query History](#query_history_semantics_sec)
* [Resource Monitors](#resource_monitors_semantics_sec)
* [Shares](#shares_semantics_sec)
* [Tasks](#tasks_semantics_sec)
* [Trust Center](#trust_center_semantics_sec)
* [Users](#users_semantics_sec)
* [Warehouse Usage](#warehouse_usage_semantics_sec)<a name="core_semantics_sec"></a>

## Dynatrace Snowflake Observability Agent `core` semantics

### Dimensions at the `core` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;system | The database management system (DBMS) product being used. It is always 'snowflake' | snowflake |
| deployment.&#8203;environment | The deployment environment, e.g., production, staging, or development. | PROD |
| deployment.&#8203;environment.&#8203;tag | Optional tag for the deployment environment in multitenancy mode | SA080 |
| host.&#8203;name | The name of the host. | mysnowflake.us-east-1.snowflakecomputing.com |
| service.&#8203;name | The name of the service. | mysnowflake.us-east-1 |
| telemetry.&#8203;exporter.&#8203;name | The name of the telemetry exporter. It is always 'dynatrace.snowagent' | dynatrace.snowagent |
| telemetry.&#8203;exporter.&#8203;version | The version of the telemetry exporter. | 0.8.0.17308403933 |

### Attributes at the `core` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| dsoa.&#8203;run.&#8203;context | The name of the Dynatrace Snowflake Observability Agent plugin (or part of plugin) used to produce the telemetry (logs, traces, metrics, or events). | query_history |
| dsoa.&#8203;run.&#8203;id | Unique ID of each execution of the Dynatrace Snowflake Observability Agent plugin. It can be used to differentiate between telemetry produced between two executions, e.g., to calculate the change in the system. | 4aa7c76c-e98c-4b8b-a5b3-a8a721bbde2d |
| snowflake.&#8203;event.&#8203;type | Type of (timestamp based) event | snowflake.table.update |

<a name="active_queries_semantics_sec"></a>

## The `Active Queries` plugin semantics

[Show plugin description](PLUGINS.md#active_queries_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "active_queries"`.

### Dimensions at the `Active Queries` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;namespace | The name of the database in which the query was executed. | analytics_db |
| db.&#8203;user | The name of the user who executed the query. | john_doe |
| snowflake.&#8203;query.&#8203;execution_status | The execution status of the query, such as: <br>- RESUMING_WAREHOUSE, <br>- RUNNING, <br>- QUEUED, <br>- BLOCKED, <br>- SUCCESS, <br>- FAILED_WITH_ERROR, <br>- FAILED_WITH_INCIDENT.  | FAILED_WITH_ERROR |
| snowflake.&#8203;role.&#8203;name | The role that was active in the session at the time of the query. | analyst_role |
| snowflake.&#8203;warehouse.&#8203;name | The name of the warehouse used to execute the query. | compute_wh |

### Attributes at the `Active Queries` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;operation.&#8203;name | The type of operation performed by the query, such as: <br>- SELECT, <br>- INSERT, <br>- UPDATE.  | SELECT |
| db.&#8203;query.&#8203;text | The text of the SQL query. | SELECT * FROM sales_data |
| session.&#8203;id | The unique identifier for the session in which the query was executed. | 123456789 |
| snowflake.&#8203;error.&#8203;code | The error code if the query failed. | 1001 |
| snowflake.&#8203;error.&#8203;message | The error message if the query failed. | Syntax error in SQL statement |
| snowflake.&#8203;query.&#8203;hash | The hash value of the query text. | hash_abcdef |
| snowflake.&#8203;query.&#8203;hash_version | The version of the query hash logic. | 1 |
| snowflake.&#8203;query.&#8203;id | The unique identifier for the query. | b1bbaa7f-8144-4e50-947a-b7e9bf7d62d5 |
| snowflake.&#8203;query.&#8203;parametrized_hash | The hash value of the parameterized query text. | param_hash_abcdef |
| snowflake.&#8203;query.&#8203;parametrized_hash_version | The version of the parameterized query hash logic. | 1 |
| snowflake.&#8203;query.&#8203;tag | The tag associated with the query, if any. | daily_report |
| snowflake.&#8203;schema.&#8203;name | The name of the schema in which the query was executed. | public |
| snowflake.&#8203;warehouse.&#8203;type | The type of warehouse used to execute the query. | STANDARD |

### Metrics at the `Active Queries` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;data.&#8203;written_to_result | Bytes Written to Result | bytes | Number of bytes written to a result object. | 1048576 |
| snowflake.&#8203;rows.&#8203;written_to_result | Rows Written to Result | rows | Number of rows written to a result object. For CREATE TABLE AS SELECT (CTAS) and all DML operations, this result is 1;. | 1 |
| snowflake.&#8203;time.&#8203;compilation | Query Compilation Time | ms | The total compilation time of the currently running query.  | 5000 |
| snowflake.&#8203;time.&#8203;execution | Execution Time | ms | Execution time (in milliseconds) | 100000 |
| snowflake.&#8203;time.&#8203;running | Query Running Time | ms | The total running time of the currently running query.  | 120000 |
| snowflake.&#8203;time.&#8203;total_elapsed | Total Elapsed Time | ms | Elapsed time (in milliseconds). | 120000 |

<a name="budgets_semantics_sec"></a>

## The `Budgets` plugin semantics

[Show plugin description](PLUGINS.md#budgets_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "budgets"`.

### Dimensions at the `Budgets` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;namespace | The name of the database that was specified in the context of the query at compilation. | analytics_db |
| snowflake.&#8203;budget.&#8203;name | Name of the budget. | monthly_budget |
| snowflake.&#8203;schema.&#8203;name | Schema that was specified in the context of the query at compilation. | public |
| snowflake.&#8203;service.&#8203;type | Type of service that is consuming credits, which can be one of the following: <br>- AUTO_CLUSTERING, <br>- HYBRID_TABLE_REQUESTS, <br>- MATERIALIZED_VIEW, <br>- PIPE, <br>- QUERY_ACCELERATION, <br>- SEARCH_OPTIMIZATION, <br>- SERVERLESS_ALERTS, <br>- SERVERLESS_TASK, <br>- SNOWPIPE_STREAMING, <br>- WAREHOUSE_METERING, <br>- WAREHOUSE_METERING_READER  | WAREHOUSE_METERING |

### Attributes at the `Budgets` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;budget.&#8203;owner | The owner of the budget, typically the user or role responsible for managing the budget. | budget_admin |
| snowflake.&#8203;budget.&#8203;owner.&#8203;role_type | The type of role assigned to the budget owner, indicating their level of access and responsibilities. | ACCOUNTADMIN |
| snowflake.&#8203;budget.&#8203;resource | The resources linked to the budget, such as databases, warehouses, or other Snowflake objects that the budget monitors. | [ "database1", "warehouse1" ] |

### Metrics at the `Budgets` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;credits.&#8203;limit | Budget Spending Limit | credits | The number of credits set as the spending limit for the budget. | 100 |
| snowflake.&#8203;credits.&#8203;spent | Credits Spent | credits | Number of credits used. | 75 |

### Event timestamps at the `Budgets` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;budget.&#8203;created_on | The timestamp when the budget was created. | 2024-11-30 23:59:59.999 |
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.budget.created_on |

<a name="data_schemas_semantics_sec"></a>

## The `Data Schemas` plugin semantics

[Show plugin description](PLUGINS.md#data_schemas_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "data_schemas"`.

### Attributes at the `Data Schemas` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;user | The user who issued the query. | SYSTEM |
| snowflake.&#8203;object.&#8203;ddl.&#8203;modified | A JSON array that specifies the objects that were associated with a write operation in the query. | { "DTAGENT_DB.APP.TMP_RECENT_QUERIES": { "objectColumns": "HISTOGRAM_METRICS, COUNTER_METRICS, START_TIME, STATUS_CODE, SESSION_ID, QUERY_ID, DIMENSIONS, END_TIME, NAME, ATTRIBUTES, PARENT_QUERY_ID", "objectDomain": "Table" } } |
| snowflake.&#8203;object.&#8203;ddl.&#8203;operation | The SQL keyword that specifies the operation on the table, view, or column: <br>- ALTER, <br>- CREATE, <br>- DROP, <br>- REPLACE,  <br>- UNDROP.  | REPLACE |
| snowflake.&#8203;object.&#8203;ddl.&#8203;properties | A JSON array that specifies the object or column properties when you create, modify, drop, or undrop the object or column.  There are two types of properties: atomic and compound.  | {"creationMode": "CREATE", "columns": {"ADD": ["ATTRIBUTE","JOB_ID"]}} |
| snowflake.&#8203;object.&#8203;id | An identifier for the object, which is unique within a given account and domain. | 747545 |
| snowflake.&#8203;object.&#8203;name | The fully qualified name of the object defined or modified by the DDL operation. | DTAGENT_DB.APP.TMP_RECENT_QUERIES |
| snowflake.&#8203;object.&#8203;type | The domain of the object defined or modified by the DDL operation, which includes all objects that can be tagged and: <br>- MASKING POLICY, <br>- ROW ACCESS POLICY, <br>- TAG.  | Table |
| snowflake.&#8203;query.&#8203;id | An internal, system<br>-generated identifier for the SQL statement. | 01b30d58-0604-6e1c-0040-e003029c1322 |
| snowflake.&#8203;query.&#8203;parent_id | The query ID of the parent job or NULL if the job does not have a parent. | 01b2fd01-0604-6864-0040-e003029abda2 |
| snowflake.&#8203;query.&#8203;root_id | The query ID of the top most job in the chain or NULL if the job does not have a parent. | 01b2fd00-0604-6864-0040-e003029abd82 |

<a name="data_volume_semantics_sec"></a>

## The `Data Volume` plugin semantics

[Show plugin description](PLUGINS.md#data_volume_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "data_volume"`.

### Dimensions at the `Data Volume` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;collection.&#8203;name | The full name of the table, including the catalog, schema, and table name. | analytics_db.public.sales_data |
| db.&#8203;namespace | The name of the database that contains the table. | analytics_db |
| snowflake.&#8203;table.&#8203;type | The type of the table, such as: <br>- BASE TABLE, <br>- TEMPORARY TABLE, <br>- EXTERNAL TABLE.  | BASE TABLE |

### Metrics at the `Data Volume` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;data.&#8203;rows | Row Count | rows | Sum of all rows in all objects in this scope. | 1000000 |
| snowflake.&#8203;data.&#8203;size | Table Size in Bytes | bytes | Total size (in bytes) of all objects in this scope. | 1073741824 |
| snowflake.&#8203;table.&#8203;time_since.&#8203;last_ddl | Time Since Last DDL | min | Time (in minutes) since last time given objects structure was altered. | 2880 |
| snowflake.&#8203;table.&#8203;time_since.&#8203;last_update | Time Since Last Update | min | Time (in minutes) since last time content of given objects was updated. | 1440 |

### Event timestamps at the `Data Volume` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.table.update |
| snowflake.&#8203;table.&#8203;ddl | Timestamp of the last DDL operation performed on the table or view. All supported table/view DDL operations update this field: <br>- CREATE, <br>- ALTER, <br>- DROP, <br>- UNDROP  | 2024-11-01 12:00:00.000 |
| snowflake.&#8203;table.&#8203;update | Date and time the object was last altered by a DML, DDL, or background metadata operation. | 2024-11-10 16:45:00.000 |

<a name="dynamic_tables_semantics_sec"></a>

## The `Dynamic Tables` plugin semantics

[Show plugin description](PLUGINS.md#dynamic_tables_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Dynamic Tables` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;collection.&#8203;name | Name of the dynamic table. | EMPLOYEE_DET | dynamic_tables, dynamic_table_refresh_history, dynamic_table_graph_history |
| db.&#8203;namespace | The name of the database in which the query was executed. | DYNAMIC_TABLE_DB | dynamic_tables, dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;schema.&#8203;name | Name of the schema that contains the dynamic table. | DYNAMIC_TABLE_SCH | dynamic_tables, dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;full_name | Fully qualified name of the dynamic table. | DYNAMIC_TABLE_DB.DYNAMIC_TABLE_SCH.EMPLOYEE_DET | dynamic_tables, dynamic_table_refresh_history, dynamic_table_graph_history |

### Attributes at the `Dynamic Tables` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;query.&#8203;text | The SELECT statement for this dynamic table. | SELECT A.EMP_ID,A.EMP_NAME,A.EMP_ADDRESS, B.SKILL_ID,B.SKILL_NAME,B.SKILL_LEVEL FROM EMPLOYEE A, EMPLOYEE_SKILL B WHERE A.EMP_ID=B.EMP_ID ORDER BY B.SKILL_ID ; | dynamic_table_graph_history |
| snowflake.&#8203;query.&#8203;id | If present, this represents the query ID of the refresh job that produced the results for the dynamic table. | 01b899f1-0712-45a6-0040-e00303977b8e | dynamic_tables, dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;graph.&#8203;alter_trigger | Describes why a new entry is created in the DYNAMIC_TABLE_GRAPH_HISTORY function. Can be one of the following: <br>- NONE (backwards<br>-compatible), <br>- CREATE_DYNAMIC_TABLE, <br>- ALTER_TARGET_LAG, <br>- SUSPEND, RESUME, <br>- REPLICATION_REFRESH, <br>- ALTER_WAREHOUSE.  | [ "CREATE_DYNAMIC_TABLE" ] | dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;graph.&#8203;inputs | Each OBJECT represents a table, view, or dynamic table that serves as the input to this dynamic table. | [ { "kind": "TABLE", "name": "DYNAMIC_TABLE_DB.DYNAMIC_TABLE_SCH.EMPLOYEE" }, { "kind": "TABLE", "name": "DYNAMIC_TABLE_DB.DYNAMIC_TABLE_SCH.EMPLOYEE_SKILL" } ] | dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;graph.&#8203;valid_from | Encodes the VALID_FROM timestamp of the DYNAMIC_TABLE_GRAPH_HISTORY table function when the refresh occurred. | 2024-11-20 19:53:47.448 Z | dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;graph.&#8203;valid_to | If present, the description of the dynamic table is valid up to this time. If null, the description is still accurate. |  | dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;target.&#8203;type | The type of target lag. | USER_DEFINED | dynamic_tables, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;code | Code representing the current state of the refresh. If the LAST_COMPLETED_REFRESH_STATE is FAILED, this column shows the error code associated with the failure. | SUCCESS | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;data_timestamp | Data timestamp of the last successful refresh. | 2024-11-22 12:55:29.695 Z | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;dependency.&#8203;data_timestamp | Data timestamp of the latest dependency to become available. | 2024-11-25 06:09:53.695 Z | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;dependency.&#8203;name | Qualified name of the latest dependency to become available. | DYNAMIC_TABLE_DB.DYNAMIC_TABLE_SCH.EMPLOYEE | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;message | Description of the current state of the refresh. If the LAST_COMPLETED_REFRESH_STATE is FAILED, this column shows the error message associated with the failure. |  | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;latest.&#8203;state | Status of the last terminated refresh for the dynamic table. Can be one of the following: <br>- **SUCCEEDED**: Refresh completed successfully, <br>- **FAILED**: Refresh failed during execution, <br>- **UPSTREAM_FAILED**: Refresh not performed due to an upstream failed refresh, <br>- **CANCELLED**: Refresh was canceled before execution.  | SUCCEEDED | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;action | Describes the type of refresh action performed. One of: <br>- **NO_DATA**: no new data in base tables. Doesn’t apply to the initial refresh of newly created dynamic tables whether or not the base tables have data, <br>- **REINITIALIZE**: base table changed or source table of a cloned dynamic table was refreshed during clone, <br>- **FULL**: Full refresh, because dynamic table contains query elements that are not incremental (see SHOW DYNAMIC TABLE refresh_mode_reason) or because full refresh was cheaper than incremental refresh, <br>- **INCREMENTAL**: normal incremental refresh.  | NO_DATA | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;code | Code representing the current state of the refresh. | SUCCESS | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;completion_target | Time by which this refresh should complete to keep lag under the TARGET_LAG parameter for the dynamic table. | 2024-11-25 06:10:05.695 Z | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;data_timestamp | Transactional timestamp when the refresh was evaluated. | 2024-11-25 06:09:53.695 Z | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;end | Time when the refresh completed. | 2024-11-25 06:09:55.308 Z | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;message | Description of the current state of the refresh. |  | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;start | Time when the refresh job started. | 2024-11-25 06:09:54.978 Z | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;state | Status of the refresh for the dynamic table. The status can be one of the following: <br>- **SCHEDULED**: refresh scheduled, but not yet executed, <br>- **EXECUTING**: refresh in progress, <br>- **SUCCEEDED**: refresh completed successfully, <br>- **FAILED**: refresh failed during execution, <br>- **CANCELLED**: refresh was canceled before execution, <br>- **UPSTREAM_FAILED**: refresh not performed due to an upstream failed refresh.  | SUCCEEDED | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;refresh.&#8203;trigger | Describes the trigger for the refresh. One of: <br>- **SCHEDULED**: normal background refresh to meet target lag or downstream target lag, <br>- **MANUAL**: user/task used ALTER DYNAMIC TABLE <name> REFRESH, <br>- **CREATION**: refresh performed during the creation DDL statement, triggered by the creation of the dynamic table or any consumer dynamic tables.  | SCHEDULED | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;scheduling.&#8203;reason.&#8203;code | Optional reason code if the state is not ACTIVE. | MAINTENANCE | dynamic_tables, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;scheduling.&#8203;reason.&#8203;message | Text description of the reason the dynamic table is not active. Only applies if the state is not active. | Scheduled maintenance | dynamic_tables, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;scheduling.&#8203;state | Scheduling state of the dynamic table. | ACTIVE | dynamic_tables, dynamic_table_graph_history |

### Metrics at the `Dynamic Tables` plugin

| Identifier | Name | Unit | Description | Example | Context Name |
|------------|------|------|-------------|---------|--------------|
| snowflake.&#8203;partitions.&#8203;added | Partitions Added | partitions | The number of partitions added during the refresh. | 5 | dynamic_table_refresh_history |
| snowflake.&#8203;partitions.&#8203;removed | Partitions Removed | partitions | The number of partitions removed during the refresh. | 3 | dynamic_table_refresh_history |
| snowflake.&#8203;rows.&#8203;copied | Rows Copied | rows | The number of rows copied during the refresh. | 75 | dynamic_table_refresh_history |
| snowflake.&#8203;rows.&#8203;deleted | Rows Deleted | rows | The number of rows deleted during the refresh. | 50 | dynamic_table_refresh_history |
| snowflake.&#8203;rows.&#8203;inserted | Rows Inserted | rows | The number of rows inserted during the refresh. | 100 | dynamic_table_refresh_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;max | Maximum Lag Time | seconds | The maximum lag time in seconds of refreshes for this dynamic table. | 83 | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;mean | Mean Lag Time | seconds | The mean lag time (in seconds) of refreshes for this dynamic table. | 26 | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;target.&#8203;time_above | Time Above Target Lag | seconds | The time in seconds when the actual lag was more than the defined target lag. | 151 | dynamic_tables |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;target.&#8203;value | Target Lag Time | seconds | The time in seconds in the retention period or since the last configuration change, when the actual lag was more than the defined target lag. | 60 | dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;lag.&#8203;target.&#8203;within_ratio | Time Within Target Lag Ratio | ratio | The ratio of time in the retention period or since the last configuration change, when actual lag is within the target lag. | 0.999 | dynamic_tables |

### Event timestamps at the `Dynamic Tables` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.table.dynamic.scheduling.resumed_on | dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;graph.&#8203;valid_from | The description of the dynamic table is valid after this time. | 2024-11-20 19:53:47.448 Z | dynamic_table_refresh_history, dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;scheduling.&#8203;resumed_on | Optional timestamp when it was last resumed if dynamic table is ACTIVE. | 2024-11-25 08:09:53.695 Z | dynamic_table_graph_history |
| snowflake.&#8203;table.&#8203;dynamic.&#8203;scheduling.&#8203;suspended_on | Optional timestamp when the dynamic table was suspended. | 2024-11-25 06:09:53.695 Z | dynamic_table_graph_history |

<a name="event_log_semantics_sec"></a>

## The `Event Log` plugin semantics

[Show plugin description](PLUGINS.md#event_log_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Event Log` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;namespace | The name of the database that was specified in the context of the query at compilation. | PROD_DB | event_log_metrics, event_log_spans |
| snowflake.&#8203;query.&#8203;id | The unique identifier for the query. | b1bbaa7f-8144-4e50-947a-b7e9bf7d62d5 | event_log_metrics, event_log_spans |
| snowflake.&#8203;role.&#8203;name | The role used to execute the query. | SYSADMIN | event_log_metrics, event_log_spans |
| snowflake.&#8203;schema.&#8203;name | The name of the schema in which the query was executed. | public | event_log_metrics, event_log_spans |
| snowflake.&#8203;warehouse.&#8203;name | The warehouse used to execute the query. | COMPUTE_WH | event_log_metrics, event_log_spans |

### Metrics at the `Event Log` plugin

| Identifier | Name | Unit | Description | Example | Context Name |
|------------|------|------|-------------|---------|--------------|
| process.&#8203;cpu.&#8203;utilization | Process CPU Utilization | 1 | The percentage of CPU utilization by the process. | 0.015 | event_log_metrics |
| process.&#8203;memory.&#8203;usage | Process Memory Usage | bytes | The total memory usage by the process in bytes. | 34844672 | event_log_metrics |

<a name="event_usage_semantics_sec"></a>

## The `Event Usage` plugin semantics

[Show plugin description](PLUGINS.md#event_usage_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "event_usage"`.

### Metrics at the `Event Usage` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;credits.&#8203;used | Credits Used for Event Table | credits | Number of credits billed for loading data into the event table during the START_TIME and END_TIME window. | 15 |
| snowflake.&#8203;data.&#8203;ingested | Bytes Ingested for Event Table | bytes | Number of bytes of data loaded during the START_TIME and END_TIME window. | 10485760 |

<a name="login_history_semantics_sec"></a>

## The `Login History` plugin semantics

[Show plugin description](PLUGINS.md#login_history_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Login History` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| client.&#8203;ip | The IP address of the client that initiated the event. | 192.168.1.1 | login_history |
| client.&#8203;type | The type of client used to connect to Snowflake, such as JDBC_DRIVER or ODBC_DRIVER. | JDBC_DRIVER | login_history |
| db.&#8203;user | The user who performed the event in the database. | john_doe | login_history, sessions |
| event.&#8203;name | The type of event that occurred, such as: <br>- LOGIN, <br>- LOGOUT.  | LOGIN | login_history |

### Attributes at the `Login History` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| authentication.&#8203;factor.&#8203;first | The first factor used for authentication, typically a password. | password123 | login_history |
| authentication.&#8203;factor.&#8203;second | The second factor used for authentication, such as an MFA token, or NULL if not applicable. | MFA_TOKEN_ABC123 | login_history |
| authentication.&#8203;type | The type of authentication used for the session. | PASSWORD | sessions |
| client.&#8203;application.&#8203;id | The ID of the client application used for the session. | app123 | sessions |
| client.&#8203;application.&#8203;version | The version of the client application used for the session. | 1.0.0 | sessions |
| client.&#8203;build_id | The build ID of the client application. | build123 | sessions |
| client.&#8203;environment | The environment of the client application. | PRODUCTION | sessions |
| client.&#8203;version | The version of the client software used to connect to Snowflake. | 1.0.0 | login_history, sessions |
| db.&#8203;snowflake.&#8203;connection | The name of the connection used by the client, or NULL if the client is not using a connection URL. | connection_1 | login_history |
| error.&#8203;code | The error code associated with the login attempt, if it was not successful. | ERR001 | login_history |
| event.&#8203;id | A unique identifier for the login attempt or the login event associated with the session. | 123456789 | login_history, sessions |
| event.&#8203;related_id | An identifier for a related event, if applicable. | 987654321 | login_history |
| session.&#8203;id | The unique identifier for the session. | session123 | sessions |
| snowflake.&#8203;session.&#8203;closed_reason | The reason the session was closed. | USER_LOGOUT | sessions |
| snowflake.&#8203;session.&#8203;start | The start time of the session. | 1633046400000000000 | sessions |
| status.&#8203;code | The status of the login attempt, indicating success (OK) or failure (ERROR). | OK | login_history |
| status.&#8203;message | A message providing additional details about the status of the login attempt. | Login successful | login_history |

<a name="query_history_semantics_sec"></a>

## The `Query History` plugin semantics

[Show plugin description](PLUGINS.md#query_history_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "query_history"`.

### Dimensions at the `Query History` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;collection.&#8203;name | The name of the table involved in the query. | users |
| db.&#8203;namespace | The name of the database that was specified in the context of the query at compilation. | PROD_DB |
| db.&#8203;operation.&#8203;name | The type of operation performed by the query. | SELECT |
| db.&#8203;snowflake.&#8203;dbs | The databases involved in the query. | PROD_DB |
| db.&#8203;user | Snowflake user who issued the query. | admin |
| snowflake.&#8203;query.&#8203;execution_status | The execution status of the query. | SUCCESS |
| snowflake.&#8203;role.&#8203;name | The role used to execute the query. | SYSADMIN |
| snowflake.&#8203;warehouse.&#8203;name | The warehouse used to execute the query. | COMPUTE_WH |

### Attributes at the `Query History` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| authentication.&#8203;type | The authentication method used for the session. | PASSWORD |
| client.&#8203;application.&#8203;id | The ID of the client application used to execute the query. | app123 |
| client.&#8203;application.&#8203;version | The version of the client application used to execute the query. | 1.0.0 |
| client.&#8203;build_id | The build ID of the client application. | build123 |
| client.&#8203;environment | The environment of the client application. | production |
| client.&#8203;version | The version of the client. | 1.0.0 |
| db.&#8203;query.&#8203;text | The text of the query. | SELECT * FROM users; |
| db.&#8203;snowflake.&#8203;tables | The tables involved in the query. | users |
| db.&#8203;snowflake.&#8203;views | The views involved in the query. | user_view |
| dsoa.&#8203;debug.&#8203;span.&#8203;events.&#8203;added | Internal debug field indicating the number of span events successfully added to the given span. | 5 |
| dsoa.&#8203;debug.&#8203;span.&#8203;events.&#8203;failed | Internal debug field indicating the number of span events that failed to be added to the given span. | 1 |
| event.&#8203;id | The login event ID associated with the query. | login123 |
| session.&#8203;id | The session ID during which the query was executed. | 1234567890 |
| snowflake.&#8203;cluster_number | The cluster number associated with the query. | cluster1 |
| snowflake.&#8203;database.&#8203;id | The unique identifier of the database involved in the query. | db123 |
| snowflake.&#8203;error.&#8203;code | The error code returned by the query, if any. | ERR123 |
| snowflake.&#8203;error.&#8203;message | The error message returned by the query, if any. | Syntax error |
| snowflake.&#8203;query.&#8203;accel_est.&#8203;estimated_query_times | Object that contains the estimated query execution time in seconds for different query acceleration scale factors. If the status for the query is not eligible for query acceleration, this object is empty. | { "scaleFactor1": 10, "scaleFactor2": 5 } |
| snowflake.&#8203;query.&#8203;accel_est.&#8203;status | Indicates whether the query is eligible to benefit from the query acceleration service. Possible values are: eligible, ineligible, accelerated, invalid. | eligible |
| snowflake.&#8203;query.&#8203;accel_est.&#8203;upper_limit_scale_factor | Number of the highest query acceleration scale factor in the estimatedQueryTimes object. If the status for the query is not eligible for query acceleration, this field is set to 0. | 2 |
| snowflake.&#8203;query.&#8203;data_transfer.&#8203;inbound.&#8203;cloud | The cloud provider from which data was transferred inbound. | AWS |
| snowflake.&#8203;query.&#8203;data_transfer.&#8203;inbound.&#8203;region | The region from which data was transferred inbound. | us-west-2 |
| snowflake.&#8203;query.&#8203;data_transfer.&#8203;outbound.&#8203;cloud | The cloud provider to which data was transferred outbound. | AWS |
| snowflake.&#8203;query.&#8203;data_transfer.&#8203;outbound.&#8203;region | The region to which data was transferred outbound. | us-west-2 |
| snowflake.&#8203;query.&#8203;hash | The hash of the query text. | hash123 |
| snowflake.&#8203;query.&#8203;hash_version | The version of the query hash. | v1 |
| snowflake.&#8203;query.&#8203;id | The unique identifier for the query. | b1bbaa7f-8144-4e50-947a-b7e9bf7d62d5 |
| snowflake.&#8203;query.&#8203;is_client_generated | Indicates if the statement was generated by the client. | true |
| snowflake.&#8203;query.&#8203;operator.&#8203;attributes | Information about the operator, depending on the operator type. | { "equality_join_condition": "(T4.C = T1.C)",   "join_type": "INNER" } |
| snowflake.&#8203;query.&#8203;operator.&#8203;id | The operator’s identifier, unique within the query. Values start at 0. | 0 |
| snowflake.&#8203;query.&#8203;operator.&#8203;parent_ids | Identifiers of the parent operators for this operator, or NULL if this is the final operator in the query plan. | [0] |
| snowflake.&#8203;query.&#8203;operator.&#8203;stats | Statistics about the operator (e.g., the number of output rows from the operator). | { "input_rows": 64, "output_rows": 64 } |
| snowflake.&#8203;query.&#8203;operator.&#8203;time | The breakdown of the execution time of the operator: <br>- **overall_percentage**: The percentage of the total query time spent by this operator, <br>- **initialization**: Time spent setting up query processing, <br>- **processing**: Time spent processing the data by the CPU, <br>- **synchronization**: Time spent synchronizing activities between participating processes, <br>- **local_disk_io**: Time during which processing was blocked while waiting for local disk access, <br>- **remote_disk_io**: Time during which processing was blocked while waiting for remote disk access, <br>- **network_communication**: Time during which processing was waiting for network data transfer.  | { "overall_percentage": 50.0,"initialization": 0.5,"processing": 4.0,"synchronization": 0.5,"local_disk_io": 0.2,"remote_disk_io": 0.1,"network_communication": 0.2 } |
| snowflake.&#8203;query.&#8203;operator.&#8203;type | The type of query operator (e.g., TableScan or Filter). | TableScan |
| snowflake.&#8203;query.&#8203;parametrized_hash | The hash of the parameterized query text. | param_hash123 |
| snowflake.&#8203;query.&#8203;parametrized_hash_version | The version of the parameterized query hash. | v1 |
| snowflake.&#8203;query.&#8203;parent_id | The unique identifier for the parent query, if applicable. | parent123 |
| snowflake.&#8203;query.&#8203;retry_cause | The cause for retrying the query, if applicable. | Network issue |
| snowflake.&#8203;query.&#8203;step.&#8203;id | Identifier of the step in the query plan. | 1 |
| snowflake.&#8203;query.&#8203;tag | The tag associated with the query. | tag1 |
| snowflake.&#8203;query.&#8203;transaction_id | The transaction ID associated with the query. | txn123 |
| snowflake.&#8203;query.&#8203;with_operator_stats | Indicates if the query was executed with operator<br>-level statistics enabled. | True |
| snowflake.&#8203;release_version | The release version of Snowflake at the time of query execution. | 5.0 |
| snowflake.&#8203;role.&#8203;type | The type of role used to execute the query. | PRIMARY |
| snowflake.&#8203;schema.&#8203;id | The unique identifier of the schema involved in the query. | schema123 |
| snowflake.&#8203;schema.&#8203;name | The name of the schema involved in the query. | public |
| snowflake.&#8203;secondary_role_stats | Statistics related to secondary roles used during the query execution. | role_stat1 |
| snowflake.&#8203;session.&#8203;closed_reason | The reason the session was closed. | User logout |
| snowflake.&#8203;session.&#8203;start | The start time of the session. | 2024-11-05T21:11:07Z |
| snowflake.&#8203;warehouse.&#8203;cluster.&#8203;number | The cluster number of the warehouse used. | cluster1 |
| snowflake.&#8203;warehouse.&#8203;id | The unique identifier of the warehouse used. | wh123 |
| snowflake.&#8203;warehouse.&#8203;size | The size of the warehouse used. | X-SMALL |
| snowflake.&#8203;warehouse.&#8203;type | The type of warehouse used. | STANDARD |

### Metrics at the `Query History` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;acceleration.&#8203;data.&#8203;scanned | Query Acceleration Bytes Scanned | bytes | Number of bytes scanned by the query acceleration service. | 2097152 |
| snowflake.&#8203;acceleration.&#8203;partitions.&#8203;scanned | Query Acceleration Partitions Scanned | partitions | Number of partitions scanned by the query acceleration service. | 50 |
| snowflake.&#8203;acceleration.&#8203;scale_factor.&#8203;max | Query Acceleration Upper Limit Scale Factor | factor | Upper limit scale factor that a query would have benefited from. | 4 |
| snowflake.&#8203;credits.&#8203;cloud_services | Cloud Services Credits Used | credits | Number of credits used for cloud services. | 10 |
| snowflake.&#8203;data.&#8203;deleted | Bytes Deleted | bytes | Number of bytes deleted by the query. | 1048576 |
| snowflake.&#8203;data.&#8203;read.&#8203;from_result | Bytes Read from Result | bytes | Number of bytes read from a result object. | 1048576 |
| snowflake.&#8203;data.&#8203;scanned | Bytes Scanned | bytes | Number of bytes scanned by this statement. | 10485760 |
| snowflake.&#8203;data.&#8203;scanned_from_cache | Percentage Scanned from Cache | percent | The percentage of data scanned from the local disk cache. The value ranges from 0.0 to 1.0. Multiply by 100 to get a true percentage. | 75 |
| snowflake.&#8203;data.&#8203;sent_over_the_network | Bytes Sent Over the Network | bytes | Volume of data sent over the network. | 524288 |
| snowflake.&#8203;data.&#8203;spilled.&#8203;local | Bytes Spilled to Local Storage | bytes | Volume of data spilled to local disk. | 1048576 |
| snowflake.&#8203;data.&#8203;spilled.&#8203;remote | Bytes Spilled to Remote Storage | bytes | Volume of data spilled to remote disk. | 2097152 |
| snowflake.&#8203;data.&#8203;transferred.&#8203;inbound | Inbound Data Transfer Bytes | bytes | Number of bytes transferred in statements that load data from another region and/or cloud. | 10485760 |
| snowflake.&#8203;data.&#8203;transferred.&#8203;outbound | Outbound Data Transfer Bytes | bytes | Number of bytes transferred in statements that unload data to another region and/or cloud. | 5242880 |
| snowflake.&#8203;data.&#8203;written | Bytes Written | bytes | Number of bytes written (e.g. when loading into a table). | 2097152 |
| snowflake.&#8203;data.&#8203;written_to_result | Bytes Written to Result | bytes | Number of bytes written to a result object. | 1048576 |
| snowflake.&#8203;external_functions.&#8203;data.&#8203;received | External Function Total Received Bytes | bytes | The total number of bytes that this query received from all calls to all remote services. | 1048576 |
| snowflake.&#8203;external_functions.&#8203;data.&#8203;sent | External Function Total Sent Bytes | bytes | The total number of bytes that this query sent in all calls to all remote services. | 524288 |
| snowflake.&#8203;external_functions.&#8203;invocations | External Function Total Invocations | count | The aggregate number of times that this query called remote services. For important details, see the Usage Notes. | 5 |
| snowflake.&#8203;external_functions.&#8203;rows.&#8203;received | External Function Total Received Rows | rows | The total number of rows that this query received from all calls to all remote services. | 1000 |
| snowflake.&#8203;external_functions.&#8203;rows.&#8203;sent | External Function Total Sent Rows | rows | The total number of rows that this query sent in all calls to all remote services. | 500 |
| snowflake.&#8203;load.&#8203;used | Query Load Percent | percent | The approximate percentage of active compute resources in the warehouse for this query execution. | 85 |
| snowflake.&#8203;partitions.&#8203;scanned | Partitions Scanned | partitions | Number of micro<br>-partitions scanned. | 100 |
| snowflake.&#8203;partitions.&#8203;total | Partitions Total | partitions | Total micro<br>-partitions of all tables included in this query. | 500 |
| snowflake.&#8203;rows.&#8203;deleted | Rows Deleted | rows | Number of rows deleted by the query. | 500 |
| snowflake.&#8203;rows.&#8203;inserted | Rows Inserted | rows | Number of rows inserted by the query. | 1000 |
| snowflake.&#8203;rows.&#8203;unloaded | Rows Unloaded | rows | Number of rows unloaded during data export. | 1000 |
| snowflake.&#8203;rows.&#8203;updated | Rows Updated | rows | Number of rows updated by the query. | 300 |
| snowflake.&#8203;rows.&#8203;written_to_result | Rows Written to Result | rows | Number of rows written to a result object. For CREATE TABLE AS SELECT (CTAS) and all DML operations, this result is 1;. | 1 |
| snowflake.&#8203;time.&#8203;child_queries_wait | Child Queries Wait Time | ms | Time (in milliseconds) to complete the cached lookup when calling a memoizable function. | 200 |
| snowflake.&#8203;time.&#8203;compilation | Compilation Time | ms | Compilation time (in milliseconds) | 5000 |
| snowflake.&#8203;time.&#8203;execution | Execution Time | ms | Execution time (in milliseconds) | 100000 |
| snowflake.&#8203;time.&#8203;fault_handling | Fault Handling Time | ms | Total execution time (in milliseconds) for query retries caused by errors that are not actionable. | 1500 |
| snowflake.&#8203;time.&#8203;list_external_files | List External Files Time | ms | Time (in milliseconds) spent listing external files. | 300 |
| snowflake.&#8203;time.&#8203;queued.&#8203;overload | Queued Overload Time | ms | Time (in milliseconds) spent in the warehouse queue, due to the warehouse being overloaded by the current query workload. | 1500 |
| snowflake.&#8203;time.&#8203;queued.&#8203;provisioning | Queued Provisioning Time | ms | Time (in milliseconds) spent in the warehouse queue, waiting for the warehouse compute resources to provision, due to warehouse creation, resume, or resize. | 3000 |
| snowflake.&#8203;time.&#8203;repair | Queued Repair Time | ms | Time (in milliseconds) spent in the warehouse queue, waiting for compute resources in the warehouse to be repaired. | 500 |
| snowflake.&#8203;time.&#8203;retry | Query Retry Time | ms | Total execution time (in milliseconds) for query retries caused by actionable errors. | 2000 |
| snowflake.&#8203;time.&#8203;total_elapsed | Total Elapsed Time | ms | Elapsed time (in milliseconds). | 120000 |
| snowflake.&#8203;time.&#8203;transaction_blocked | Transaction Blocked Time | ms | Time (in milliseconds) spent blocked by a concurrent DML. | 1000 |

<a name="resource_monitors_semantics_sec"></a>

## The `Resource Monitors` plugin semantics

[Show plugin description](PLUGINS.md#resource_monitors_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "resource_monitors"`.

### Dimensions at the `Resource Monitors` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;resource_monitor.&#8203;name | The name of the resource monitor. | RM_MONITOR |
| snowflake.&#8203;warehouse.&#8203;name | The name of the warehouse. | COMPUTE_WH |

### Attributes at the `Resource Monitors` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;budget.&#8203;name | The name of the budget associated with the warehouse. | BUDGET_2024 |
| snowflake.&#8203;credits.&#8203;quota | The credit quota of the resource monitor. | 1000 |
| snowflake.&#8203;credits.&#8203;quota.&#8203;remaining | The remaining credits of the resource monitor. | 500 |
| snowflake.&#8203;credits.&#8203;quota.&#8203;used | The credits used by the resource monitor. | 500 |
| snowflake.&#8203;resource_monitor.&#8203;frequency | The frequency of the resource monitor. | DAILY |
| snowflake.&#8203;resource_monitor.&#8203;is_active | Indicates if the resource monitor is active. | true |
| snowflake.&#8203;resource_monitor.&#8203;level | The level of the resource monitor. | ACCOUNT |
| snowflake.&#8203;warehouse.&#8203;execution_state | The execution state of the warehouse. | RUNNING |
| snowflake.&#8203;warehouse.&#8203;has_query_acceleration_enabled | Indicates if query acceleration is enabled for the warehouse. | true |
| snowflake.&#8203;warehouse.&#8203;is_auto_resume | Indicates if the warehouse is set to auto<br>-resume. | true |
| snowflake.&#8203;warehouse.&#8203;is_auto_suspend | Indicates if the warehouse is set to auto<br>-suspend. | true |
| snowflake.&#8203;warehouse.&#8203;is_current | Indicates if the warehouse is the current warehouse. | true |
| snowflake.&#8203;warehouse.&#8203;is_default | Indicates if the warehouse is the default warehouse. | true |
| snowflake.&#8203;warehouse.&#8203;is_unmonitored | Indicates if the warehouse is NOT monitored by a resource monitor. | true |
| snowflake.&#8203;warehouse.&#8203;owner | The owner of the warehouse. | admin |
| snowflake.&#8203;warehouse.&#8203;owner.&#8203;role_type | The role type of the warehouse owner. | SYSADMIN |
| snowflake.&#8203;warehouse.&#8203;scaling_policy | The scaling policy of the warehouse. | STANDARD |
| snowflake.&#8203;warehouse.&#8203;size | The size of the warehouse. | X-SMALL |
| snowflake.&#8203;warehouse.&#8203;type | The type of the warehouse. | STANDARD |
| snowflake.&#8203;warehouses.&#8203;names | The names of the warehouses monitored. | COMPUTE_WH |

### Metrics at the `Resource Monitors` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;acceleration.&#8203;scale_factor.&#8203;max | Query Acceleration Max Scale Factor | factor | Maximal scale factor for query acceleration in the given warehouse | 2 |
| snowflake.&#8203;compute.&#8203;available | Percentage Available | percent | Percentage of available resources in given warehouse. | 60 |
| snowflake.&#8203;compute.&#8203;other | Percentage Other | percent | Percentage of other resources in given warehouse | 10 |
| snowflake.&#8203;compute.&#8203;provisioning | Percentage Provisioning | percent | Percentage of provisioning resources in given warehouse. | 20 |
| snowflake.&#8203;compute.&#8203;quiescing | Percentage Quiescing | percent | Percentage of quiescing resources in given warehouse. | 10 |
| snowflake.&#8203;credits.&#8203;quota | Credits Quota | credits | Total number of credits allowed for the given resource monitor | 1000 |
| snowflake.&#8203;credits.&#8203;quota.&#8203;remaining | Credits Remaining | credits | Number of credits remaining for the given resource monitor | 250 |
| snowflake.&#8203;credits.&#8203;quota.&#8203;used | Credits Used | credits | Number of credits used by the given resource monitor | 750 |
| snowflake.&#8203;credits.&#8203;quota.&#8203;used_pct | Percentage Quota Used | percent | Percentage of quota used by given resource monitor | 75 |
| snowflake.&#8203;queries.&#8203;queued | Queued Queries | queries | Current number of queued queries in the given warehouse | 5 |
| snowflake.&#8203;queries.&#8203;running | Running Queries | queries | Current number of running queries in the given warehouse | 15 |
| snowflake.&#8203;resource_monitor.&#8203;warehouses | Warehouses Count | warehouses | Number of warehouses monitored by the given resource monitor | 5 |
| snowflake.&#8203;warehouse.&#8203;clusters.&#8203;max | Maximum Cluster Count | clusters | Maximal number of clusters in the given warehouse | 10 |
| snowflake.&#8203;warehouse.&#8203;clusters.&#8203;min | Minimum Cluster Count | clusters | Minimal number of clusters in the given warehouse | 1 |
| snowflake.&#8203;warehouse.&#8203;clusters.&#8203;started | Started Clusters | clusters | Current number of started clusters in the given warehouse | 3 |

### Event timestamps at the `Resource Monitors` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.warehouse.resumed_on |
| snowflake.&#8203;resource_monitor.&#8203;created_on | The timestamp when the resource monitor was created. | 2024-10-15 12:34:56.789 |
| snowflake.&#8203;resource_monitor.&#8203;end_time | The timestamp when the resource monitor ended. | 2024-11-30 23:59:59.999 |
| snowflake.&#8203;resource_monitor.&#8203;start_time | The timestamp when the resource monitor started. | 2024-11-01 00:00:00.000 |
| snowflake.&#8203;warehouse.&#8203;created_on | The timestamp when the warehouse was created. | 2024-09-01 08:00:00.000 |
| snowflake.&#8203;warehouse.&#8203;resumed_on | The timestamp when the warehouse was last resumed. | 2024-11-15 09:00:00.000 |
| snowflake.&#8203;warehouse.&#8203;updated_on | The timestamp when the warehouse was last updated. | 2024-11-10 14:30:00.000 |

<a name="shares_semantics_sec"></a>

## The `Shares` plugin semantics

[Show plugin description](PLUGINS.md#shares_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Shares` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;collection.&#8203;name | Name of the shared Snowflake table. | SALES_DATA | inbound_shares |
| db.&#8203;namespace | Name of the database used to store shared data. | DEV_DB | outbound_shares, inbound_shares |
| snowflake.&#8203;grant.&#8203;name | Name of the grant to a share. | READ_ACCESS | outbound_shares |
| snowflake.&#8203;schema.&#8203;name | Name of the schema where the table is located. | PUBLIC | inbound_shares |
| snowflake.&#8203;share.&#8203;name | Name of the share. | SAMPLE_DATA | outbound_shares, inbound_shares |

### Attributes at the `Shares` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| snowflake.&#8203;data.&#8203;rows | Number of rows in the table. | 20000 | inbound_shares |
| snowflake.&#8203;data.&#8203;size | Number of bytes accessed by a scan of the table. | 800000 | inbound_shares |
| snowflake.&#8203;grant.&#8203;by | Shows the name of the account which made the grant. | ACCOUNTADMIN | outbound_shares |
| snowflake.&#8203;grant.&#8203;grantee | Shows the grantee account name. | PARTNER_ACCOUNT | outbound_shares |
| snowflake.&#8203;grant.&#8203;on | Shows on what type of object the grant was made. | DATABASE | outbound_shares |
| snowflake.&#8203;grant.&#8203;option | Indicates if grant option is available. | False | outbound_shares |
| snowflake.&#8203;grant.&#8203;privilege | Shows the type of privilege granted. | USAGE | outbound_shares |
| snowflake.&#8203;grant.&#8203;to | Shows to what the grant was made. | SHARE | outbound_shares |
| snowflake.&#8203;share.&#8203;has_db_deleted | Indicates whether DB related to that INBOUND share has been deleted. | False | inbound_shares |
| snowflake.&#8203;share.&#8203;has_details_reported | Indicates whether or not details on this share should be reported. | False | inbound_shares |
| snowflake.&#8203;share.&#8203;is_secure_objects_only | Indicates if the share is only for secure objects. | True | outbound_shares, inbound_shares |
| snowflake.&#8203;share.&#8203;kind | Indicates the type of share. | OUTBOUND | outbound_shares, inbound_shares |
| snowflake.&#8203;share.&#8203;listing_global_name | Global name of the share listing. | GLOBAL_SHARE_NAME | outbound_shares, inbound_shares |
| snowflake.&#8203;share.&#8203;owner | Shows the account owning the share. | ACCOUNTADMIN | outbound_shares, inbound_shares |
| snowflake.&#8203;share.&#8203;shared_from | Shows the owner account of the share. | SNOWFLAKE | outbound_shares, inbound_shares |
| snowflake.&#8203;share.&#8203;shared_to | Shows the account the share was made to. | PARTNER_ACCOUNT | outbound_shares, inbound_shares |
| snowflake.&#8203;table.&#8203;clustering_key | Clustering key for the table. | DATE | inbound_shares |
| snowflake.&#8203;table.&#8203;comment | Comment for this table. | The tables defined in this database that are accessible to the current user's role. | inbound_shares |
| snowflake.&#8203;table.&#8203;is_auto_clustering_on | Indicates whether automatic clustering is enabled for the table. | YES | inbound_shares |
| snowflake.&#8203;table.&#8203;is_dynamic | Indicates whether the table is a dynamic table. | NO | inbound_shares |
| snowflake.&#8203;table.&#8203;is_hybrid | Indicates whether this is a hybrid table. | False | inbound_shares |
| snowflake.&#8203;table.&#8203;is_iceberg | Indicates whether the table is an Iceberg table. | NO | inbound_shares |
| snowflake.&#8203;table.&#8203;is_temporary | Indicates whether this is a temporary table. | NO | inbound_shares |
| snowflake.&#8203;table.&#8203;is_transient | Indicates whether this is a transient table. | NO | inbound_shares |
| snowflake.&#8203;table.&#8203;last_ddl_by | The current username for the user who executed the last DDL operation. | DBA_USER | inbound_shares |
| snowflake.&#8203;table.&#8203;owner | Name of the role that owns the table. | ACCOUNTADMIN | inbound_shares |
| snowflake.&#8203;table.&#8203;retention_time | Number of days that historical data is retained for Time Travel. | 5 | inbound_shares |
| snowflake.&#8203;table.&#8203;type | Indicates the table type. | BASE TABLE | inbound_shares |

### Event timestamps at the `Shares` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.grant.created_on | outbound_shares, inbound_shares |
| snowflake.&#8203;grant.&#8203;created_on | Timestamp of the date of creating the grant. | 1639051180946000000 | outbound_shares |
| snowflake.&#8203;share.&#8203;created_on | Timestamp of the date of creating the share. | 1639051180714000000 | outbound_shares, inbound_shares |
| snowflake.&#8203;table.&#8203;created_on | Creation time of the table. | 1649940827875000000 | inbound_shares |
| snowflake.&#8203;table.&#8203;ddl | Timestamp of the last DDL operation performed on the table or view. | 1639940327875000000 | inbound_shares |
| snowflake.&#8203;table.&#8203;update | Date and time the object was last altered by a DML, DDL, or background metadata operation. | 1649962827875000000 | inbound_shares |

<a name="tasks_semantics_sec"></a>

## The `Tasks` plugin semantics

[Show plugin description](PLUGINS.md#tasks_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Tasks` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;namespace | The name of the database. | PROD_DB | serverless_tasks, task_versions, task_history |
| snowflake.&#8203;schema.&#8203;name | The name of the schema. | public | serverless_tasks, task_versions, task_history |
| snowflake.&#8203;task.&#8203;name | The name of the task. | daily_backup_task | serverless_tasks, task_versions, task_history |
| snowflake.&#8203;warehouse.&#8203;name | The name of the warehouse. | COMPUTE_WH | task_versions |

### Attributes at the `Tasks` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;query.&#8203;text | The text of the query. | SELECT * FROM users; | task_versions |
| snowflake.&#8203;database.&#8203;id | The unique identifier for the database. | db123 | serverless_tasks, task_versions |
| snowflake.&#8203;error.&#8203;code | The error code returned by the task. | ERR123 | task_history |
| snowflake.&#8203;error.&#8203;message | The error message returned by the task. | Syntax error | task_history |
| snowflake.&#8203;query.&#8203;hash | The hash of the query. | hash123 | task_history |
| snowflake.&#8203;query.&#8203;hash_version | The version of the query hash. | v1 | task_history |
| snowflake.&#8203;query.&#8203;id | The unique identifier for the query. | query123 | task_history |
| snowflake.&#8203;query.&#8203;parametrized_hash | The parameterized hash of the query. | param_hash123 | task_history |
| snowflake.&#8203;query.&#8203;parametrized_hash_version | The version of the parameterized query hash. | v1 | task_history |
| snowflake.&#8203;schema.&#8203;id | The unique identifier for the schema. | schema123 | serverless_tasks, task_versions |
| snowflake.&#8203;task.&#8203;condition | The condition text of the task. | status = 'SUCCESS' | task_versions, task_history |
| snowflake.&#8203;task.&#8203;config | The configuration of the task. | config123 | task_history |
| snowflake.&#8203;task.&#8203;config.&#8203;allow_overlap | Indicates if overlapping execution is allowed. | true | task_versions |
| snowflake.&#8203;task.&#8203;end_time | The end time of the task. | 1633046700000000000 | serverless_tasks |
| snowflake.&#8203;task.&#8203;error_integration | The error integration for the task. | error_integration123 | task_versions |
| snowflake.&#8203;task.&#8203;graph.&#8203;root_id | The root ID of the task graph. | root123 | task_versions, task_history |
| snowflake.&#8203;task.&#8203;graph.&#8203;version | The version of the task graph. | v1 | task_versions, task_history |
| snowflake.&#8203;task.&#8203;id | The unique identifier for the task. | task123 | serverless_tasks, task_versions |
| snowflake.&#8203;task.&#8203;instance_id | The unique identifier for the task instance. | instance123 | serverless_tasks |
| snowflake.&#8203;task.&#8203;last_committed_on | The last committed time of the task. | 1633046400000000000 | task_versions |
| snowflake.&#8203;task.&#8203;last_suspended_on | The last suspended time of the task. | 1633046700000000000 | task_versions |
| snowflake.&#8203;task.&#8203;owner | The owner of the task. | admin | task_versions |
| snowflake.&#8203;task.&#8203;predecessors | The predecessors of the task. | taskA, taskB | task_versions |
| snowflake.&#8203;task.&#8203;run.&#8203;attempt | The attempt number of the task run. | 1 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;completed_time | The completed time of the task run. | 1633046700000000000 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;group_id | The group ID of the task run. | group123 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;id | The unique identifier for the task run. | run123 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;return_value | The return value of the task run. | 0 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;scheduled_from | The source from which the task was scheduled. | CRON | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;scheduled_time | The scheduled time of the task run. | 1633046400000000000 | task_history |
| snowflake.&#8203;task.&#8203;run.&#8203;state | The state of the task run. | RUNNING | task_history |
| snowflake.&#8203;task.&#8203;schedule | The schedule of the task. | `0 0 * * *` | task_versions |
| snowflake.&#8203;task.&#8203;start_time | The start time of the task. | 1633046400000000000 | serverless_tasks |

### Metrics at the `Tasks` plugin

| Identifier | Name | Unit | Description | Example | Context Name |
|------------|------|------|-------------|---------|--------------|
| snowflake.&#8203;credits.&#8203;used | Serverless Tasks Credits Used | credits | Number of credits billed for serverless task usage during the START_TIME and END_TIME window. | 10 | serverless_tasks |

### Event timestamps at the `Tasks` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| snowflake.&#8203;event.&#8203;trigger | Additionally to sending logs, each entry in `EVENT_TIMESTAMPS` is sent as event with key set to `snowflake.event.trigger`, value to key from `EVENT_TIMESTAMPS` and `timestamp` set to the key value. | snowflake.task.graph.version.created_on | task_versions |
| snowflake.&#8203;task.&#8203;graph.&#8203;version.&#8203;created_on | The creation time of the task graph version. | 1633046400000000000 | task_versions |

<a name="trust_center_semantics_sec"></a>

## The `Trust Center` plugin semantics

[Show plugin description](PLUGINS.md#trust_center_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "trust_center"`.

### Dimensions at the `Trust Center` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| event.&#8203;category | The category of the event, such as 'Warning' or 'Vulnerability management', based on the severity. | Warning |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;id | The unique identifier for the scanner used in the Trust Center. | scanner123 |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;package.&#8203;id | The unique identifier for the scanner package used in the Trust Center. | package123 |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;type | The type of scanner used in the Trust Center, such as 'CIS Benchmarks' or 'Threat Intelligence'. | CIS Benchmarks |
| vulnerability.&#8203;risk.&#8203;level | The risk level of the vulnerability, such as LOW, MEDIUM, HIGH, or CRITICAL. | HIGH |

### Attributes at the `Trust Center` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| error.&#8203;code | The error code associated with the scanner, if any. | ERR001 |
| event.&#8203;id | A unique identifier for the security event. | event123 |
| event.&#8203;kind | The kind of event, in this case, 'SECURITY_EVENT'. | SECURITY_EVENT |
| snowflake.&#8203;entity.&#8203;details | Additional details about the entity involved in the event. | Contains user data |
| snowflake.&#8203;entity.&#8203;id | The unique identifier for the entity involved in the event. | entity123 |
| snowflake.&#8203;entity.&#8203;name | The name of the entity involved in the event. | User Table |
| snowflake.&#8203;entity.&#8203;type | The type of entity involved in the event, such as a table, view, or user. | table |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;description | A short description of the scanner used in the Trust Center. | Ensure monitoring and alerting exist for password sign-in without MFA |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;name | The name of the scanner used in the Trust Center. | 2.4 |
| snowflake.&#8203;trust_center.&#8203;scanner.&#8203;package.&#8203;name | The name of the scanner package used in the Trust Center. | CIS Package |
| status.&#8203;message | The name and description of the scanner, providing additional details about the status. | 2.4 Ensure monitoring and alerting exist for password sign-in without MFA |

### Metrics at the `Trust Center` plugin

| Identifier | Name | Unit | Description | Example |
|------------|------|------|-------------|---------|
| snowflake.&#8203;trust_center.&#8203;findings | Trust Center Findings Count | count | The total number of findings at risk identified by the scanner. | 10 |

<a name="users_semantics_sec"></a>

## The `Users` plugin semantics

[Show plugin description](PLUGINS.md#users_info_sec)

All telemetry delivered by this plugin is reported as `dsoa.run.context == "users"`.

### Dimensions at the `Users` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| db.&#8203;user | Snowflake user who issued the query. | admin |

### Attributes at the `Users` plugin

| Identifier | Description | Example |
|------------|-------------|---------|
| snowflake.&#8203;user.&#8203;bypass_mfa_until | The time until which the user can bypass MFA. | 2024-11-06T00:00:00Z |
| snowflake.&#8203;user.&#8203;comment | Any comments associated with the user. | New user account |
| snowflake.&#8203;user.&#8203;created_on | The creation time of the user account. | 1651830381846000000 |
| snowflake.&#8203;user.&#8203;default.&#8203;namespace | The default namespace for the user. | PUBLIC |
| snowflake.&#8203;user.&#8203;default.&#8203;role | The default role for the user. | SYSADMIN |
| snowflake.&#8203;user.&#8203;default.&#8203;secondary_role | The default secondary role for the user. | SECURITYADMIN |
| snowflake.&#8203;user.&#8203;default.&#8203;warehouse | The default warehouse for the user. | COMPUTE_WH |
| snowflake.&#8203;user.&#8203;deleted_on | The deletion time of the user account, if applicable. | 1615219846384000000 |
| snowflake.&#8203;user.&#8203;display_name | The display name of the user. | John Doe |
| snowflake.&#8203;user.&#8203;email | The email address of the user. | `jdoe@example.com` |
| snowflake.&#8203;user.&#8203;expires_at | The expiration date of the user account. | 1620213179885000000 |
| snowflake.&#8203;user.&#8203;ext_authn.&#8203;duo | Indicates if Duo authentication is enabled for the user. | true |
| snowflake.&#8203;user.&#8203;ext_authn.&#8203;uid | The external authentication UID for the user. | ext123 |
| snowflake.&#8203;user.&#8203;has_password | Indicates if the user has a password set. | true |
| snowflake.&#8203;user.&#8203;id | The unique identifier for the user. | 12345 |
| snowflake.&#8203;user.&#8203;is_disabled | Indicates if the user account is disabled. | false |
| snowflake.&#8203;user.&#8203;is_locked | Indicates if the user account is locked by Snowflake. | false |
| snowflake.&#8203;user.&#8203;last_success_login | The last successful login time of the user. | 1732181350954000000 |
| snowflake.&#8203;user.&#8203;locked_until_time | The time until which the user account is locked. | 1615479617866000000 |
| snowflake.&#8203;user.&#8203;must_change_password | Indicates if the user must change their password. | true |
| snowflake.&#8203;user.&#8203;name | The login name of the user. | jdoe |
| snowflake.&#8203;user.&#8203;name.&#8203;first | The first name of the user. | John |
| snowflake.&#8203;user.&#8203;name.&#8203;last | The last name of the user. | Doe |
| snowflake.&#8203;user.&#8203;owner | The role that owns the user account. | ACCOUNTADMIN |
| snowflake.&#8203;user.&#8203;password_last_set_time | The last time the user's password was set. | 1615219848053000000 |
| snowflake.&#8203;user.&#8203;privilege | Name of the privilege and type of object this privilege granted on to the user or role. Composed as `privilege:granted_on_object`. | CREATE SERVICE:SCHEMA |
| snowflake.&#8203;user.&#8203;privilege.&#8203;granted_by | Array of all roles which granted grants to a user for a privilege. | ['ACCOUNTADMIN'] |
| snowflake.&#8203;user.&#8203;privilege.&#8203;grants_on | List of all objects of given type on which given privilege was given; both object type and privilege are reported as `snowflake.user.privilege` | ['TRUST_CENTER_ADMIN', 'COMPUTE_WH'] |
| snowflake.&#8203;user.&#8203;privilege.&#8203;last_altered | Nanosecond timestamp of the last alteration to user's privileges. | 1732181350954000000 |
| snowflake.&#8203;user.&#8203;roles.&#8203;all | Comma separated list of all roles granted to a user. | SNOWFLAKE_FINANCE,MONITORING |
| snowflake.&#8203;user.&#8203;roles.&#8203;direct | List of all direct roles granted to user. | ['DEVOPS_ROLE', 'SYSADMIN', 'ACCOUNTADMIN'] |
| snowflake.&#8203;user.&#8203;roles.&#8203;direct.&#8203;removed | Name of the role that was revoked from user. | ACCOUNTADMIN |
| snowflake.&#8203;user.&#8203;roles.&#8203;direct.&#8203;removed_on | Nanosecond timestamp of the last deletion of a direct role to a user. | 1718260900411000000 |
| snowflake.&#8203;user.&#8203;roles.&#8203;granted_by | Array of admin roles that were used to grant current list of user roles. | ['DEMIGOD', 'SECURITYADMIN', 'ACCOUNTADMIN'] |
| snowflake.&#8203;user.&#8203;roles.&#8203;last_altered | Nanosecond timestamp of last alteration of roles granted to user. | 1718260900411000000 |
| snowflake.&#8203;user.&#8203;type | Specifies the type of user | LEGACY_SERVICE |

<a name="warehouse_usage_semantics_sec"></a>

## The `Warehouse Usage` plugin semantics

[Show plugin description](PLUGINS.md#warehouse_usage_info_sec)

This plugin delivers telemetry in multiple contexts. To filter by one of plugin's context names (reported as `dsoa.run.context`), please check the `Context Name` column below.

### Dimensions at the `Warehouse Usage` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| snowflake.&#8203;warehouse.&#8203;event.&#8203;name | The name of the event. | WAREHOUSE_START | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;event.&#8203;state | The state of the event, such as STARTED or COMPLETED. | STARTED | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;name | The name of the warehouse. | COMPUTE_WH | warehouse_usage, warehouse_usage_load, warehouse_usage_metering |

### Attributes at the `Warehouse Usage` plugin

| Identifier | Description | Example | Context Name |
|------------|-------------|---------|--------------|
| db.&#8203;user | The user who initiated the event. | admin | warehouse_usage |
| snowflake.&#8203;query.&#8203;id | The unique identifier for the query associated with the event. | query123 | warehouse_usage |
| snowflake.&#8203;role.&#8203;name | The role name associated with the event. | SYSADMIN | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;cluster.&#8203;number | The number of the cluster within the warehouse. | 1 | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;clusters.&#8203;count | The number of clusters in the warehouse. | 2 | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;event.&#8203;reason | The reason for the event. | USER_REQUEST | warehouse_usage |
| snowflake.&#8203;warehouse.&#8203;id | The unique identifier for the warehouse. | wh123 | warehouse_usage, warehouse_usage_load, warehouse_usage_metering |
| snowflake.&#8203;warehouse.&#8203;size | The size of the warehouse. | X-SMALL | warehouse_usage |

### Metrics at the `Warehouse Usage` plugin

| Identifier | Name | Unit | Description | Example | Context Name |
|------------|------|------|-------------|---------|--------------|
| snowflake.&#8203;credits.&#8203;cloud_services | Cloud Services Credits Used | credits | The number of credits used for cloud services. | 2 | warehouse_usage_metering |
| snowflake.&#8203;credits.&#8203;compute | Compute Credits Used | credits | The number of credits used for compute. | 8 | warehouse_usage_metering |
| snowflake.&#8203;credits.&#8203;used | Total Credits Used | credits | The total number of credits used by the warehouse. | 10 | warehouse_usage_metering |
| snowflake.&#8203;load.&#8203;blocked | Average Blocked Queries | count | The average number of queries blocked by a transaction lock. | 0 | warehouse_usage_load |
| snowflake.&#8203;load.&#8203;queued.&#8203;overloaded | Average Queued Queries (Load) | count | The average number of queries queued due to load. | 2 | warehouse_usage_load |
| snowflake.&#8203;load.&#8203;queued.&#8203;provisioning | Average Queued Queries (Provisioning) | count | The average number of queries queued due to provisioning. | 1 | warehouse_usage_load |
| snowflake.&#8203;load.&#8203;running | Average Running Queries | count | The average number of running queries. | 5 | warehouse_usage_load |

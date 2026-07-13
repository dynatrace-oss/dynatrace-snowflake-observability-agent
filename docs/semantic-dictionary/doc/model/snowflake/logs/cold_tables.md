<!-- model snowflake.logs.cold_tables -->
<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->
## Snowflake cold tables log records

Log records emitted by the DSOA cold_tables plugin.

### Query

Fetch the 100 most recent DSOA cold_tables plugin log entries from Grail.

*Davis CoPilot description: Search for all cold_tables plugin logs from the Snowflake observability agent.*

```sql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "cold_tables"
| sort timestamp desc
| limit 100
```

---
Fetch the 50 most recent tables classified as COLD by the cold_tables plugin.

*Davis CoPilot description: Find Snowflake tables currently classified as cold.*

```sql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "cold_tables"
| filter snowflake.table.cold_status == "COLD"
| sort timestamp desc
| limit 50
```

---
Rank Snowflake tables by how long they have been idle.

*Davis CoPilot description: Find the Snowflake tables that have been idle the longest.*

```sql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "cold_tables"
| filter isNotNull(snowflake.table.full_name)
| summarize { idle_days = takeMax(toLong(snowflake.table.days_since_last_access)) }, by: { snowflake.table.full_name }
| sort idle_days desc
| limit 25
```

Snowflake cold tables log records implements the following interfaces: *i.dsoa_resource*

### DSOA resource fields

Fields present on all DSOA telemetry records. Synced with config.py RESOURCE_ATTRIBUTES.

| Attribute  | Type | Description  | Examples  |
|---|---|---|---|
| [`db.system`](../../../fields/db.md) | string | ![Experimental](https://img.shields.io/badge/-experimental-orange)<br>An identifier for the database management system (DBMS) product being used. See below for a list of well-known identifiers. [1] | `mongodb`; `mysql` |
| `deployment.environment` | string | ![Resource](https://img.shields.io/badge/-resource-grey) **![Deprecated](https://img.shields.io/badge/-deprecated-red)<br>Use deployment.environment.name instead.**<br>Deprecated alias for deployment.environment.name. The deployment environment, e.g., production, staging, or development. Will be removed in release 1.3.0. [2] | `PROD` |
| `deployment.environment.name` | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>The deployment environment name (OTel semconv canonical field), e.g., production, staging, or development. Emitted alongside deployment.environment during the deprecation window. [3] | `PROD` |
| `deployment.environment.tag` | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>Optional tag for the deployment environment in multitenancy mode [4] | `SA080` |
| `dsoa.run.context` | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>The name of the Dynatrace Snowflake Observability Agent context (part of plugin) used to produce the telemetry (logs, traces, metrics, or events). In case of multiple contexts within the same plugin, this helps differentiate between them. If plugin delivers only one context, this field will have the same value as the plugin name. [5] | `users_all_roles` |
| `dsoa.run.id` | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>Unique ID of each execution of the Dynatrace Snowflake Observability Agent plugin. It can be used to differentiate between telemetry produced between two executions, e.g., to calculate the change in the system. [6] | `4aa7c76c-e98c-4b8b-a5b3-a8a721bbde2d` |
| `dsoa.run.plugin` | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>The name of the DSOA plugin that produced this telemetry. Use to filter all telemetry from a specific plugin (e.g., 'query\_history', 'warehouse\_usage'). Distinct from dsoa.run.context, which may represent a sub-context within a plugin. [7] | `users` |
| [`host.name`](../../../fields/host.md) | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Experimental](https://img.shields.io/badge/-experimental-orange)<br>The host name as determined on the data source (for instance, OneAgent, extensions or OpenTelemetry).<br/>Important: This is not the name of the host entity, which can be modified based on naming rules. [8]<br>Tags: `permission` | `ip-10-178-54-32.ec2.internal` |
| [`service.name`](../../../fields/service.md) | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Stable](https://img.shields.io/badge/-stable-lightgreen)<br>The logical name of the service. [9] | `shoppingcart` |
| [`telemetry.exporter.name`](../../../fields/telemetry.md) | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Experimental](https://img.shields.io/badge/-experimental-orange)<br>The exporter name. [10] | `odin` |
| [`telemetry.exporter.version`](../../../fields/telemetry.md) | string | ![Resource](https://img.shields.io/badge/-resource-grey) ![Experimental](https://img.shields.io/badge/-experimental-orange)<br>The full agent/exporter version. [11] | `1.285.1.20240101-256988` |

**[1]:** Always 'snowflake' for all DSOA telemetry.

**[2]:** User-configured deployment environment label, e.g. 'PROD', 'STG', or 'DEV'. Set via 'core.snowflake.deployment_environment'.

**[3]:** User-configured deployment environment label (OTel-stable canonical key), e.g. 'PROD', 'STG', or 'DEV'. Set via 'core.snowflake.deployment_environment'. Prefer this key over the deprecated deployment.environment alias.

**[4]:** Optional user-defined tag for grouping Snowflake accounts in multitenancy mode, set via 'core.tag'.

**[5]:** Identifies the specific sub-context within the plugin (e.g. 'query_history', 'users_all_roles').

**[6]:** Unique identifier for a single DSOA agent execution run. Changes on every invocation.

**[7]:** The DSOA plugin that produced this telemetry (e.g. 'query_history', 'warehouse_usage').

**[8]:** The Snowflake account hostname (e.g. 'xy12345.snowflakecomputing.com'), from 'core.snowflake.host_name'.

**[9]:** Always the Snowflake account identifier without '.snowflakecomputing.com' suffix (e.g. 'myorg-myaccount').

**[10]:** Always 'dynatrace.snowagent' — identifies DSOA as the telemetry exporter.

**[11]:** The installed DSOA agent version in '<major>.<minor>.<patch>.<build>' format.

`db.system` has the following list of well-known values. If one of them applies, then the respective value MUST be used, otherwise a custom value MAY be used.

| Value  | Description | Display name |
|---|---|---|
| `adabas` | Adabas (Adaptable Database System) | Adabas |
| `amazon-documentdb` | Amazon DocumentDB | DocumentDB |
| `aurora-mysql` | Amazon Aurora MySQL | Aurora MySQL |
| `aurora-postgresql` | Amazon Aurora PostgreSQL | Aurora PostgreSQL |
| `cache` | InterSystems Caché | InterSystems Caché |
| `cassandra` | Apache Cassandra | Cassandra |
| `clickhouse` | ClickHouse | ClickHouse |
| `cloudscape` | Cloudscape | Cloudscape |
| `cockroachdb` | CockroachDB | CockroachDB |
| `coldfusion` | ColdFusion IMQ | ColdFusion IMQ |
| `cosmosdb` | Microsoft Azure Cosmos DB | Cosmos DB |
| `couchbase` | Couchbase | Couchbase |
| `couchdb` | CouchDB | CouchDB |
| `databricks` | Databricks Data Platform | Databricks Data Platform |
| `db2` | IBM Db2 | IBM Db2 |
| `derby` | Apache Derby | Derby |
| `dl/i` | IBM DL/I | IBM DL/I |
| `dynamodb` | Amazon DynamoDB | DynamoDB |
| `edb` | EnterpriseDB | EnterpriseDB |
| `elasticsearch` | Elasticsearch | Elasticsearch |
| `filemaker` | FileMaker | FileMaker |
| `firebird` | Firebird | Firebird |
| `firstsql` | FirstSQL | FirstSQL |
| `geode` | Apache Geode | Geode |
| `h2` | H2 | H2 |
| `hanadb` | SAP HANA | SAP HANA |
| `hbase` | Apache HBase | HBase |
| `hive` | Apache Hive | Hive |
| `hsqldb` | HyperSQL DataBase | HSQLDB |
| `informix` | Informix | Informix |
| `ingres` | Ingres | Ingres |
| `instantdb` | InstantDB | InstantDB |
| `interbase` | InterBase | InterBase |
| `keyspaces-cassandra` | Amazon Keyspaces for Apache Cassandra | Keyspaces |
| `mariadb` | MariaDB | MariaDB |
| `maxdb` | SAP MaxDB | SAP MaxDB |
| `memcached` | Memcached | Memcached |
| `mongodb` | MongoDB | MongoDB |
| `mssql` | Microsoft SQL Server | SQL Server |
| `mssqlcompact` | Microsoft SQL Server Compact | SQL Server Compact |
| `mysql` | MySQL | MySQL |
| `neo4j` | Neo4j | Neo4j |
| `neptune` | Amazon Neptune | Neptune |
| `netezza` | Netezza | Netezza |
| `opensearch` | OpenSearch | OpenSearch |
| `oracle` | Oracle Database | Oracle |
| `other_sql` | Some other SQL database. Fallback only. See notes. | Other SQL |
| `pervasive` | Pervasive PSQL | Pervasive PSQL |
| `phoenix` | Apache Phoenix | Apache Phoenix |
| `pointbase` | PointBase | PointBase |
| `postgresql` | PostgreSQL | PostgreSQL |
| `progress` | Progress Database | Progress |
| `redis` | Redis | Redis |
| `redshift` | Amazon Redshift | Redshift |
| `snowflake` | Snowflake Data Platform | Snowflake Data Platform |
| `spanner` | Cloud Spanner | Cloud Spanner |
| `sqlite` | SQLite | SQLite |
| `sybase` | Sybase | Sybase |
| `teradata` | Teradata | Teradata |
| `valkey` | Valkey | Valkey |
| `vertica` | Vertica | Vertica |
<!-- end_model -->

<!-- dynatrace_internal -->
| Responsible PM | Maintainer | Team |
|---|---|---|
| Michael Schachner-Pointner | Sebastian Kruk | DSOA |
<!-- end_dynatrace_internal -->

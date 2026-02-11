# Use Case Highlights

Dynatrace Snowflake Observability Agent (DSOA) delivers telemetry to implement all five [Data Platform Observability](DPO.md) themes. Here are some
example use cases which can be realized with observability data gathered and delivered to Dynatrace by DSOA.

- [Theme: Security](#theme-security)
- [Theme: Operations](#theme-operations)
- [Theme: Costs](#theme-costs)
- [Theme: Performance](#theme-performance)
- [Theme: Quality](#theme-quality)

## Theme: Security

| Use case                      | In Details                                                                                                                                                             | Data                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Warehouse security monitoring | Detect potential data security issues and breaches as quickly as possible. Gather information about these security issues and entities put at risk by vulnerabilities. | [Trust Center plugin](PLUGINS.md#trust_center_info_sec)   |
| Log in and session monitoring | Provide detailed information on logging history and sessions, essential for detecting security breaches.                                                               | [Login History plugin](PLUGINS.md#login_history_info_sec) |

## Theme: Operations

| Use case                      | In Details                                                                                                                                                       | Data                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Predicting credits exhaustion | Move beyond static threshold emails for resource monitor credits. Analyze costs to predict whether credits will suffice by the time the resource monitor resets. | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec) |
| Snowflake Trail monitoring    | Gather information from Snowflake Trail to provide enhanced visibility into pipeline health.                                                                     | [Event Log plugin](PLUGINS.md#event_log_info_sec)             |

## Theme: Costs

| Use case                   | In Details                                                                                                                                                    | Data                                                              |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Resource monitors analysis | Determine if the credits limit set on a resource monitor is enough, too much, or too little for future needs. Analyze detailed data to make better decisions. | [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec) |
| Budgets analysis           | Combine budget details like spending limits and linked resources with their spending history to enable complete cost analysis.                                | [Budgets plugin](PLUGINS.md#budgets_info_sec)                     |
| Ingest cost analysis       | Monitor data ingestion, credits used during events, and bytes ingested.                                                                                       | [Event Usage plugin](PLUGINS.md#event_usage_info_sec)             |
| Serverless tasks analysis  | Monitor credits spent by serverless tasks, which rely on compute resources managed by Snowflake.                                                              | [Tasks plugin](PLUGINS.md#tasks_info_sec)                         |
| Warehouse metering history | Monitor spending of particular warehouses and predict trends in their expenses.                                                                               | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec)     |

## Theme: Performance

| Use case                       | In Details                                                                                                                                                                                                                                                | Data                                                          |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Query slowdowns                | With anomaly detection we should be able to detect queries that go slower in given context (query tag, table, …)                                                                                                                                          | [Query History plugin](PLUGINS.md#query_history_info_sec)     |
| Table slowdowns                | We would like to know if certain tables should be reindexed to improve performance, that is, query slowdown may indicate deterioration of table data structure over time, but we should not limit our analysis only to tables that are slow all the time. | [Query History plugin](PLUGINS.md#query_history_info_sec)     |
| Warehouse optimization         | Evaluate if warehouses are appropriately sized for their workloads                                                                                                                                                                                        | [Query History plugin](PLUGINS.md#query_history_info_sec)     |
| Multi-level query analysis     | Analyze performance of procedures and functions to identify bottlenecks                                                                                                                                                                                   | [Query History plugin](PLUGINS.md#query_history_info_sec)     |
| Detect costly repeated queries | Taking into account the size of the warehouse, we should detect the most costly queries.                                                                                                                                                                  | [Query History plugin](PLUGINS.md#query_history_info_sec)     |
| Monitoring tasks performance   | We can monitor and report on task performance to verify if there are any slowdowns or failing tasks.                                                                                                                                                      | [Tasks plugin](PLUGINS.md#tasks_info_sec)                     |
| Monitor warehouse loads        | We can monitor the loads put on warehouses to determine which could benefit from additional resources or which don’t utilize their resources fully.                                                                                                       | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec) |
| Query summary                  | We provide a summary of queries, giving their count, fastest, slowest, and average running time. This can be useful in detecting slowdowns.                                                                                                               | [Active Queries plugin](PLUGINS.md#active_queries_info_sec)   |
| Current query monitoring       | Monitor the status and runtime duration of currently executing queries                                                                                                                                                                                    | [Active Queries plugin](PLUGINS.md#active_queries_info_sec)   |

## Theme: Quality

| Use case                   | In Details                                                                                                                           | Data                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| Data volume monitoring     | Understand how data volume in monitored databases, schemas, and tables changes over time. Identify anomalies in data volume changes. | [Data Volume plugin](PLUGINS.md#data_volume_info_sec) |
| Snowflake Trail monitoring | Gather information from Snowflake Trail to provide enhanced visibility into data quality.                                            | [Event Log plugin](PLUGINS.md#event_log_info_sec)     |

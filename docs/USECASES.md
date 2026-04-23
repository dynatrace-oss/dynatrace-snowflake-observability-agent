# Use Case Highlights

Dynatrace Snowflake Observability Agent (DSOA) delivers telemetry to implement all five [Data Platform Observability](DPO.md) themes across
the three DPO tiers: **Data Infrastructure**, **Data Apps & Pipelines**, and **Data Quality & Governance**.

Here are the use cases which can be realized with observability data gathered and delivered to Dynatrace by DSOA.
Use cases marked with 🔜 are **upcoming** — they depend on plugins currently in development (Stages, Streams).

- [Theme: Security](#theme-security)
- [Theme: Operations](#theme-operations)
- [Theme: Costs](#theme-costs)
- [Theme: Performance](#theme-performance)
- [Theme: Quality](#theme-quality)
- [Use Case vs Tier Matrix](#use-case-vs-tier-matrix)

---

## Theme: Security

### Security — Tier 1 — Data Infrastructure

| Use case                              | In Details                                                                                                                                                                                               | Data                                                      |
|---------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| Trust Center vulnerability monitoring | Detect potential data security issues and breaches as quickly as possible. Gather information about entities put at risk by vulnerability findings from CIS Benchmarks and Threat Intelligence scanners. | [Trust Center plugin](PLUGINS.md#trust_center_info_sec)   |
| Login and session monitoring          | Provide detailed information on login history and sessions — authentication methods, failed logins, error codes — essential for detecting security breaches and unauthorized access.                     | [Login History plugin](PLUGINS.md#login_history_info_sec) |

### Security — Tier 2 — Data Apps & Pipelines

| Use case                            | In Details                                                                                                                                                                | Data                                                      |
|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| User identity and access monitoring | Track active users, disabled/locked accounts, MFA enrollment, RSA key usage, password policies, and role assignments. Detect removed users and role changes between runs. | [Users plugin](PLUGINS.md#users_info_sec)                 |
| Privilege escalation detection      | With `ALL_ROLES` and `ALL_PRIVILEGES` monitoring modes, detect excessive privilege grants and identify users with overly broad access.                                    | [Users plugin](PLUGINS.md#users_info_sec)                 |
| Data sharing security review        | Monitor inbound and outbound shares — ownership, grant privileges, secure-objects-only flags — to detect unauthorized or misconfigured data sharing.                      | [Shares plugin](PLUGINS.md#shares_info_sec)               |
| Query origin analysis               | Analyze client applications, authentication types, and session details associated with queries to detect anomalous access patterns.                                       | [Query History plugin](PLUGINS.md#query_history_info_sec) |
| 🔜 Stage access auditing            | Track who accesses external and internal stages, detect unauthorized file operations, and audit encryption configurations.                                                | Stages plugin (upcoming)                                  |

### Security — Tier 3 — Data Quality & Governance

| Use case                    | In Details                                                                                                  | Data                                                    |
|-----------------------------|-------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| Schema ownership governance | Track schema and table ownership, DDL changes, and retention policies to ensure data governance compliance. | [Data Schemas plugin](PLUGINS.md#data_schemas_info_sec) |

---

## Theme: Operations

### Operations — Tier 1 — Data Infrastructure

| Use case                       | In Details                                                                                                                                                        | Data                                                              |
|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| Warehouse lifecycle monitoring | Track warehouse events — creating, dropping, altering, resizing, resuming, suspending clusters — to maintain operational awareness of infrastructure changes.     | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec)     |
| Predicting credits exhaustion  | Move beyond static threshold emails for resource monitor credits. Analyze trends to predict whether credits will suffice by the time the resource monitor resets. | [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec) |
| Resource monitor health        | Monitor resource monitor states including active status, frequency, quota usage percentages, and remaining credits with threshold-based alerting.                 | [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec) |

### Operations — Tier 2 — Data Apps & Pipelines

| Use case                            | In Details                                                                                                                                            | Data                                                        |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| Task orchestration monitoring       | Monitor task graph versions, predecessors, schedules, error integrations, and execution states. Detect failed tasks with error codes and messages.    | [Tasks plugin](PLUGINS.md#tasks_info_sec)                   |
| Dynamic table refresh monitoring    | Track dynamic table refresh status, scheduling lag, and operational state changes to detect stale materializations.                                   | [Dynamic Tables plugin](PLUGINS.md#dynamic_tables_info_sec) |
| Current query monitoring            | Monitor the status and runtime duration of currently executing queries across all warehouses, detecting long-running or stuck queries.                | [Active Queries plugin](PLUGINS.md#active_queries_info_sec) |
| Snowpipe operational monitoring     | Monitor pipe health and status: detect PAUSED_BY_SNOWFLAKE and STOPPED_BY_SNOWFLAKE states, track error-file percentages, and alert on pipe failures. | Snowpipes plugin (upcoming)                                 |
| Snowpipe stage backlog analysis     | Track pending file counts and stage scan depth to detect ingestion backlogs and stalled pipelines.                                                    | Snowpipes plugin (upcoming)                                 |
| 🔜 Stream consumption lag detection | Monitor stream staleness, detect stalled consumers (no consumption within N intervals), and alert on streams approaching their max offset age.        | Streams plugin (upcoming)                                   |

### Operations — Tier 3 — Data Quality & Governance

| Use case                        | In Details                                                                                                                                                               | Data                                              |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| Snowflake Trail process metrics | Forward Snowflake Trail telemetry (process CPU utilization, memory usage, execution spans) to Dynatrace for unified visibility into Snowflake's internal process health. | [Event Log plugin](PLUGINS.md#event_log_info_sec) |

---

## Theme: Costs

### Costs — Tier 1 — Data Infrastructure

| Use case                   | In Details                                                                                                                                                                  | Data                                                              |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| Resource monitors analysis | Determine if the credits limit set on a resource monitor is enough, too much, or too little for future needs. Analyze quota used vs remaining to make better decisions.     | [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec) |
| Budgets analysis           | Combine budget details like spending limits and linked resources with their spending history to enable complete cost analysis.                                              | [Budgets plugin](PLUGINS.md#budgets_info_sec)                     |
| Warehouse metering history | Monitor credit consumption of particular warehouses, compare cloud services credits vs compute credits, and predict trends in expenses.                                     | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec)     |
| Event table ingest costs   | Monitor credits billed and bytes ingested for loading data into the Snowflake event table over time.                                                                        | [Event Usage plugin](PLUGINS.md#event_usage_info_sec)             |
| Storage growth analysis    | Track database and table storage growth trends (total size, row counts) and time since last DDL/update for capacity planning.                                               | [Data Volume plugin](PLUGINS.md#data_volume_info_sec)             |
| Cold table identification  | Identify tables with no recent query access to find candidates for archiving, dropping, or tiering to lower-cost storage. Reduce storage costs by sunsetting unused tables. | [Cold Tables plugin](PLUGINS.md#cold_tables_info_sec)             |

### Costs — Tier 2 — Data Apps & Pipelines

| Use case                         | In Details                                                                                                                                | Data                                                      |
|----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| Serverless task cost analysis    | Monitor credits spent by serverless tasks (which rely on Snowflake-managed compute) broken down by database, schema, and task name.       | [Tasks plugin](PLUGINS.md#tasks_info_sec)                 |
| Query cost attribution           | Attribute cloud services credits and compute costs to specific users, roles, warehouses, and query types for chargeback and optimization. | [Query History plugin](PLUGINS.md#query_history_info_sec) |
| Data transfer cost monitoring    | Track inbound and outbound data transfer volumes across regions and clouds to identify unexpected cross-region costs.                     | [Query History plugin](PLUGINS.md#query_history_info_sec) |
| Snowpipe FinOps attribution      | Track credits consumed by Snowpipe per pipe, per database, enabling cost allocation and chargeback for data ingestion pipelines.          | Snowpipes plugin (upcoming)                               |
| 🔜 Stage storage cost visibility | Monitor stage file counts and sizes to identify stale files consuming storage credits, and track external stage cloud provider costs.     | Stages plugin (upcoming)                                  |
| 🔜 Stream FinOps attribution     | Attribute CDC processing costs to specific streams and consuming tasks for accurate FinOps reporting.                                     | Streams plugin (upcoming)                                 |

---

## Theme: Performance

### Performance — Tier 1 — Data Infrastructure

| Use case                | In Details                                                                                                                                                                                                 | Data                                                                                                                             |
|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------|
| Monitor warehouse loads | Monitor query load values (running queries, queued queries, compute utilization percentages) to determine which warehouses could benefit from additional resources or don't utilize their resources fully. | [Warehouse Usage plugin](PLUGINS.md#warehouse_usage_info_sec), [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec) |
| Warehouse optimization  | Evaluate if warehouses are appropriately sized for their workloads by analyzing cluster counts, scaling policies, and queue overload times.                                                                | [Resource Monitors plugin](PLUGINS.md#resource_monitors_info_sec), [Query History plugin](PLUGINS.md#query_history_info_sec)     |

### Performance — Tier 2 — Data Apps & Pipelines

| Use case                              | In Details                                                                                                                                                                          | Data                                                        |
|---------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| Query slowdown detection              | With anomaly detection, detect queries that go slower in a given context (query tag, table, warehouse, role) by analyzing compilation time, execution time, and total elapsed time. | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Table performance degradation         | Detect tables that should be re-clustered by analyzing partition scan ratios, data spill volumes (local and remote), and cache hit rates over time.                                 | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Multi-level query analysis            | Analyze performance of procedures and functions using parent-child query relationships, operator-level statistics, and step-level timing breakdowns.                                | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Detect costly repeated queries        | Taking into account warehouse size, detect the most costly queries by analyzing bytes scanned, rows processed, spill volumes, and execution times grouped by query hash.            | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Query acceleration analysis           | Identify queries eligible for query acceleration, evaluate estimated time savings at various scale factors, and measure actual acceleration bytes scanned.                          | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Task execution performance            | Monitor task run durations, detect failing tasks via error codes, and analyze retry patterns and scheduling delays.                                                                 | [Tasks plugin](PLUGINS.md#tasks_info_sec)                   |
| Dynamic table refresh performance     | Track dynamic table scheduling lag and data freshness to detect materializations falling behind their target lag.                                                                   | [Dynamic Tables plugin](PLUGINS.md#dynamic_tables_info_sec) |
| Query summary and active monitoring   | Provide a real-time summary of queries giving their count, fastest, slowest, and average running time. Detect long-running queries in progress.                                     | [Active Queries plugin](PLUGINS.md#active_queries_info_sec) |
| External function performance         | Monitor external function invocations, data sent/received volumes, and row counts to detect performance bottlenecks in remote service calls.                                        | [Query History plugin](PLUGINS.md#query_history_info_sec)   |
| Snowpipe ingestion throughput         | Track files-per-interval and bytes-per-interval rates to detect throughput degradation and ingestion bottlenecks.                                                                   | Snowpipes plugin (upcoming)                                 |
| 🔜 Stream change-record volume spikes | Detect abnormal surges in CDC record volumes that could indicate upstream schema changes or bulk operations impacting downstream consumers.                                         | Streams plugin (upcoming)                                   |

---

## Theme: Quality

### Quality — Tier 1 — Data Infrastructure

| Use case               | In Details                                                                                                                                                                             | Data                                                    |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| Data volume monitoring | Understand how data volume in monitored databases, schemas, and tables changes over time. Identify anomalies in data volume changes (active bytes, time-travel bytes, failsafe bytes). | [Data Volume plugin](PLUGINS.md#data_volume_info_sec)   |
| Data schema monitoring | Track database and table metadata — table types (dynamic, hybrid, iceberg, transient, temporary), clustering keys, auto-clustering status, and retention policies.                     | [Data Schemas plugin](PLUGINS.md#data_schemas_info_sec) |

### Quality — Tier 2 — Data Apps & Pipelines

| Use case                            | In Details                                                                                                                                                                             | Data                                                        |
|-------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| Share data quality                  | Monitor inbound share availability status, detect UNAVAILABLE shares, and track table row counts and sizes within shared databases to identify data quality issues in shared datasets. | [Shares plugin](PLUGINS.md#shares_info_sec)                 |
| Dynamic table data freshness        | Track dynamic table scheduling lag and data timestamp to detect stale materializations that could propagate outdated data downstream.                                                  | [Dynamic Tables plugin](PLUGINS.md#dynamic_tables_info_sec) |
| Snowpipe ingestion validation       | Track error-file ratios, detect PARTIALLY_LOADED states, and validate that ingested row counts match expected volumes.                                                                 | Snowpipes plugin (upcoming)                                 |
| 🔜 Stage data validation            | Monitor file counts and modification timestamps in stages, detect orphaned files, and validate stage-to-table load completeness.                                                       | Stages plugin (upcoming)                                    |
| 🔜 CDC data-quality drift detection | Detect structural changes in stream source tables that cause downstream type mismatches or schema evolution issues.                                                                    | Streams plugin (upcoming)                                   |

### Quality — Tier 3 — Data Quality & Governance

| Use case                   | In Details                                                                                                                               | Data                                                                                                 |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| Table lifecycle governance | Track table creation, DDL, and DML timestamps to identify stale tables, enforce retention policies, and audit data lifecycle compliance. | [Data Schemas plugin](PLUGINS.md#data_schemas_info_sec), [Shares plugin](PLUGINS.md#shares_info_sec) |

---

## Use Case vs Tier Matrix

The matrix below maps each DPO theme to the three observability tiers, showing the number of current and upcoming use cases.

| Theme           | Tier 1: Data Infrastructure | Tier 2: Data Apps & Pipelines | Tier 3: Data Quality & Governance |
|-----------------|-----------------------------|-------------------------------|-----------------------------------|
| **Security**    | 2 current                   | 4 current + 1 upcoming        | 1 current                         |
| **Operations**  | 3 current                   | 3 current + 3 upcoming        | 1 current                         |
| **Costs**       | 5 current                   | 3 current + 3 upcoming        | —                                 |
| **Performance** | 2 current                   | 9 current + 2 upcoming        | —                                 |
| **Quality**     | 2 current                   | 2 current + 3 upcoming        | 1 current                         |
| **Total**       | **14 current**              | **21 current + 12 upcoming**  | **3 current**                     |

### Upcoming Plugin Summary

| Plugin        | Status                        | Key Use Cases                                                                              | DPO Themes                              |
|---------------|-------------------------------|--------------------------------------------------------------------------------------------|-----------------------------------------|
| **Snowpipes** | 0.9.4                         | Operational monitoring, FinOps attribution, ingestion validation, throughput analysis      | Operations, Costs, Performance, Quality |
| **Stages**    | Planned (deferred)            | Access auditing, storage cost visibility, data validation (non-pipe operations only)       | Security, Costs, Quality                |
| **Streams**   | Planned (no immediate demand) | Consumption lag detection, FinOps attribution, volume spike detection, CDC drift detection | Operations, Costs, Performance, Quality |

> **Note:** Pipe-associated stage monitoring (backlog, pending files) is covered by the Snowpipes plugin
> via `SYSTEM$PIPE_STATUS`. The standalone Stages plugin targets non-pipe operations (`PIPE_NAME IS NULL`
> in COPY_HISTORY): manual COPY INTO, stage storage sprawl, zombie file detection, and access auditing.

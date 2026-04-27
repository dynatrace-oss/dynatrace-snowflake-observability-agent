# Example Dashboards

This directory contains example Dynatrace dashboards designed to visualize and analyze telemetry data collected by the Dynatrace Snowflake Observability Agent (DSOA). These dashboards provide comprehensive insights across the five themes of [Data Platform Observability](../DPO.md): Security, Operations, Costs, Performance, and Quality.

- [Distribution Package](#distribution-package)
- [Available Dashboards](#available-dashboards)
  - [DSOA Self-Monitoring](#dsoa-self-monitoring)
  - [Snowflake Query Performance](#snowflake-query-performance)
  - [Org-Level Costs Observability](#org-level-costs-observability)
  - [Tasks \& Pipelines Monitoring](#tasks--pipelines-monitoring)
  - [Snowpipes Monitoring](#snowpipes-monitoring)
  - [Budgets \& FinOps](#budgets--finops)
  - [Snowflake Query Deep Dive](#snowflake-query-deep-dive)
  - [Data Volume \& Storage](#data-volume--storage)
  - [Snowflake Security](#snowflake-security)
  - [Shares \& Governance](#shares--governance)
- [Dashboard Structure](#dashboard-structure)
- [Importing Dashboards](#importing-dashboards)
  - [Using Deployment Script (Recommended for Automation)](#using-deployment-script-recommended-for-automation)
  - [Using Pre-Generated JSON Files](#using-pre-generated-json-files)
  - [Using Dynatrace UI](#using-dynatrace-ui)
  - [Converting from YAML Source (Advanced)](#converting-from-yaml-source-advanced)
- [Prerequisites](#prerequisites)
- [Customization](#customization)
- [Related Documentation](#related-documentation)
- [Support and Contribution](#support-and-contribution)

## Distribution Package

When you download the DSOA distribution package (`dynatrace_snowflake_observability_agent-*.zip`), the `dashboards/` directory contains ready-to-import JSON files for all example dashboards. These JSON files are automatically generated from the YAML source definitions and can be imported directly into your Dynatrace environment using the Dynatrace UI or API.

**To import dashboards:**

1. Extract the distribution package
2. Navigate to the `dashboards/` directory
3. Import the desired JSON files into Dynatrace via:
   - **UI**: Dashboards > Browse > Import dashboard
   - **API**: Use the Dynatrace Dashboards API

Each JSON file is named after its dashboard title (e.g., `Costs Monitoring.json`, `Snowflake Query Performance.json`) for easy identification.

## Available Dashboards

### [DSOA Self-Monitoring](self-monitoring/)

**Purpose**: Monitor the operational health and performance of the DSOA agent itself.

**Key Features**:

- Track plugin execution times and frequency
- Monitor data production across logs, events, spans, and business events
- Identify and troubleshoot failed plugin executions
- Analyze agent resource consumption

**Required Plugin**: `query_history`

**DPO Theme**: Operations

---

### [Snowflake Query Performance](query-performance/)

**Purpose**: Identify slow or resource-intensive Snowflake queries to optimize performance.

**Key Features**:

- Monitor query execution time trends across accounts, databases, tables, and users
- Identify top resource consumers with donut charts for tables, users, and databases
- AI-powered anomaly detection correlating query performance with table growth
- Executive summary with account-wide performance overview

**Required Plugin**: `query_history`

**DPO Theme**: Performance

---
**Purpose**: Detect queries with full cartesian joins that indicate potential quality issues.

**Key Features**:

- Identify queries producing cartesian products (unintended cross joins)
- Track cartesian join trends over time by environment, operation, and user
- Detailed query logs with execution metadata for investigation
**Required Plugin**: `query_history`
**DPO Theme**: Quality

---

**Purpose**: Monitor and optimize Snowflake resource costs and credit consumption.
**Key Features**:

- Monitor credit quota utilization for resource monitors
- Identify warehouses missing resource monitor assignments
- Analyze warehouse performance metrics (execution time, queuing, delays)
- Detect slow queries that may exhaust warehouse credits

**Required Plugins**: `warehouse_usage`, `resource_monitors`, `query_history`, `active_queries`

**DPO Theme**: Costs, Operations

---

### [Org-Level Costs Observability](org-costs-observability/)

**Purpose**: Monitor organization-wide Snowflake costs across all accounts in a single dashboard.

**Key Features**:

- Credit consumption by service type and service name across the organization
- Cloud services credit adjustment trends
- Organization-wide storage bytes by storage type and account locator
- Cross-cloud and cross-region data transfer volumes
- Billing amounts in contract currency per service type and account
- Remaining contract balances (free usage, capacity, on-demand, rollover, total)

**Required Plugin**: `org_costs` (disabled by default — requires ORGADMIN or organization-linked account)

**DPO Theme**: Costs

---

### [Tasks & Pipelines Monitoring](tasks-pipelines/)

**Purpose**: Monitor the health, performance, cost, and data freshness of Snowflake task graphs and dynamic tables.

**Key Features**:

- Task execution state trends (SUCCEEDED, FAILED, SKIPPED) with detailed failed-task error drill-down
- Task run duration trending and retry pattern analysis to detect unstable or slow pipelines
- Serverless task credit attribution by task name, database, and schema
- Dynamic table scheduling state heatmap for at-a-glance freshness health
- Lag monitoring — mean lag vs max lag trended per table, time above target lag, and within-target-lag ratio
- Recent dynamic table refresh history with state colour coding and action distribution breakdown

**Required Plugins**: `tasks`, `dynamic_tables`

**DPO Theme**: Operations, Performance, Costs, Quality

---

### [Snowpipes Monitoring](snowpipes-monitoring/)

**Purpose**: Monitor the health, performance, and cost of Snowflake Snowpipe continuous data ingestion pipelines.

**Key Features**:

- Executive overview with pipe health %, credits consumed, files processed, and p95 latency KPIs
- Pipe status heatmap showing RUNNING, PAUSED, and STOPPED/STALLED pipes at a glance
- Ingestion latency trends per pipe with configurable warning and critical thresholds
- Stage backlog monitoring to detect accumulating pending files before they cause delays
- Error analytics by target table and top-error pipe rankings
- Credit consumption trends over time per pipe

**Required Plugin**: `snowpipes`

**DPO Theme**: Operations, Performance

---

### [Budgets & FinOps](budgets-finops/)

**Purpose**: Track Snowflake budget spending, warehouse sizing decisions, and warehouse load patterns.

**Key Features**:

- Budget spend vs. limit KPIs with historical trends and per-service-type credit breakdown
- Per-warehouse sizing overview: cluster configuration, resource monitor assignment, and unmonitored warehouse detection
- Cluster utilization and resource monitor quota usage trends over time
- Warehouse load analysis: running, queued, and blocked query counts from `WAREHOUSE_LOAD_HISTORY`
- Resource monitor quota utilization and alert threshold visibility

**Required Plugins**: `budgets`, `warehouse_usage`, `resource_monitors`

**DPO Theme**: Costs, Operations

---

### [Snowflake Query Deep Dive](query-deep-dive/)

**Purpose**: Advanced query analytics for DBAs and FinOps teams — covering costly repeated queries, table performance degradation, query acceleration, multi-level analysis, external functions, query origins, and cost attribution.

**Key Features**:

- Rank query hashes by total bytes scanned and spill volumes to surface the costliest repeated query patterns
- Partition scan ratio and cache hit rate trends per table to identify re-clustering candidates
- Query acceleration eligibility list with estimated time savings at multiple scale factors
- Parent-child query breakdown and operator-level plan statistics from span data
- External function invocation and data volume monitoring
- Query origin analysis by client application and authentication type for security forensics
- Cloud services credit attribution by user, role, and warehouse
- Cross-region data transfer volumes for egress cost monitoring

**Required Plugin**: `query_history`

**DPO Theme**: Performance, Security, Costs

---

### [Data Volume & Storage](data-volume-storage/)

**Purpose**: Monitor data growth, storage consumption, table freshness, and schema change history across Snowflake databases.

**Key Features**:

- Track storage byte and row count trends over time per database with headline KPI tiles
- Identify the top 20 largest tables for capacity planning and archival prioritisation
- Surface stale tables by days since last DML or DDL operation for lifecycle governance
- Visualise table type distribution (BASE TABLE, TEMPORARY TABLE, EXTERNAL TABLE)
- Audit recent DDL operations (CREATE, ALTER, DROP, REPLACE, UNDROP) with user attribution
- Analyse DDL operation frequency over time and object type breakdown

**Required Plugins**: `data_volume`, `data_schemas`

**DPO Theme**: Quality, Costs, Security

---

### [Snowflake Security](snowflake-security/)

**Purpose**: Monitor security aspects and compliance of Snowflake accounts.

**Key Features**:

- Consolidate findings from Snowflake's Trust Center across multiple accounts
- Monitor query history of users with excessive privileges
- Track failed login attempts for threat detection
- Enforce secure authentication methods (MFA, SSO, Key-Pair, OAuth)
- Analyze authentication methods for human and service accounts

**Required Plugins**: `trust_center`, `login_history`, `query_history`

**DPO Theme**: Security

---

### [Shares & Governance](shares-governance/)

**Purpose**: Monitor the health, security posture, and governance of Snowflake data sharing across inbound and outbound shares.

**Key Features**:

- Full share inventory — all outbound and inbound shares with owner, database, and direction
- Inbound share health monitoring — detect UNAVAILABLE shares, deleted-database references, and data-volume anomalies
- Shared table row count and size tracking to detect truncated or unexpectedly empty inbound shares
- Secure-objects-only compliance pie chart for outbound shares
- Grant audit trail — every privilege grant per outbound share with grantee and granted-by attribution
- Outbound grantee ranking to identify over-provisioned external sharing

**Required Plugin**: `shares`

**DPO Theme**: Security, Operations

---

## Dashboard Structure

Each dashboard folder in the source repository contains:

- **`*.yml`** - Dashboard definition file in YAML format (converted to JSON in distribution packages)
- **`readme.md`** - Comprehensive documentation with:
  - Dashboard purpose and use cases
  - Description of all visualizations and tiles
  - Required plugins and dependencies
  - Technical details and default settings
- **`img/`** - Screenshots and visual documentation

## Importing Dashboards

### Using Deployment Script (Recommended for Automation)

The `deploy_dt_assets.sh` script automates dashboard deployment using [dtctl](https://github.com/dynatrace-oss/dtctl).
It converts YAML sources to JSON, wraps them in the correct dtctl envelope, and applies them idempotently.

**Deploy all dashboards:**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=dashboards
```

**Dry-run (preview without applying):**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=dashboards --dry-run
```

**Deploy dashboards and workflows together:**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=all
```

**Via the main deploy script:**

```bash
./scripts/deploy/deploy.sh <env> --scope=dt_assets
```

> **Prerequisites:** [dtctl](https://github.com/dynatrace-oss/dtctl) must be installed and authenticated.
> See the [Installation Guide](../INSTALL.md#deploying-dashboards-and-workflows) for setup instructions.

### Using Pre-Generated JSON Files

**If you downloaded the distribution package** (`dynatrace_snowflake_observability_agent-*.zip`), ready-to-use JSON dashboard files are included in the `dashboards/` directory. Simply import them directly:

1. Extract the distribution package
2. Navigate to the `dashboards/` directory
3. Import the desired JSON file into your Dynatrace environment

### Using Dynatrace UI

1. Navigate to **Dashboards** in your Dynatrace environment
2. Click **Import dashboard**
3. Upload the JSON file from the `dashboards/` directory (or converted from YAML, see below)
4. Adjust dashboard variables if needed

### Converting from YAML Source (Advanced)

**If you are working from the source repository**, dashboards are maintained as YAML files for better readability and version control. Convert them to JSON using:

```bash
./scripts/tools/yaml-to-json.sh docs/dashboards/<dashboard-name>/<dashboard-name>.yml > 'Dashboard Name.json'
```

Then import the generated JSON file as described above.

## Prerequisites

- DSOA must be deployed and collecting telemetry from your Snowflake account(s)
- Required plugins for each dashboard must be enabled in your DSOA configuration
- Sufficient Dynatrace Davis Data Units (DDUs) for the data volume being collected

## Customization

These dashboards serve as starting points and can be customized to meet your specific needs:

- Modify time ranges and aggregation intervals
- Add or remove variables for additional filtering
- Adjust visualizations and layouts
- Create dashboard presets for different teams or use cases

> **Note:** The YAML source files ship with pre-populated `id:` fields. If you customize a dashboard in the
> Dynatrace UI and later redeploy from an updated upstream YAML, the matching ID will overwrite your changes.
> See the [Idempotency and Dashboard IDs](../INSTALL.md#idempotency-and-dashboard-ids) section in the
> Installation Guide for strategies to avoid this.

## Related Documentation

- [Data Platform Observability (DPO)](../DPO.md) - Understanding the five themes of data observability
- [Available Plugins](../PLUGINS.md) - Complete list of DSOA plugins and their capabilities
- [Common Use Cases](../USECASES.md) - Practical scenarios for leveraging DSOA telemetry
- [Telemetry Semantics](../SEMANTICS.md) - Comprehensive dictionary of all telemetry fields
- [Architecture](../ARCHITECTURE.md) - Understanding how DSOA collects and sends telemetry data

## Support and Contribution

For issues, questions, or contributions related to these dashboards:

- Review the [Contribution Guidelines](../CONTRIBUTING.md)
- Open an issue in the repository
- Submit a pull request with improvements or new dashboard examples

---

**Note**: Dashboard query performance depends on the volume of data collected and the time range selected. For large deployments, consider using dashboard presets with narrower time ranges or specific account filters.

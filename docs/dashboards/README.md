# Example Dashboards

This directory contains example Dynatrace dashboards designed to visualize and analyze telemetry data collected by the Dynatrace Snowflake Observability Agent (DSOA). These dashboards provide comprehensive insights across the five themes of [Data Platform Observability](../DPO.md): Security, Operations, Costs, Performance, and Quality.

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

### [Snowflake Query Quality](query-quality/)

**Purpose**: Detect queries with full cartesian joins that indicate potential quality issues.

**Key Features**:

- Identify queries producing cartesian products (unintended cross joins)
- Track cartesian join trends over time by environment, operation, and user
- Analyze distribution of cartesian joins across different dimensions
- Detailed query logs with execution metadata for investigation

**Required Plugin**: `query_history`

**DPO Theme**: Quality

---

### [Costs Monitoring](costs-monitoring/)

**Purpose**: Monitor and optimize Snowflake resource costs and credit consumption.

**Key Features**:

- Track credit usage over time with forecasting capabilities
- Monitor credit quota utilization for resource monitors
- Identify warehouses missing resource monitor assignments
- Analyze warehouse performance metrics (execution time, queuing, delays)
- Detect slow queries that may exhaust warehouse credits

**Required Plugins**: `warehouse_usage`, `resource_monitors`, `query_history`, `active_queries`

**DPO Theme**: Costs, Operations

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

## Dashboard Structure

Each dashboard folder contains:

- **`*.yml`** - Dashboard definition file in YAML format (can be converted to JSON for import)
- **`readme.md`** - Comprehensive documentation with:
  - Dashboard purpose and use cases
  - Description of all visualizations and tiles
  - Required plugins and dependencies
  - Technical details and default settings
- **`img/`** - Screenshots and visual documentation

## Importing Dashboards

### Using YAML Files

The dashboards are provided in YAML format for better readability and version control. To import into Dynatrace:

1. Convert YAML to JSON using the provided conversion tool:

   ```bash
   ./tools/yaml-to-json.sh docs/dashboards/<dashboard-name>/<dashboard-name>.yml > 'Dashboard Name.json'
   ```

1. Import the JSON file into your Dynatrace environment via the UI or API

### Using Dynatrace UI

1. Navigate to **Dashboards** in your Dynatrace environment
2. Click **Import dashboard**
3. Upload the converted JSON file
4. Adjust dashboard variables if needed

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

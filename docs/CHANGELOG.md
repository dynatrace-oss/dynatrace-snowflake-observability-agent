# Changelog

All notable changes to this project will be documented in this file.

## Dynatrace Snowflake Observability Agent 0.9.3

Released on February 12, 2026

### Breaking Changes in 0.9.3

- **DTAGENT_OWNER Role Introduction**: Re-architected SnowAgent to introduce `DTAGENT_OWNER` role that owns all SnowAgent artifacts (database, schemas, tables, procedures, tasks). The `DTAGENT_ADMIN` role is now reserved exclusively for elevated administrative privileges, while `DTAGENT_VIEWER` handles regular telemetry-related operations.
- **Deployment vs. Upgrade Permission Requirements**: Deployment and upgrade now have separate permission requirements with the new owner-admin-viewer role separation model.
- **Deployment Configuration**: Configuration files are now in YAML format. Multi-configuration deployment is no longer supported. Each DSOA instance must be deployed separately with its own configuration. Use `convert_config_to_yaml.sh` script to convert existing JSON files.
- **Configuration Structure**: Reorganized Snowflake-related configuration into nested `core.snowflake` structure. The `convert_config_to_yaml.sh` script automatically migrates old paths to the new structure.

### New in 0.9.3

- **Admin Deployment Scope**: New `admin` deployment scope for administrative operations, enabling granular control via `--scope=admin` option.
- **Custom Snowflake Object Names**: Added ability to customize names for all Snowflake objects (database, warehouse, resource monitor, roles). Set admin role or resource monitor to `"-"` to skip their creation entirely.
- **Optional Object Deployment**: When admin role or resource monitor is disabled via `"-"`, related SQL code is automatically excluded from deployment scripts.

### Fixed in 0.9.3

- **Log Timestamp Handling**: Fixed timestamps in logs being sent as nanoseconds instead of milliseconds.
- **Event Log Resource Attributes**: Fixed duplicated resource attribute fields in event log entries.
- **Metric Dimension Array Formatting**: Fixed issue where array-type dimensions (e.g., `db.snowflake.dbs`, `db.snowflake.tables`) were being sent to Dynatrace as Python list representations (e.g., `['DATABASE']`) causing 400 Bad Request errors. Arrays are now properly converted to comma-separated strings (e.g., `DATABASE` or `DB1,DB2,DB3`).

### Improved in 0.9.3

- **Flexible Role Model**: Implemented role hierarchy with `ACCOUNTADMIN` → `DTAGENT_OWNER` → `DTAGENT_VIEWER` as primary hierarchy and `DTAGENT_OWNER` → `DTAGENT_ADMIN` as optional admin branch.
- **Security Model**: Isolated administrative operations in dedicated admin scripts with automated tests to enforce separation.
- **Selective Plugin Deployment**: Enabled deployment with only selected plugins based on use case requirements.
- **Custom Warehouse Support**: Added ability to disable the built-in Resource Monitor or use a customer-provided warehouse.
- **Data Retention Configuration**: Added ability to configure data retention on `DTAGENT_DB` permanent tables (default: 1 day).
- **Simplified Configuration Format**: YAML format with lowercase keys to match Snowflake configuration table paths.
- **Enhanced Deployment Script**: Refactored `deploy.sh` with improved parameter handling using named parameters (`--scope`, `--from-version`, `--output-file`, `--options`).
- **Structured Deployment Scopes**: Introduced well-defined deployment scopes (`init`, `admin`, `setup`, `plugins`, `config`, `agents`, `apikey`, `all`, `teardown`, `upgrade`).
- **Flexible Scope Combinations**: The `apikey` deployment scope can now be combined with other scopes (e.g., `setup,plugins,config,agents,apikey`).
- **Upgrade Process**: Delivered upgrade process with `--scope=upgrade --from-version=VERSION` parameters, supporting custom queries for version migrations.
- **Bill of Materials**: BOM files are now included as part of the documentation with structured tables.
- **Extended Code Quality**: Extended code quality checks to include `build/*.py` files.

## Dynatrace Snowflake Observability Agent 0.9.2

Released on November 24, 2025

### Breaking Changes in 0.9.2

- **Self-monitoring Telemetry**: All self-monitoring telemetry will now have `dsoa.run.context` set to `self_monitoring` (underscore) instead of `self-monitoring` (hyphen).

### New in 0.9.2

- **Example Dashboards**: Added example dashboards to help users visualize and interpret telemetry data, including costs monitoring, self-monitoring, and Snowflake security dashboards with descriptions and screenshots.
- **Configurable Query Analysis**: Introduced options to configure minimum query runtime and the maximum number of top queries for deeper analysis, providing greater flexibility in performance monitoring.
- **Telemetry Configuration**: It is now possible to exclude certain telemetry types, e.g., events, spans, from being sent, either globally or on a per-plugin basis.
- **Event Log Metrics**: Extended support for `RECORD_ATTRIBUTES` in event log metrics for richer telemetry data.

### Improved in 0.9.2

- **Data Schema Plugin**: Now reports on objects (tables, schemas, databases) modified by DDL queries as events.
- **Query Robustness**: Improved query robustness in the Resource Monitors and Users plugins by using explicit column selection to prevent errors from column order changes in `SHOW WAREHOUSES` and `SNOWFLAKE.ACCOUNT_USAGE.USERS`.
- **Telemetry Sender**: Enabled labeling and classification of telemetry calls for better differentiation and analysis of query data. Added `SEND_TELEMETRY` support for `SHOW` statements, enabling more flexible custom queries.
- **Event Handling**: Expanded event-handling capabilities, including support for sending multiple events in a single call and improved handling of Davis events.
- **Metric Dimensions**: Plugin and context names are now available as metric dimensions, improving traceability.
- **Telemetry Query Performance**: Improved performance of reading and processing telemetry data by using simpler queries. Added safety limits and ordering to event log queries to handle high-volume applications.
- **Self-monitoring**: Agent execution now returns detailed status information, including the number of telemetry objects sent by type, plugin, and run context. The deployment process also reports its start and finish as BizEvents, compatible with other telemetry.
- **Configuration**: API post timeout and retry delay are now configurable for metrics and events, providing better control over telemetry delivery.
- **Code Quality & Testing**: Streamlined internal plugin implementations and extended tests for all plugins. Added a suite of code quality checks to the automated build process.
- **Documentation**: Updated documentation to reflect new features, improved the structure for easier navigation as online GitHub pages, and added comprehensive troubleshooting guide for debugging data delivery issues.

## Dynatrace Snowflake Observability Agent 0.9.1

Released on September 18, 2025

### Improved in 0.9.1

- **Telemetry Sender**: `SEND_TELEMETRY` procedure now supports `SHOW` statements, enabling more flexible and powerful custom queries/
- **Modular Documentation**: The documentation has been restructured into multiple files (`PLUGINS.md`, `SEMANTICS.md`, `APPENDIX.md`) for
  improved readability and maintainability.

### Fixed in 0.9.1

- **Resource Monitors**: Queries now use explicit column selection to prevent errors caused by changes in the column order of
  `SHOW WAREHOUSES` command results.
- **Query History**: Fixed upgrade for procedure `P_REFRESH_RECENT_QUERIES` to ensure it works correctly when upgrading from versions prior
  to 0.8.3.

## Dynatrace Snowflake Observability Agent 0.9.0

Released on July 25, 2025

### Highlights

- **Open Source**: This release marks a significant milestone for the Dynatrace Snowflake Observability Agent. The project is now available
  as an Open Source project on GitHub under the permissive MIT license. We welcome community contributions to help us expand its
  capabilities and improve observability for Snowflake environments.

## Dynatrace Snowflake Observability Agent 0.8.3

Released on July 14, 2025.

### Breaking Changes in 0.8.3

- **Meta-field semantics**: In order to align with rebranding to new official name of Dynatrace Snowflake Observability Agent (DSOA) or
  Dynatrace SnowAgent in short, a number of field names had to be refactored.

### Plugins Updated in 0.8.3

- **Shares**: Reduced the number of events sent by the plugin to improve performance.
- **Query History**: Empty queries executed by SYSTEM user at `COMPUTE_SERVICE_WH_*` are no longer reported to Dynatrace.

### Added in 0.8.3

- **Tutorial**: Step-by-step debug tutorial to check if telemetry on currently running queries is correctly delivered via active_queries
  plugin to Dynatrace.
- **Test Suite**: Test suite now ensures that standardized views deliver `TIMESTAMP` column.

### Improved in 0.8.3

- **Improved Security Model**: Basic plugin tasks are now executed as `DTAGENT_VIEWER`, with only special tasks executed as `DTAGENT_ADMIN`.
- **Enhanced Communication Handling**: Improved auto-detection of communication issues between Snowflake and Dynatrace, reducing time to
  wrap up processes that were unsuccessful in sending telemetry to Dynatrace.
- **Optimized Deployment**: Monitoring grants are no longer granted during deployment time, reducing time to deploy the complete agent.
- **Cost Optimization**: Tasks are now scheduled `USING CRON` to reduce costs of running the agent by saturating usage of warehouse time.
- **Enhanced Deployment Script**: Improved interaction in `deploy.sh` when `DTAGENT_TOKEN` is not provided.

### Fixed in 0.8.3

- **BizEvents Timestamps**: Fixed timestamps of BizEvents sent from Snowflake.
- **SSL Connection Handling**: SSL connection issues are now gracefully handled during the deployment process.
- **Negative Elapsed Time**: Negative values of `snowflake.time.total_elapsed` are no longer propagated from Snowflake telemetry.
- **Problem Reporting**: Agent no longer mutes problems when processing or sending telemetry.
- **Status Logging**: Fixed how results of running Agent are reported in `STATUS.LOG_PROCESSED_MEASUREMENTS` in case of no data being
  processed.
- **Span Hierarchy**: Fixed span hierarchy reported from Snowflake query parent ID.

## Dynatrace Snowflake Observability Agent 0.8.2

Released on May 20, 2025.

### Breaking Changes in 0.8.2

- **Multi-Config Deployment**: Configuration is now expected to be a JSON array of objects. Dynatrace Snowflake Observability Agent is
  deployed to all specified configurations, with keys from the first configuration taking precedence in case of conflicts.
- **Users Plugin**: Now sends all user-related information as logs.
- **Timestamp-Triggered Events**: The name of the timestamp field that triggered the event is now sent as the value of the
  `snowflake.event.trigger` field in the event.

### Plugins Updated in 0.8.2

- **Active Queries**:
  - Introduced a configurable fast mode via the `PLUGINS.ACTIVE_QUERIES.FAST_MODE` key. The existing filter from
    `PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` remains available and is applied in addition to the mode.
  - Updated `MONITOR` privileges granted to Dynatrace Snowflake Observability Agent roles to ensure visibility into all queries.
- **Users**: Added multiple monitoring modes: `DIRECT_ROLES`, `ALL_ROLES`, and `ALL_PRIVILEGES`. See the "Users Plugin" section for more
  details.
- **Query History**: Improved performance by accelerating the process of granting Dynatrace Snowflake Observability Agent the necessary
  permissions to monitor all warehouses.

### Added in 0.8.2

- **Communication Failure Handling**: Dynatrace Snowflake Observability Agent now aborts execution upon persistent communication issues. A
  task status BizEvent is sent with `dsoa.task.exec.status` set to `FAILED`, including details of the last failed connection attempt.

### Fixed in 0.8.2

- **Teardown Process**: Correctly tears down tagged instances.
- **Span Event Reporting**: Removed the hard limit of 128 span events. The limit is now configurable via `OTEL.SPANS.MAX_EVENT_COUNT`.
- **Spans for Queries**: Fixed the problem with a hierarchy of query calls not being represented by a hierarchy of spans (_0.8.2 Hotfix 1_).
- **Self-Monitoring Configuration**: Plugin default configurations no longer overwrite self-monitoring settings.
- **Self-Monitoring BizEvents**: BizEvents are now sent by default when Dynatrace Snowflake Observability Agent is deployed and executed.

## Dynatrace Snowflake Observability Agent 0.8.1

Released on Mar 24, 2025.

### Breaking Changes in 0.8.1

- **Active Queries**: The plugin no longer reports a summary of query statuses since the last run. By default, only queries with
  `snowflake.query.execution_status` set to `RUNNING` are reported.
- **Event Log**: Entries are now reported as OTEL logs instead of events.
- **Attribute Name Changes**: Corrected typos in attribute names: `authentication.factor.first`, `authentication.factor.second`,
  `snowflake.task.run.scheduled_from`.

### New Plugins in 0.8.1

- **Data Schema**: Enables monitoring of data schema changes. Reports on objects (tables, schemas, databases) modified by DDL queries.

### Plugins Updated in 0.8.1

- **Active Queries**: Improved performance by reporting only RUNNING queries.
- **Resource Monitors**: Added `snowflake.warehouse.is_unmonitored` attribute. Log entries marked as `WARNING` for warehouses missing
  resource monitors and `ERROR` for accounts missing global resource monitors.
- **Event Log**: Metric entries are now reported as Dynatrace metrics, and traces/spans as OTEL traces/spans, reusing `trace_id` and
  `span_id` generated by Snowflake.
- **Event Log**: Old entries are cleaned up based on their timestamp compared to the `PLUGINS.EVENT_LOG.RETENTION_HOURS` configuration
  option.
- **Trust Center**: Sends all information as logs and metrics, and only critical findings as problem events.

### Added in 0.8.1

- **Documentation**: Includes complete chapters on Data Platform Observability and Dynatrace Snowflake Observability Agent architecture.
- **Bill of Materials**: Lists Snowflake objects delivered and referenced by Dynatrace Snowflake Observability Agent.
- **New Attribute**: `deployment.environment.tag` helps identify Dynatrace Snowflake Observability Agent instances by `CORE.TAG` value.

### Improved in 0.8.1

- **Code Quality**: Multiple improvements, including automated code quality checks and using YAML format for semantic dictionary
  `instruments-def` files.
- **Telemetry**: `dsoa.task.exec.id` is now shared among all telemetry sent in a given run of the plugin, even if different types of objects
  are being sent.
- **Documentation**: Improved clarity on how each plugin sends telemetry data, specifying what is sent as logs, spans, events, bizevents, or
  metrics.

### Fixed in 0.8.1

- **Active Queries**: Long-running queries are reported each time the plugin executes. If a query remains `RUNNING` for an hour, it will be
  reported 5 times with the default 10-minute interval.
- **Query History**: Now reports queries executed by external tasks or those without `snowflake.query.parent_id` in the `QUERY_HISTORY`
  view.
- **Trust Center**: Correctly reports `status.message` after changes to the content of `SCANNER_NAME` in `TRUST_CENTER.FINDINGS`.
- **Event Log**: Correctly runs in multitenancy mode.
- Code Adjustments: Correctly sends complex objects after migrating to the new version of OTEL libraries.
- Teardown Process: Removes resource monitors associated with the Dynatrace Snowflake Observability Agent instance being removed.

## Dynatrace Snowflake Observability Agent 0.8.0

Released on Jan 9, 2025.

### Breaking Changes in 0.8.0

- **Dimension, Attribute, and Metric Names**: Refactored for aligned, easier-to-work-with semantics.
- **Configuration Refactored**: Both JSON files and `CONFIG.CONFIGURATIONS` representation have been refactored to simplify changes,
  including the ability to reconfigure and disable each plugin separately.

### New Plugins in 0.8.0

- **Shares**: Reports on tables within outbound and inbound shares to track broken ones.
- **Event Usage**: Provides information on the history of data loaded into Snowflake event tables, reporting findings from the
  `EVENT_USAGE_HISTORY` view.

### Plugins Updated in 0.8.0

- **Users**: Added support for key-pair rotation.
- **Query History**: Added support for query retry (time and cause) and fault handling time. Also, information on query acceleration
  estimates is now automatically added for slower queries.

### Added in 0.8.0

- Support for sending Events and BizEvents.
- The new `APP.SEND_TELEMETRY()` procedure allows sending data from tables, views, or arrays/objects as selected telemetry types to
  Dynatrace.
- You can now configure only selected plugins to be active.
- Severe issues in the monitored Snowflake environment are sent directly as Dynatrace Problem events.
- Complete documentation is now available in PDF form.
- Dynatrace Snowflake Observability Agent tasks are reported via BizEvents.
- A self-monitoring dashboard has been added.

### Improved in 0.8.0

- Stored procedures now return meaningful, human-readable status on successful runs or error messages in case of issues.
- Event information is now sent as events instead of logs.
- More telemetry attributes are now reported as metric dimensions.

### Fixed in 0.8.0

- All queries are now reported as span traces in the Query History.
- The Dynatrace API Key is automatically deployed during initial setups.
- Re-deploying Dynatrace Snowflake Observability Agent runs without issues.

## Dynatrace Snowflake Observability Agent 0.7.3

Released on Nov 29, 2024.

### New Plugins in 0.7.3

- **Dynamic Tables**: Enables tracking the availability and performance of running Snowflake dynamic table refreshes. The telemetry is based
  on checking three functions: `INFORMATION_SCHEMA.DYNAMIC_TABLES()`, `INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY()`, and
  `INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY()`.

### Added in 0.7.3

- Added support for multitenancy, enabling telemetry to be sent to multiple Dynatrace tenants from a single Snowflake account.

## Dynatrace Snowflake Observability Agent 0.7.2

Released on Oct 8, 2024.

### New Plugins in 0.7.2

- **Active Queries**: Lists currently running queries and tracks the status of queries that finished since the last check. Reports findings
  from the `INFORMATION_SCHEMA.QUERY_HISTORY()` function, providing details on compilation and running times.

### Added in 0.7.2

- Pickle for testing of the Users plugin.
- Copyright statements to the code.

### Fixed in 0.7.2

- Issues with reporting metrics from the Budgets plugin.
- Granting monitoring access for the role `DTAGENT_VIEWER` on new warehouses.
- Self-monitoring issues, with plugins not reporting once their execution is finished.
- Warehouse usage views filtering, to avoid sending the same entries multiple times.

## Dynatrace Snowflake Observability Agent 0.7.1

Released on Sep 25, 2024.

### Added in 0.7.1

- Possibility of using customer-owned account event tables instead of `EVENT_LOG`.
- Automatically disabling the Trust Center plugin if Trust Center findings are not enabled by the admin.
- Resource monitor as a dimension for warehouse monitoring settings.
- Ability to define only modified configuration values in per-env config file.

### Fixed in 0.7.1

- Budget task by adjusting timestamps in plugin views.
- DT token is no longer visible in query logs.
- DT token is no longer visible in Snowflake query history.

### Changed in 0.7.1

- Configuration deployment is resilient to providing incomplete configuration information.
- Transposed `CONFIG.CONFIGURATION` table to make it easier for extending. Refactored related code.
- Updated dashboards.

## Dynatrace Snowflake Observability Agent 0.7.0

Released on Sep 12, 2024.

### New Plugins in 0.7.0

- **Budgets**: Monitors budgets, resources linked to them, and their expenditures. Allows managing the Dynatrace Snowflake Observability
  Agent’s own budget, reporting on all budgets within the account, including their details, spending limit, and recent spending.
- **Tasks**: Provides information regarding the last performed serverless tasks, including credits used, timestamps, and IDs of the
  warehouse and database the task is performed on.
- **Warehouse Usage**: Provides detailed information regarding warehouses' credit usage, workload, and events triggered on them, based on
  `WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, and `WAREHOUSE_METERING_HISTORY`.

### Added in 0.7.0

- Updating configuration table when deployment procedure is called without parameters.
- `README.md` and `INSTALL.md` files.
- Query quality monitoring dashboard.
- BI ETL operations log dashboard.
- Warehouses and resource monitors dashboard.
- Snowflake security dashboard.
- Snowflake security anomaly detection workflow.
- Data volume anomaly detection workflow.
- `test/test_utils.py` file, cleaned and simplified tests.

### Fixed in 0.7.0

- Generic method `Plugin::_log_entries()`.
- Issues with connecting to Snowflake with a custom connection name.
- Missing table information in query history view.

### Changed in 0.7.0

- Cleaned up semantics.
- Updated dashboards, workflows, and anomaly detection to new semantics (post-cleanup).
- Migrated metric extraction rules to DQL to unlock PPX/OpenPipeline.

## Dynatrace Snowflake Observability Agent 0.6.0

Released on Aug 30, 2024.

### New Plugins in 0.6.0

- **Login History**: Provides details about login and session history from `V_LOGIN_HISTORY` and `V_SESSIONS`, including user IDs, error
  codes, connection types, timestamps, and session details.
- **Trust Center**: Evaluates and monitors accounts for security, downloading data from the `TRUST_CENTER.FINDINGS` view and providing
  information on scanner details and at-risk entities.

### Added in 0.6.0

- Enabled trimming `event_log` table to the last 24 hours.
- Setting context in which spans and logs are generated.
- Analyzing only the top N slowest queries with query operator stats.

### Fixed in 0.6.0

- Tasks and procedures are not run by `ACCOUNTADMIN` nor `SECURITYADMIN`.
- Sending `processed_last_timestamp` as a string to `DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS`.

### Changed in 0.6.0

- Optimized memory usage in DT_AGENT.
- Refactored code to replace globals with encapsulating classes.
- Optimized Dynatrace Snowflake Observability Agent credit usage.
- Expanded `event_log` attributes into separate log attributes.

## Dynatrace Snowflake Observability Agent 0.5.0

Released on May 21, 2024.

### New Plugins in 0.5.0

- **Resource Monitors**: Reports the state of resource monitors and analyzes warehouse conditions, providing detailed logs and warnings
  about monitor setups and warehouse states.

### Added in 0.5.0

- Enabled tracing of slow queries.
- Mapped metrics to custom device entities.
- Implemented metrics based on table and database volume.
- Sending augmented query history as logs with related trace.id.
- Recursive query dependencies analysis into multilevel span-trace hierarchies.
- Retrying API posts to Dynatrace if connection fails.
- Support for internal Snowflake logging.
- Sending recently logged information in `event_log` to table to DT as logs.

### Fixed in 0.5.0

- `get_query_operator_stats` to analyze each query independently to avoid queries overflowing Snowflake memory.

### Changed in 0.5.0

- Improved dimension sets with metrics.

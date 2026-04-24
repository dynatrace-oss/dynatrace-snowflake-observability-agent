# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

> [!NOTE] Note:
> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
>
> Detailed technical changes and implementation notes are available in [DEVLOG.md](DEVLOG.md).

## [Unreleased]

### Added

- Cold tables identification plugin: identifies tables with no recent query access (default: >90 days) to enable FinOps teams to find candidates for archiving, dropping, or tiering to lower-cost storage. Reduces storage costs by sunsetting unused tables. See [Cold Tables plugin](PLUGINS.md#cold_tables_info_sec).
- New `metering` plugin reporting credit consumption across all Snowflake service types via `METERING_HISTORY`. Covers auto-clustering, pipes, serverless tasks, AI services, replication, and more with `service_type` dimension for FinOps cost attribution.
- **Interactive deployment wizard** (`--interactive` flag): Guides users through 5-phase configuration (core config, deployment scope, plugin selection, advanced settings, telemetry settings). Auto-triggered when config file is missing. Generates `conf/config-$ENV.yml`. Includes HTTPS reachability probes for DT tenant and Snowflake account (warn-only, non-blocking). Supports `--dry-run` (print config to stdout) and `--output=<file>` (write to custom path).
- **New `deploy.sh` flags**: `--env=<ENV>` (replaces positional arg), `--interactive` (launch wizard), `--defaults` (generate minimal config non-interactively). Positional `$ENV` still supported with deprecation warning for backward compatibility.
- **Shared bash library** (`scripts/deploy/lib.sh`): Logging, prompt helpers, validators (DT tenant, Snowflake account, tokens) for reuse across deployment scripts.

### Changed

- Updated `snowflake-snowpark-python` minimum version to `>=1.49.0` (was `>=1.48.1`). Python version constraint
  remains `<3.14` — bottleneck is `snowflake==1.12.0`, not snowpark. See [DEVLOG.md](DEVLOG.md) for full audit details.

### Deprecated

- `event_usage` plugin is deprecated and disabled by default. Use `metering` instead. Will be removed in 0.9.6. To reproduce the same data, filter by `snowflake.service.type == "TELEMETRY_DATA_INGEST"`.

### Fixed

- The `event_log` plugin setup procedure now adapts to Snowflake BCR Bundle 2026\_02 (`LOG_EVENT_LEVEL` parameter).
  On accounts where the BCR is active, `LOG_EVENT_LEVEL = INFO` is set at database level, and also at account
  level when DSOA provisions and owns the event table, so events emitted by DSOA procedures continue to reach the
  event table. When a pre-existing/custom event table is used, the account-level parameter is left unchanged. On
  pre-BCR accounts the new parameter is detected as absent and the change is skipped gracefully. See
  [DEVLOG.md](DEVLOG.md) for details.

- Config changes on redeploy now take full effect: the config upload procedure uses DELETE + INSERT (full replace) instead of an additive MERGE, so entries removed from the YAML (e.g. a plugin's `is_enabled: true`) are also removed from Snowflake. Previously, stale config entries could override a new `disabled_by_default: true` setting.
- Disabled plugins now have their Snowflake tasks suspended automatically on every redeploy, regardless of deploy scope. The deploy script injects `ALTER TASK IF EXISTS … SUSPEND` for every excluded plugin (including multi-task and admin-task plugins) before executing the deploy SQL. Previously, stale tasks continued running and consuming compute credits after a plugin was disabled.

See [DEVLOG.md](DEVLOG.md) for implementation details.

## [0.9.4] - 2026-04-14

### Added

- Pipes monitoring plugin.
- Six new dashboards: Budgets & FinOps, Data Volume & Storage, Query Deep Dive, Shares & Governance, Snowpipes Monitoring, and Tasks & Pipelines.
- Five Davis AI-powered anomaly detection workflows: credits exhaustion, data volume anomaly, dynamic table drift, query slowdown, and table performance degradation.
- Dashboard and workflow deployment automation via `scripts/deploy/deploy_dt_assets.sh` with `dtctl` integration.
- Per-plugin configurable lookback time for historical data catchup.
- Support for `SNOWFLAKE.TELEMETRY.EVENTS` as account-level event table.
- AI-assisted development infrastructure: GitHub Copilot instructions with architecture context and safety guardrails; OpenCode agent configuration with seven domain-specific skills (`plugin-development`, `dynatrace-dashboard`, `dynatrace-workflow`, `qa-runner`, `snowflake-synthetic`, `pr-reviewer`, `dashboard-docs`); semantic telemetry definitions as AI context; scaffolded `.github/context/` for private developer planning.

### Changed

- **BREAKING**: `db.collection.name` now contains bare table name (e.g., `ORDERS`) instead of FQN. Use new `snowflake.table.full_name` attribute for fully-qualified names.
- **BREAKING**: Task timestamp fields (`snowflake.task.run.scheduled_time`, etc.) now use epoch nanoseconds instead of ISO 8601 strings.
- Event log plugin now reports `WARN`/`ERROR` entries from all `DTAGENT_*_DB` instances by default (set `cross_tenant_monitoring: false` to opt out).
- Shares & Governance dashboard tile 14 renamed to "Shares No Longer Observed" with improved 7-day log-history detection.
- Updated Costs Monitoring, Query Performance, Query Quality, Self-Monitoring, and Snowflake Security dashboards with improved tiles and semantics alignment.
- Migrated all stored procedures to `execute as caller` for improved security (`P_GRANT_IMPORTED_PRIVILEGES` remains `execute as owner` due to privilege requirements).
- Test fixtures migrated from binary `.pkl` to human-readable `.ndjson` format.

### Fixed

- Dynamic table scheduling state fields now emit `NULL` instead of empty strings when absent.
- Dynamic table grant granularity now matches `include` pattern scope (database/schema/table level).
- Span timestamps corrected to prevent re-processing after agent restart.
- Log `observed_timestamp` field now uses nanoseconds per OTLP specification.
- Budget spending view date filtering now uses day granularity to include today's data.
- Deploy script TAG substitution no longer replaces identifiers inside config string values.
- Budget grant procedure handles imported/shared databases and application-owned budgets.

## [0.9.3.1] - 2026-03-18

### Fixed

- **DTAGENT_ADMIN Role Privileges**: Fixed critical bug where `DTAGENT_ADMIN` role was missing `DTAGENT_VIEWER` role privileges.

## [0.9.3] - 2026-02-12

### Added

- Admin deployment scope for administrative operations, enabling granular control via `--scope=admin` option.
- Ability to customize names for all Snowflake objects (database, warehouse, resource monitor, roles). Set admin role or resource monitor to `"-"` to skip their creation entirely.
- Upgrade process with `--scope=upgrade --from-version=VERSION` parameters, supporting custom queries for version migrations.
- Bill of Materials files as part of the documentation with structured tables.

### Changed

- **BREAKING**: Introduced `DTAGENT_OWNER` role that owns all SnowAgent artifacts. The `DTAGENT_ADMIN` role is now reserved exclusively for elevated administrative privileges, while `DTAGENT_VIEWER` handles regular telemetry-related operations.
- **BREAKING**: Deployment and upgrade now have separate permission requirements with the new owner-admin-viewer role separation model.
- **BREAKING**: Configuration files are now in YAML format. Multi-configuration deployment is no longer supported. Use `convert_config_to_yaml.sh` script to convert existing JSON files.
- **BREAKING**: Reorganized Snowflake-related configuration into nested `core.snowflake` structure.
- Implemented role hierarchy with `ACCOUNTADMIN` → `DTAGENT_OWNER` → `DTAGENT_VIEWER` as primary hierarchy and `DTAGENT_OWNER` → `DTAGENT_ADMIN` as optional admin branch.
- Isolated administrative operations in dedicated admin scripts with automated tests to enforce separation.
- YAML format with lowercase keys to match Snowflake configuration table paths.
- Refactored `deploy.sh` with improved parameter handling using named parameters (`--scope`, `--from-version`, `--output-file`, `--options`).
- Introduced well-defined deployment scopes (`init`, `admin`, `setup`, `plugins`, `config`, `agents`, `apikey`, `all`, `teardown`, `upgrade`).
- The `apikey` deployment scope can now be combined with other scopes.
- When admin role or resource monitor is disabled via `"-"`, related SQL code is automatically excluded from deployment scripts.
- Enabled deployment with only selected plugins based on use case requirements.
- Data retention on `DTAGENT_DB` permanent tables now configurable (default: 1 day).
- Extended code quality checks to include `build/*.py` files.

### Fixed

- Timestamps in logs being sent as nanoseconds instead of milliseconds.
- Duplicated resource attribute fields in event log entries.
- Array-type dimensions (e.g., `db.snowflake.dbs`, `db.snowflake.tables`) were being sent as Python list representations causing 400 Bad Request errors. Arrays are now properly converted to comma-separated strings.

## [0.9.2] - 2025-11-24

### Added

- Example dashboards to help users visualize and interpret telemetry data, including costs monitoring, self-monitoring, and Snowflake security dashboards.
- Options to configure minimum query runtime and the maximum number of top queries for deeper analysis.
- Support for `RECORD_ATTRIBUTES` in event log metrics.
- Suite of code quality checks to the automated build process.
- Comprehensive troubleshooting guide for debugging data delivery issues.

### Changed

- **BREAKING**: Self-monitoring telemetry now has `dsoa.run.context` set to `self_monitoring` (underscore) instead of `self-monitoring` (hyphen).
- Telemetry types (e.g., events, spans) can now be excluded, either globally or on a per-plugin basis.
- Data Schema plugin now reports on objects modified by DDL queries as events.
- Resource Monitors and Users plugins now use explicit column selection to prevent errors from column order changes.
- Telemetry sender now supports labeling and classification of telemetry calls and `SHOW` statements.
- Event handling now supports sending multiple events in a single call.
- Plugin and context names are now available as metric dimensions.
- Improved performance of reading and processing telemetry data. Added safety limits and ordering to event log queries.
- Agent execution now returns detailed status information, including the number of telemetry objects sent by type, plugin, and run context.
- Deployment process now reports its start and finish as BizEvents.
- API post timeout and retry delay are now configurable for metrics and events.
- Documentation improved for easier navigation as online GitHub pages.

## [0.9.1] - 2025-09-18

### Added

- Modular documentation structure with separate files (`PLUGINS.md`, `SEMANTICS.md`, `APPENDIX.md`).

### Changed

- `SEND_TELEMETRY` procedure now supports `SHOW` statements, enabling more flexible custom queries.

### Fixed

- Resource Monitors queries now use explicit column selection to prevent errors from column order changes in `SHOW WAREHOUSES`.
- Query History upgrade for procedure `P_REFRESH_RECENT_QUERIES` to work correctly when upgrading from versions prior to 0.8.3.

## [0.9.0] - 2025-07-25

### Added

- **Open Source Release**: The project is now available as an Open Source project on GitHub under the permissive MIT license.

## [0.8.3] - 2025-07-14

### Changed

- **Meta-field semantics**: In order to align with rebranding to new official name of Dynatrace Snowflake Observability Agent (DSOA) or
  Dynatrace SnowAgent in short, a number of field names had to be refactored.

### Plugins Updated

- **Shares**: Reduced the number of events sent by the plugin to improve performance.
- **Query History**: Empty queries executed by SYSTEM user at `COMPUTE_SERVICE_WH_*` are no longer reported to Dynatrace.

### Added

- **Tutorial**: Step-by-step debug tutorial to check if telemetry on currently running queries is correctly delivered via active_queries
  plugin to Dynatrace.
- **Test Suite**: Test suite now ensures that standardized views deliver `TIMESTAMP` column.

### Improved

- **Improved Security Model**: Basic plugin tasks are now executed as `DTAGENT_VIEWER`, with only special tasks executed as `DTAGENT_ADMIN`.
- **Enhanced Communication Handling**: Improved auto-detection of communication issues between Snowflake and Dynatrace, reducing time to
  wrap up processes that were unsuccessful in sending telemetry to Dynatrace.
- **Optimized Deployment**: Monitoring grants are no longer granted during deployment time, reducing time to deploy the complete agent.
- **Cost Optimization**: Tasks are now scheduled `USING CRON` to reduce costs of running the agent by saturating usage of warehouse time.
- **Enhanced Deployment Script**: Improved interaction in `deploy.sh` when `DTAGENT_TOKEN` is not provided.

### Fixed

- **BizEvents Timestamps**: Fixed timestamps of BizEvents sent from Snowflake.
- **SSL Connection Handling**: SSL connection issues are now gracefully handled during the deployment process.
- **Negative Elapsed Time**: Negative values of `snowflake.time.total_elapsed` are no longer propagated from Snowflake telemetry.
- **Problem Reporting**: Agent no longer mutes problems when processing or sending telemetry.
- **Status Logging**: Fixed how results of running Agent are reported in `STATUS.LOG_PROCESSED_MEASUREMENTS` in case of no data being
  processed.
- **Span Hierarchy**: Fixed span hierarchy reported from Snowflake query parent ID.

## [0.8.2] - 2025-05-20

### Changed

- **Multi-Config Deployment**: Configuration is now expected to be a JSON array of objects. Dynatrace Snowflake Observability Agent is
  deployed to all specified configurations, with keys from the first configuration taking precedence in case of conflicts.
- **Users Plugin**: Now sends all user-related information as logs.
- **Timestamp-Triggered Events**: The name of the timestamp field that triggered the event is now sent as the value of the
  `snowflake.event.trigger` field in the event.

### Plugins Updated

- **Active Queries**:
  - Introduced a configurable fast mode via the `PLUGINS.ACTIVE_QUERIES.FAST_MODE` key. The existing filter from
    `PLUGINS.ACTIVE_QUERIES.REPORT_EXECUTION_STATUS` remains available and is applied in addition to the mode.
  - Updated `MONITOR` privileges granted to Dynatrace Snowflake Observability Agent roles to ensure visibility into all queries.
- **Users**: Added multiple monitoring modes: `DIRECT_ROLES`, `ALL_ROLES`, and `ALL_PRIVILEGES`. See the "Users Plugin" section for more
  details.
- **Query History**: Improved performance by accelerating the process of granting Dynatrace Snowflake Observability Agent the necessary
  permissions to monitor all warehouses.

### Added

- **Communication Failure Handling**: Dynatrace Snowflake Observability Agent now aborts execution upon persistent communication issues. A
  task status BizEvent is sent with `dsoa.task.exec.status` set to `FAILED`, including details of the last failed connection attempt.

### Fixed

- **Teardown Process**: Correctly tears down tagged instances.
- **Span Event Reporting**: Removed the hard limit of 128 span events. The limit is now configurable via `OTEL.SPANS.MAX_EVENT_COUNT`.
- **Spans for Queries**: Fixed the problem with a hierarchy of query calls not being represented by a hierarchy of spans (*0.8.2 Hotfix 1*).
- **Self-Monitoring Configuration**: Plugin default configurations no longer overwrite self-monitoring settings.
- **Self-Monitoring BizEvents**: BizEvents are now sent by default when Dynatrace Snowflake Observability Agent is deployed and executed.

## [0.8.1] - 2025-03-24

### Changed

- **Active Queries**: The plugin no longer reports a summary of query statuses since the last run. By default, only queries with
  `snowflake.query.execution_status` set to `RUNNING` are reported.
- **Event Log**: Entries are now reported as OTEL logs instead of events.
- **Attribute Name Changes**: Corrected typos in attribute names: `authentication.factor.first`, `authentication.factor.second`,
  `snowflake.task.run.scheduled_from`.

### New Plugins

- **Data Schema**: Enables monitoring of data schema changes. Reports on objects (tables, schemas, databases) modified by DDL queries.

### Plugins Updated

- **Active Queries**: Improved performance by reporting only RUNNING queries.
- **Resource Monitors**: Added `snowflake.warehouse.is_unmonitored` attribute. Log entries marked as `WARNING` for warehouses missing
  resource monitors and `ERROR` for accounts missing global resource monitors.
- **Event Log**: Metric entries are now reported as Dynatrace metrics, and traces/spans as OTEL traces/spans, reusing `trace_id` and
  `span_id` generated by Snowflake.
- **Event Log**: Old entries are cleaned up based on their timestamp compared to the `PLUGINS.EVENT_LOG.RETENTION_HOURS` configuration
  option.
- **Trust Center**: Sends all information as logs and metrics, and only critical findings as problem events.

### Added

- **Documentation**: Includes complete chapters on Data Platform Observability and Dynatrace Snowflake Observability Agent architecture.
- **Bill of Materials**: Lists Snowflake objects delivered and referenced by Dynatrace Snowflake Observability Agent.
- **New Attribute**: `deployment.environment.tag` helps identify Dynatrace Snowflake Observability Agent instances by `CORE.TAG` value.

### Improved

- **Code Quality**: Multiple improvements, including automated code quality checks and using YAML format for semantic dictionary
  `instruments-def` files.
- **Telemetry**: `dsoa.task.exec.id` is now shared among all telemetry sent in a given run of the plugin, even if different types of objects
  are being sent.
- **Documentation**: Improved clarity on how each plugin sends telemetry data, specifying what is sent as logs, spans, events, bizevents, or
  metrics.

### Fixed

- **Active Queries**: Long-running queries are reported each time the plugin executes. If a query remains `RUNNING` for an hour, it will be
  reported 5 times with the default 10-minute interval.
- **Query History**: Now reports queries executed by external tasks or those without `snowflake.query.parent_id` in the `QUERY_HISTORY`
  view.
- **Trust Center**: Correctly reports `status.message` after changes to the content of `SCANNER_NAME` in `TRUST_CENTER.FINDINGS`.
- **Event Log**: Correctly runs in multitenancy mode.
- Code Adjustments: Correctly sends complex objects after migrating to the new version of OTEL libraries.
- Teardown Process: Removes resource monitors associated with the Dynatrace Snowflake Observability Agent instance being removed.

## [0.8.0] - 2025-01-09

### Changed

- **Dimension, Attribute, and Metric Names**: Refactored for aligned, easier-to-work-with semantics.
- **Configuration Refactored**: Both JSON files and `CONFIG.CONFIGURATIONS` representation have been refactored to simplify changes,
  including the ability to reconfigure and disable each plugin separately.

### New Plugins

- **Shares**: Reports on tables within outbound and inbound shares to track broken ones.
- **Event Usage**: Provides information on the history of data loaded into Snowflake event tables, reporting findings from the
  `EVENT_USAGE_HISTORY` view.

### Plugins Updated

- **Users**: Added support for key-pair rotation.
- **Query History**: Added support for query retry (time and cause) and fault handling time. Also, information on query acceleration
  estimates is now automatically added for slower queries.

### Added

- Support for sending Events and BizEvents.
- The new `APP.SEND_TELEMETRY()` procedure allows sending data from tables, views, or arrays/objects as selected telemetry types to
  Dynatrace.
- You can now configure only selected plugins to be active.
- Severe issues in the monitored Snowflake environment are sent directly as Dynatrace Problem events.
- Complete documentation is now available in PDF form.
- Dynatrace Snowflake Observability Agent tasks are reported via BizEvents.
- A self-monitoring dashboard has been added.

### Improved

- Stored procedures now return meaningful, human-readable status on successful runs or error messages in case of issues.
- Event information is now sent as events instead of logs.
- More telemetry attributes are now reported as metric dimensions.

### Fixed

- All queries are now reported as span traces in the Query History.
- The Dynatrace API Key is automatically deployed during initial setups.
- Re-deploying Dynatrace Snowflake Observability Agent runs without issues.

## [0.7.3] - 2024-11-29

### Added

- **Dynamic Tables**: Enables tracking the availability and performance of running Snowflake dynamic table refreshes. The telemetry is based
  on checking three functions: `INFORMATION_SCHEMA.DYNAMIC_TABLES()`, `INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY()`, and
  `INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY()`.

### Added

- Added support for multitenancy, enabling telemetry to be sent to multiple Dynatrace tenants from a single Snowflake account.

## [0.7.2] - 2024-10-08

### Added

- **Active Queries**: Lists currently running queries and tracks the status of queries that finished since the last check. Reports findings
  from the `INFORMATION_SCHEMA.QUERY_HISTORY()` function, providing details on compilation and running times.

### Added

- Fixtures for testing of the Users plugin.
- Copyright statements to the code.

### Fixed

- Issues with reporting metrics from the Budgets plugin.
- Granting monitoring access for the role `DTAGENT_VIEWER` on new warehouses.
- Self-monitoring issues, with plugins not reporting once their execution is finished.
- Warehouse usage views filtering, to avoid sending the same entries multiple times.

## [0.7.1] - 2024-09-25

### Added

- Possibility of using customer-owned account event tables instead of `EVENT_LOG`.
- Automatically disabling the Trust Center plugin if Trust Center findings are not enabled by the admin.
- Resource monitor as a dimension for warehouse monitoring settings.
- Ability to define only modified configuration values in per-env config file.

### Fixed

- Budget task by adjusting timestamps in plugin views.
- DT token is no longer visible in query logs.
- DT token is no longer visible in Snowflake query history.

### Changed

- Configuration deployment is resilient to providing incomplete configuration information.
- Transposed `CONFIG.CONFIGURATION` table to make it easier for extending. Refactored related code.
- Updated dashboards.

## [0.7.0] - 2024-09-12

### Added

- **Budgets**: Monitors budgets, resources linked to them, and their expenditures. Allows managing the Dynatrace Snowflake Observability
  Agent’s own budget, reporting on all budgets within the account, including their details, spending limit, and recent spending.
- **Tasks**: Provides information regarding the last performed serverless tasks, including credits used, timestamps, and IDs of the
  warehouse and database the task is performed on.
- **Warehouse Usage**: Provides detailed information regarding warehouses' credit usage, workload, and events triggered on them, based on
  `WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, and `WAREHOUSE_METERING_HISTORY`.

### Added

- Updating configuration table when deployment procedure is called without parameters.
- `README.md` and `INSTALL.md` files.
- Query quality monitoring dashboard.
- BI ETL operations log dashboard.
- Warehouses and resource monitors dashboard.
- Snowflake security dashboard.
- Snowflake security anomaly detection workflow.
- Data volume anomaly detection workflow.
- `test/test_utils.py` file, cleaned and simplified tests.

### Fixed

- Generic method `Plugin::_log_entries()`.
- Issues with connecting to Snowflake with a custom connection name.
- Missing table information in query history view.

### Changed

- Cleaned up semantics.
- Updated dashboards, workflows, and anomaly detection to new semantics (post-cleanup).
- Migrated metric extraction rules to DQL to unlock PPX/OpenPipeline.

## [0.6.0] - 2024-08-30

### Added

- **Login History**: Provides details about login and session history from `V_LOGIN_HISTORY` and `V_SESSIONS`, including user IDs, error
  codes, connection types, timestamps, and session details.
- **Trust Center**: Evaluates and monitors accounts for security, downloading data from the `TRUST_CENTER.FINDINGS` view and providing
  information on scanner details and at-risk entities.

### Added

- Enabled trimming `event_log` table to the last 24 hours.
- Setting context in which spans and logs are generated.
- Analyzing only the top N slowest queries with query operator stats.

### Fixed

- Tasks and procedures are not run by `ACCOUNTADMIN` nor `SECURITYADMIN`.
- Sending `processed_last_timestamp` as a string to `DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS`.

### Changed

- Optimized memory usage in DT_AGENT.
- Refactored code to replace globals with encapsulating classes.
- Optimized Dynatrace Snowflake Observability Agent credit usage.
- Expanded `event_log` attributes into separate log attributes.

## [0.5.0] - 2024-05-21

### Added

- **Resource Monitors**: Reports the state of resource monitors and analyzes warehouse conditions, providing detailed logs and warnings
  about monitor setups and warehouse states.

### Added

- Enabled tracing of slow queries.
- Mapped metrics to custom device entities.
- Implemented metrics based on table and database volume.
- Sending augmented query history as logs with related trace.id.
- Recursive query dependencies analysis into multilevel span-trace hierarchies.
- Retrying API posts to Dynatrace if connection fails.
- Support for internal Snowflake logging.
- Sending recently logged information in `event_log` to table to DT as logs.

### Fixed

- `get_query_operator_stats` to analyze each query independently to avoid queries overflowing Snowflake memory.

### Changed

- Improved dimension sets with metrics.

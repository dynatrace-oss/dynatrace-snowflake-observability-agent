# Appendix

- [Appendix A: Migrating semantics from version 0.7 to 0.8](#appendix-a-sec)
- [Appendix B: Migrating meta-field semantics to version 0.8.3 or higher](#appendix-b-sec)
- [Appendix C: Migrating field names to version 1.0.0 or higher](#appendix-c-sec)

<a name="appendix-a-sec"></a>

## Appendix A: Migrating semantics from version 0.7 to 0.8

In version 0.8, the semantics of the telemetry sent by Dynatrace Snowflake Observability Agent underwent significant refactoring to improve
compatibility with industry standards such as OpenTelemetry and the naming conventions in the Dynatrace Semantic Dictionary. This ensures
better interoperability and adherence to widely accepted practices.

To update to the new version, users need to run the `refactor_field_names.sh` script, which is included in the package. This script requires
two parameters:

1. **fields-refactoring.csv**: This file, provided in the package, contains the mapping of old field names to new field names.
2. **Exported Data Folder**: The location of the folder containing all exported dashboards, workflows, and other relevant data.

By running the script with these parameters, it will automatically update all semantics to be compatible with version 0.8. This process
ensures that all field names are correctly updated according to the new naming conventions.

Below is a table that lists all the changes made to the field names. This table provides a clear mapping between the old names (version 0.7)
and the new names (version 0.8):

### Field Name Mapping

<!-- do not correct any typos in first column; they were in the previous release and are fixed now -->

| 0.7 Name                                                 | 0.8 Name                                      |
| -------------------------------------------------------- | --------------------------------------------- |
| authentiacation.factor.first                             | authentication.factor.first                   |
| authentiacation.factor.second                            | authentication.factor.second                  |
| snowflake.task.run.sheduled_from                         | snowflake.task.run.scheduled_from             |
| telemetry.exporter.module                                | dsoa.run.context                              |
| snowflake.resource_monitor.credits.quota                 | snowflake.credits.quota                       |
| snowflake.resource_monitor.credits.remaining             | snowflake.credits.quota.remaining             |
| snowflake.resource_monitor.credits.used                  | snowflake.credits.quota.used                  |
| snowflake.error_code                                     | snowflake.error.code                          |
| snowflake.error_message                                  | snowflake.error.message                       |
| snowflake.inbound_data_transfer_cloud                    | snowflake.query.data_transfer.inbound.cloud   |
| snowflake.inbound_data_transfer_region                   | snowflake.query.data_transfer.inbound.region  |
| snowflake.outbound_data_transfer_cloud                   | snowflake.query.data_transfer.outbound.cloud  |
| snowflake.outbound_data_transfer_region                  | snowflake.query.data_transfer.outbound.region |
| snowflake.query_hash                                     | snowflake.query.hash                          |
| snowflake.query_hash_version                             | snowflake.query.hash.version                  |
| snowflake.query_id                                       | snowflake.query.id                            |
| snowflake.is_client_generated_statement                  | snowflake.query.is_client_generated           |
| snowflake.query_parameterized_hash                       | snowflake.query.parametrized_hash             |
| snowflake.query_parameterized_hash_version               | snowflake.query.parametrized_hash.version     |
| snowflake.parent_query_id                                | snowflake.query.parent_id                     |
| snowflake.query_retry_cause                              | snowflake.query.retry_cause                   |
| snowflake.query_tag                                      | snowflake.query.tag                           |
| snowflake.transaction_id                                 | snowflake.query.transaction_id                |
| snowflake.role_name                                      | snowflake.role.name                           |
| snowflake.role_type                                      | snowflake.role.type                           |
| snowflake.task.instance.id                               | snowflake.task.instance_id                    |
| snowflake.user.default_namespace                         | snowflake.user.default.namespace              |
| snowflake.user.default_role                              | snowflake.user.default.role                   |
| snowflake.user.default_secondary_role                    | snowflake.user.default.secondary_role         |
| snowflake.user.default_warehouse                         | snowflake.user.default.warehouse              |
| snowflake.user.ext_authn_duo                             | snowflake.user.ext_authn.duo                  |
| snowflake.user.ext_authn_uid                             | snowflake.user.ext_authn.uid                  |
| snowflake.user.snowflake_lock                            | snowflake.user.is_locked                      |
| snowflake.user.first_name                                | snowflake.user.name.first                     |
| snowflake.user.last_name                                 | snowflake.user.name.last                      |
| snowflake.user.ownership_role                            | snowflake.user.owner                          |
| snowflake.user.all_roles                                 | snowflake.user.roles.direct                   |
| snowflake.warehouse.cluster_number                       | snowflake.warehouse.cluster.number            |
| snowflake.warehouse.cluster.count                        | snowflake.warehouse.clusters.count            |
| snowflake.warehouse.owner_role_type                      | snowflake.warehouse.owner.role_type           |
| db.snowflake.db_names                                    | db.snowflake.dbs                              |
| db.snowflake.table_names                                 | db.snowflake.tables                           |
| db.snowflake.view_names                                  | db.snowflake.views                            |
| snowflake.role_name                                      | snowflake.role.name                           |
| snowflake.budget.spending.service_type                   | snowflake.service.type                        |
| snowflake.`*`query_acceleration_bytes_scanned            | snowflake.acceleration.data.scanned           |
| snowflake.`*`query_acceleration_partitions_scanned       | snowflake.acceleration.partitions.scanned     |
| snowflake.`*`query_acceleration_upper_limit_scale_factor | snowflake.acceleration.scale_factor.max       |
| snowflake.warehouse.query_acceleration_max_scale_factor  | snowflake.acceleration.scale_factor.max       |
| snowflake.warehouse.percentage_available                 | snowflake.compute.available                   |
| snowflake.warehouse.percentage_other                     | snowflake.compute.other                       |
| snowflake.warehouse.percentage_provisioning              | snowflake.compute.provisioning                |
| snowflake.warehouse.percentage_quiescing                 | snowflake.compute.quiescing                   |
| snowflake.`*`cloud_services.credits.used                 | snowflake.credits.cloud_services              |
| snowflake.warehouse.credits.cloud_services               | snowflake.credits.cloud_services              |
| snowflake.warehouse.credits.compute                      | snowflake.credits.compute                     |
| snowflake.budget.spending_limit                          | snowflake.credits.limit                       |
| snowflake.resource_monitor.credits.quota                 | snowflake.credits.quota                       |
| snowflake.resource_monitor.credits.percentage_quota_used | snowflake.credits.quota.used_pct              |
| snowflake.resource_monitor.credits.remaining             | snowflake.credits.quota.remaining             |
| snowflake.resource_monitor.credits.used                  | snowflake.credits.quota.used                  |
| snowflake.budget.spending.credits_spent                  | snowflake.credits.spent                       |
| snowflake.event_usage.credits.used                       | snowflake.credits.used                        |
| snowflake.serverless_tasks.credits.used                  | snowflake.credits.used                        |
| snowflake.warehouse.credits.used                         | snowflake.credits.used                        |
| snowflake.`*`bytes_deleted                               | snowflake.data.deleted                        |
| snowflake.event_usage.bytes_ingested                     | snowflake.data.ingested                       |
| snowflake.`*`bytes_read_from_result                      | snowflake.data.read.from_result               |
| snowflake.`*`size.row_count                              | snowflake.data.rows                           |
| snowflake.`*`bytes_scanned                               | snowflake.data.scanned                        |
| snowflake.`*`percentage_scanned_from_cache               | snowflake.data.scanned_from_cache             |
| snowflake.`*`bytes_sent_over_the_network                 | snowflake.data.sent_over_the_network          |
| snowflake.`*`size.bytes                                  | snowflake.data.size                           |
| snowflake.`*`bytes_spilled_to_local_storage              | snowflake.data.spilled.to_local_storage       |
| snowflake.`*`bytes_spilled_to_remote_storage             | snowflake.data.spilled.to_remote_storage      |
| snowflake.`*`inbound_data_transfer_bytes                 | snowflake.data.transferred.inbound            |
| snowflake.`*`outbound_data_transfer_bytes                | snowflake.data.transferred.outbound           |
| snowflake.`*`bytes_written                               | snowflake.data.written                        |
| snowflake.`*`bytes_written_to_result                     | snowflake.data.written.to_result              |
| snowflake.`*`external_function_total_received_bytes      | snowflake.external_functions.data.received    |
| snowflake.`*`external_function_total_sent_bytes          | snowflake.external_functions.data.sent        |
| snowflake.`*`external_function_total_invocations         | snowflake.external_functions.invocations      |
| snowflake.`*`external_function_total_received_rows       | snowflake.external_functions.rows.received    |
| snowflake.`*`external_function_total_sent_rows           | snowflake.external_functions.rows.sent        |
| snowflake.warehouse.load.avg_blocked                     | snowflake.load.blocked                        |
| snowflake.warehouse.load.avg_queued_load                 | snowflake.load.queued.overloaded              |
| snowflake.warehouse.load.avg_queued_provisioning         | snowflake.load.queued.provisioning            |
| snowflake.warehouse.load.avg_running                     | snowflake.load.running                        |
| snowflake.`*`query_load_percent                          | snowflake.load.used                           |
| snowflake.`*`partitions_scanned                          | snowflake.partitions.scanned                  |
| snowflake.`*`partitions_total                            | snowflake.partitions.total                    |
| snowflake.query.count                                    | -                                             |
| snowflake.warehouse.queued_queries                       | snowflake.queries.queued                      |
| snowflake.warehouse.running_queries                      | snowflake.queries.running                     |
| snowflake.resource_monitor.warehouses.count              | snowflake.resource_monitor.warehouses         |
| snowflake.`*`rows_deleted                                | snowflake.rows.deleted                        |
| snowflake.`*`rows_inserted                               | snowflake.rows.inserted                       |
| snowflake.`*`rows_unloaded                               | snowflake.rows.unloaded                       |
| snowflake.`*`rows_updated                                | snowflake.rows.updated                        |
| snowflake.`*`rows_written_to_result                      | snowflake.rows.written_to_result              |
| snowflake.`*`last_ddl.time_since                         | snowflake.table.time_since.last_ddl           |
| snowflake.`*`last_update.time_since                      | snowflake.table.time_since.last_update        |
| snowflake.`*`child_queries_wait_time                     | snowflake.time.child_queries_wait             |
| snowflake.`*`compilation_time                            | snowflake.time.compilation                    |
| snowflake.`*`execution_time                              | snowflake.time.execution                      |
| snowflake.`*`fault_handling_time                         | snowflake.time.fault_handling                 |
| snowflake.`*`list_external_files_time                    | snowflake.time.list_external_files            |
| snowflake.`*`queued_overload_time                        | snowflake.time.queued.overload                |
| snowflake.`*`queued_provisioning_time                    | snowflake.time.queued.provisioning            |
| snowflake.`*`queued_repair_time                          | snowflake.time.repair                         |
| snowflake.`*`query_retry_time                            | snowflake.time.retry                          |
| snowflake.query.running_time                             | snowflake.time.running                        |
| snowflake.`*`total_elapsed_time                          | snowflake.time.total_elapsed                  |
| snowflake.`*`transaction_blocked_time                    | snowflake.time.transaction_blocked            |
| snowflake.trust_center.findings.count                    | snowflake.trust_center.findings               |
| snowflake.warehouse.max_cluster_count                    | snowflake.warehouse.clusters.max              |
| snowflake.warehouse.min_cluster_count                    | snowflake.warehouse.clusters.min              |
| snowflake.warehouse.started_clusters                     | snowflake.warehouse.clusters.started          |
| snowflake.otlp.debug.span_events_added                   | dsoa.debug.span.events.added                  |
| snowflake.otlp.debug.span_events_failed                  | dsoa.debug.span.events.failed                 |
| snowflake.operator_id                                    | snowflake.query.operator.id                   |
| snowflake.operator_type                                  | snowflake.query.operator.type                 |
| snowflake.operator_parent_ops                            | snowflake.query.operator.parent_ids           |
| snowflake.operator_attr                                  | snowflake.query.operator.attributes           |
| snowflake.operator_stat                                  | snowflake.query.operator.stats                |
| snowflake.operator_exec_time                             | snowflake.query.operator.time                 |
| snowflake.table.event                                    | snowflake.event.trigger                       |

`*` represents possible values that might be present as part of the field name:
`(warehouse.load.|warehouse.credits.|table.dynamic.|trust_center.|table_qs.|event_usage.|table.|budget.|budget.spending.|serverless_tasks.|resource_monitor.|warehouse.|query.)`

<a name="appendix-b-sec"></a>

## Appendix B: Migrating meta-field semantics to version 0.8.3 or higher

Version 0.8.3 aligns the naming of several meta-fields with the product's final, official name: **Dynatrace Snowflake Observability Agent**
(formerly SnowAgent). If you are upgrading from a version prior to 0.8.3, you will need to update any custom dashboards, workflows, or other
assets that rely on these fields.

The refactoring process is similar to the one described in [Appendix A](#appendix-a-sec) and uses the same `refactor_field_names.sh` script.
However, for this migration, you must use the `dsoa-fields-refactoring.csv` file, which contains the specific mappings for these meta-field
updates.

The table below lists the changes, showing the mapping from the old names to the new names used in version 0.8.3 and onwards.

### Meta-Field Name Mapping

<!-- do not correct any typos in first column; they were in the previous release and are fixed now -->

| < 0.8.3 Name                       | >= 0.8.3 Name                 |
| ---------------------------------- | ----------------------------- |
| snowagent.debug.span_events_added  | dsoa.debug.span.events.added  |
| snowagent.debug.span_events_failed | dsoa.debug.span.events.failed |
| snowagent.run.context              | dsoa.run.context              |
| snowagent.run.id                   | dsoa.run.id                   |
| snowagent.task.exec.id             | dsoa.task.exec.id             |
| snowagent.task.name                | dsoa.task.name                |
| snowagent.task.exec.status         | dsoa.task.exec.status         |
| snowagent.task.exec.id             | dsoa.task.exec.id             |
| snowagent.deployment.parameter     | dsoa.deployment.parameter     |
| snowagent.task                     | dsoa.task                     |
| snowagent.bizevent                 | dsoa.bizevent                 |

<a name="appendix-c-sec"></a>

## Appendix C: Migrating field names to version 1.0.0 or higher

Version 1.0.0 introduces a set of field renames across multiple plugins as part of a semantic alignment effort with the Dynatrace Semantic
Dictionary and OpenTelemetry naming conventions. All changes are pure renames at the DSOA telemetry emission layer; no Snowflake API columns
or underlying query logic change.

The renames span several areas:

- **Anomaly-detection event properties** (`ad.*` → Semantic Dictionary names): four properties emitted by all anomaly-detection workflows
  and the `login_history` plugin are renamed. The `login_history` plugin additionally changes its `anomaly.detector` value from
  `snowflake_security` to `dsoa.failed_login_detection`.
- **Query operator span attributes** (`snowflake.query.operator.*` → `snowflake.query.step.operator.*`): six fields gain the `step.` infix
  to reflect that operator IDs are unique within a step, not across the full query. The `.time` field is additionally renamed to
  `.time_breakdown` to signal its structured JSON value.
- **Resource monitor and warehouse scalar fields**: `snowflake.resource_monitor.threshold.pct` becomes `.threshold.value` (type changes from
  string to double with `percent` unit); `snowflake.credits.quota` becomes `.quota.value`; `snowflake.warehouse.event` becomes
  `.event.trigger`; `snowflake.warehouse.is_auto_suspend` becomes `.auto_suspend` and is reclassified as a numeric metric with unit
  `seconds`.
- **Error code field**: `error.code` is renamed to `snowflake.error.code` for namespace consistency.
- **Owner and role attributes**: `snowflake.warehouse.owner` and `snowflake.budget.owner` become `.owner.name` (the bare owner becomes an
  explicit string leaf), and `snowflake.warehouse.owner.role_type`/`snowflake.budget.owner.role_type` drop the `_type` suffix to become
  `.owner.role`.
- **Resource-monitor warehouse fields**: the attached-warehouse name list `snowflake.warehouses.names` moves into the owning namespace as
  `snowflake.resource_monitor.warehouses`, and the existing warehouse-count metric `snowflake.resource_monitor.warehouses` is renamed to
  `snowflake.resource_monitor.warehouses.count` to free that name for the list.
- **User attributes**: `snowflake.user.name` becomes `.name.login` (disambiguating it from the `.name.first`/`.name.last` siblings),
  `snowflake.user.privilege` becomes `.privilege.name`, and `snowflake.user.roles.direct` becomes `.roles.direct.list` to signal its array
  value.
- **Task configuration**: `snowflake.task.config` becomes `snowflake.task.config.id`.
- **Session and status fields**: `session.id`, `status.code`, and `status.message` are Snowflake-namespaced to `snowflake.session.id`,
  `snowflake.status.code`, and `snowflake.status.message`.

To update existing dashboards, workflows, or other Dynatrace assets that reference the old field names, run the `refactor_field_names.sh`
script included in the package with the `appx-c-query-step-operator-refactoring.csv` mapping file:

```bash
./scripts/deploy/refactor_field_names.sh appx-c-query-step-operator-refactoring.csv <exported-assets-folder>
```

For DQL queries that filter on renamed anomaly-detection fields, update them manually. Example migration:

```dql
// Before
| filter isNotNull(`ad.source`) | filter `ad.source` == "dsoa.data_volume_anomaly"
// After
| filter isNotNull(`anomaly.detector`) | filter `anomaly.detector` == "dsoa.data_volume_anomaly"
```

The table below lists all field renames.

### Field Name Mapping

| old name                                 | new name                                     |
| ---------------------------------------- | -------------------------------------------- |
| ad.source                                | anomaly.detector                             |
| ad.source_metric                         | metric.key                                   |
| ad.direction                             | anomaly.direction                            |
| ad.category                              | anomaly.subject                              |
| error.code                               | snowflake.error.code                         |
| snowflake.credits.quota                  | snowflake.credits.quota.value                |
| snowflake.query.operator.attributes      | snowflake.query.step.operator.attributes     |
| snowflake.query.operator.id              | snowflake.query.step.operator.id             |
| snowflake.query.operator.parent_ids      | snowflake.query.step.operator.parent_ids     |
| snowflake.query.operator.stats           | snowflake.query.step.operator.stats          |
| snowflake.query.operator.time            | snowflake.query.step.operator.time_breakdown |
| snowflake.query.operator.type            | snowflake.query.step.operator.type           |
| snowflake.query.step.operator.time       | snowflake.query.step.operator.time_breakdown |
| snowflake.resource_monitor.threshold.pct | snowflake.resource_monitor.threshold.value   |
| snowflake.warehouse.event                | snowflake.warehouse.event.trigger            |
| snowflake.warehouse.is_auto_suspend      | snowflake.warehouse.auto_suspend             |
| snowflake.budget.owner.role_type         | snowflake.budget.owner.role                  |
| snowflake.budget.owner                   | snowflake.budget.owner.name                  |
| snowflake.warehouse.owner.role_type      | snowflake.warehouse.owner.role               |
| snowflake.warehouse.owner                | snowflake.warehouse.owner.name               |
| snowflake.resource_monitor.warehouses    | snowflake.resource_monitor.warehouses.count  |
| snowflake.warehouses.names               | snowflake.resource_monitor.warehouses        |
| snowflake.task.config                    | snowflake.task.config.id                     |
| snowflake.user.name                      | snowflake.user.name.login                    |
| snowflake.user.privilege                 | snowflake.user.privilege.name                |
| snowflake.user.roles.direct              | snowflake.user.roles.direct.list             |
| session.id                               | snowflake.session.id                         |
| status.code                              | snowflake.status.code                        |
| status.message                           | snowflake.status.message                     |

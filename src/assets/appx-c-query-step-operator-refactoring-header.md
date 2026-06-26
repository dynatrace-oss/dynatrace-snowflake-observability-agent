<a name="appendix-c-sec"></a>

## Appendix C: Migrating field names to version 1.0.0 or higher

Version 1.0.0 introduces a set of field renames across multiple plugins as part of a semantic alignment effort with the
Dynatrace Semantic Dictionary and OpenTelemetry naming conventions. All changes are pure renames at the DSOA telemetry
emission layer; no Snowflake API columns or underlying query logic change.

The renames span several areas:

- **Anomaly-detection event properties** (`ad.*` → Semantic Dictionary names): four properties emitted by all anomaly-detection
  workflows and the `login_history` plugin are renamed. The `login_history` plugin additionally changes its `anomaly.detector`
  value from `snowflake_security` to `dsoa.failed_login_detection`.
- **Query operator span attributes** (`snowflake.query.operator.*` → `snowflake.query.step.operator.*`): six fields gain the
  `step.` infix to reflect that operator IDs are unique within a step, not across the full query. The `.time` field is
  additionally renamed to `.time_breakdown` to signal its structured JSON value.
- **Resource monitor and warehouse scalar fields**: `snowflake.resource_monitor.threshold.pct` becomes `.threshold.value`
  (type changes from string to double with `percent` unit); `snowflake.credits.quota` becomes `.quota.value`;
  `snowflake.warehouse.event` becomes `.event.trigger`; `snowflake.warehouse.is_auto_suspend` becomes `.auto_suspend`
  and is reclassified as a numeric metric with unit `seconds`.
- **Error code field**: `error.code` is renamed to `snowflake.error.code` for namespace consistency.
- **Owner and role attributes**: `snowflake.warehouse.owner` and `snowflake.budget.owner` become `.owner.name` (the bare
  owner becomes an explicit string leaf), and `snowflake.warehouse.owner.role_type`/`snowflake.budget.owner.role_type` drop
  the `_type` suffix to become `.owner.role`.
- **Resource-monitor warehouse fields**: the attached-warehouse name list `snowflake.warehouses.names` moves into the owning
  namespace as `snowflake.resource_monitor.warehouses`, and the existing warehouse-count metric
  `snowflake.resource_monitor.warehouses` is renamed to `snowflake.resource_monitor.warehouses.count` to free that name for
  the list.
- **User attributes**: `snowflake.user.name` becomes `.name.login` (disambiguating it from the `.name.first`/`.name.last`
  siblings), `snowflake.user.privilege` becomes `.privilege.name`, and `snowflake.user.roles.direct` becomes
  `.roles.direct.list` to signal its array value.
- **Task configuration**: `snowflake.task.config` becomes `snowflake.task.config.id`.
- **Session and status fields**: `session.id`, `status.code`, and `status.message` are Snowflake-namespaced to
  `snowflake.session.id`, `snowflake.status.code`, and `snowflake.status.message`.

To update existing dashboards, workflows, or other Dynatrace assets that reference the old field names, run the
`refactor_field_names.sh` script included in the package with the `appx-c-query-step-operator-refactoring.csv` mapping file:

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

| old name | new name |
|----------|----------|

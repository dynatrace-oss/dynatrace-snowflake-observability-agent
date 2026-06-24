<a name="appendix-c-sec"></a>

## Appendix C: Migrating query operator field names to version 1.0.0 or higher

Version 1.0.0 renames six `snowflake.query.operator.*` span event attribute fields to
`snowflake.query.step.operator.*`, scoping them as lexical children of the `snowflake.query.step.id`
concept. No Snowflake API columns change; this is a pure rename at the DSOA telemetry emission layer.
The `operator_id` values were already unique only within a step (encoded as
`operator_number = 10000 * step_id + operator_id`), so the new namespace reflects the true scope.

To update existing dashboards, workflows, or other Dynatrace assets that reference the old field
names, run the `refactor_field_names.sh` script included in the package with the
`appx-c-query-step-operator-refactoring.csv` mapping file:

```bash
./scripts/deploy/refactor_field_names.sh appx-c-query-step-operator-refactoring.csv <exported-assets-folder>
```

The table below lists all six field renames.

### Field Name Mapping

| old name | new name |
|----------|----------|

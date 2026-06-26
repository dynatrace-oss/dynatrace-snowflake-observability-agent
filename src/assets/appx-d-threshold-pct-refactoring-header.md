<a name="appendix-d-sec"></a>

## Appendix D: Migrating resource monitor threshold field to version 1.0.0 or higher

Version 1.0.0 renames the `snowflake.resource_monitor.threshold.pct` field to
`snowflake.resource_monitor.threshold.value` and changes its type from string to double with a
`percent` unit. This makes the field consistent with the Dynatrace Semantic Dictionary convention
that separates the threshold configuration value from the live consumption percentage
(`snowflake.credits.quota.used_pct`).

To update existing dashboards, workflows, or other Dynatrace assets that reference the old field
name, run the `refactor_field_names.sh` script included in the package with the
`appx-d-threshold-pct-refactoring.csv` mapping file:

```bash
./scripts/deploy/refactor_field_names.sh appx-d-threshold-pct-refactoring.csv <exported-assets-folder>
```

The table below lists the field rename.

### Field Name Mapping

| old name | new name |
|----------|----------|

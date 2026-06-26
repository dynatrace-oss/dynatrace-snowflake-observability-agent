<a name="appendix-f-sec"></a>

## Appendix F: Migrating warehouse auto-suspend field to version 1.0.0 or higher

Version 1.0.0 renames `snowflake.warehouse.is_auto_suspend` to
`snowflake.warehouse.auto_suspend` and reclassifies it from an attribute to a metric with
unit `seconds`. The field now carries the actual auto-suspend timeout in seconds (e.g.,
`600`) rather than a boolean-style value, aligning with the Snowflake `SHOW WAREHOUSES`
`AUTO_SUSPEND` column semantics. A value of `null` or `0` indicates auto-suspend is disabled.

To update existing dashboards, workflows, or other Dynatrace assets that reference the old
field name, run the `refactor_field_names.sh` script included in the package with the
`appx-f-auto-suspend-refactoring.csv` mapping file:

```bash
./scripts/deploy/refactor_field_names.sh appx-f-auto-suspend-refactoring.csv <exported-assets-folder>
```

The table below lists the field rename.

### Field Name Mapping

| old name | new name |
|----------|----------|

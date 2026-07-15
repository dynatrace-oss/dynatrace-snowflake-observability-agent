<a name="appendix-b-sec"></a>

## Appendix B: Migrating meta-field semantics to version 0.8.3 or higher

Version 0.8.3 aligns the naming of several meta-fields with the product's final, official name: **Dynatrace Snowflake Observability Agent** (formerly SnowAgent). If you are upgrading from a version prior to 0.8.3, you will need to update any custom dashboards, workflows, or other assets that rely on these fields.

The refactoring process is similar to the one described in [Appendix A](README.md#appendix-a-sec) and uses the same `refactor_field_names.sh` script.
However, for this migration, you must use the `dsoa-fields-refactoring.csv` file, which contains the specific mappings for these meta-field updates.

The table below lists the changes, showing the mapping from the old names to the new names used in version 0.8.3 and onwards.

### Meta-Field Name Mapping

<!-- do not correct any typos in first column; they were in the previous release and are fixed now -->

| < 0.8.3 Name | >= 0.8.3 Name |
|--------------|---------------|

<a name="appendix-a-sec"></a>

## Appendix A: Migrating semantics from version 0.7 to 0.8

In version 0.8, the semantics of the telemetry sent by Dynatrace Snowflake Observability Agent underwent significant refactoring to improve compatibility with industry standards such as OpenTelemetry and the naming conventions in the Dynatrace Semantic Dictionary.
This ensures better interoperability and adherence to widely accepted practices.

To update to the new version, users need to run the `refactor_field_names.sh` script, which is included in the package.
This script requires two parameters:

1. **fields-refactoring.csv**: This file, provided in the package, contains the mapping of old field names to new field names.
2. **Exported Data Folder**: The location of the folder containing all exported dashboards, workflows, and other relevant data.

By running the script with these parameters, it will automatically update all semantics to be compatible with version 0.8.
This process ensures that all field names are correctly updated according to the new naming conventions.

Below is a table that lists all the changes made to the field names.
This table provides a clear mapping between the old names (version 0.7) and the new names (version 0.8):

### Field Name Mapping

<!-- do not correct any typos in first column; they were in the previous release and are fixed now -->

| 0.7 Name | 0.8 Name |
|----------|----------|

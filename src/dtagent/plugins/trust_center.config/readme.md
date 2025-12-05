Delivers new findings reported (within the last 24 hours) by Snowflake Trust Center as log entries.
For findings with `CRITICAL` severity, `CUSTOM_ALERT` event is sent to Dynatrace.

This plugin provides information on:

- scanner name, description, and packages details,
- number of entities at risk as a metric, plus
- details on those entities as `snowflake.entity.details` log attribute.

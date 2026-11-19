Delivers new findings reported (within the last 24 hours) by Snowflake Trust Center as log entries.
Findings with `CRITICAL` severity are no longer sent as `CUSTOM_ALERT` events; alerting is provided by the Data Observability app.

This plugin provides information on:

- scanner name, description, and packages details,
- number of entities at risk as a metric, plus
- details on those entities as `snowflake.entity.details` log attribute.

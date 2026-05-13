> **Deprecated:** This plugin is deprecated as of 0.9.5 and will be removed in 0.9.6.
> Use the [metering](../metering.config/readme.md) plugin instead, which covers all Snowflake service types
> via `METERING_HISTORY`. To reproduce the same data, filter by `service_type == "TELEMETRY_DATA_INGEST"`.

This plugin delivers information regarding the history of data loaded into Snowflake event tables. It reports telemetry from the `EVENT_USAGE_HISTORY` view.

Log entries include:

- timestamps: start and end time of the event,
- bytes ingested during the event (also reported as `snowflake.data.ingested` metric),
- credits consumed during the event (also reported as `snowflake.credits.used` metric).

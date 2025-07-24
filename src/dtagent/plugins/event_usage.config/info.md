This plugin delivers information regarding the history of data loaded into Snowflake event tables. It reports telemetry from the `EVENT_USAGE_HISTORY` view.

Log entries include include:

* timestamps: start and end time of the event,
* bytes ingested during the event (also reported as `snowflake.data.ingested` metric),
* credits consumed during the event (also reported as `snowflake.credits.used` metric).

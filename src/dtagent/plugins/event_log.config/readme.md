This plugin delivers to Dynatrace data reported by Snowflake Trail in the `EVENT TABLE`.

By default, it runs every 30 minutes and registers entries from the last 12 hours, omitting the ones, which:

- where already delivered,
- with scope set to `DTAGENT_OTLP` as they are internal log recording entries sent over the OpenTelemetry protocol
- related to execution of other instances of Dynatrace Snowflake Observability Agent, or
- with importance below the level set as `CORE.LOG_LEVEL`, i.e., only warnings or errors from the given Dynatrace Snowflake Observability Agent instance are reported.

By default, it produces log entries containing the following information:

- timestamp of the entry to Snowflake Trail,
- timestamp the plugin observed the entry,
- content,
- type of record, and
- trace of the entry.

Metric entries (`RECORD_TYPE = 'METRIC'`) are sent via Dynatrace Metrics API v2.
Metrics that were identified during development time will have their semantics included already in the Dynatrace Snowflake Observability Agent semantic dictionary; semantics for any new metric will be copied from information provided by Snowflake Trail.

Span entries (`RECORD_TYPE = 'SPAN'`) are send via OpenTelemetry Trace API, with trace ID and span ID set as reported by Snowflake Trail.

Unless [OpenTelemetry-compliant attribute names](https://opentelemetry.io/docs/specs/semconv/attributes-registry/), such as `code.function`, are reported in the event log table, Snowflake prefixes all internal telemetry names with `snow.`. Dynatrace Snowflake Observability Agent passes all telemetry under the original names provided by Snowflake in the event log table. The only exception is the `SCOPE` column, where attribute names are short (like `name`) and Dynatrace Snowflake Observability Agent reports them with `snowflake.event.scope.` prefix, e.g., `snowflake.event.scope.name`.

# Dynatrace Snowflake Observability Agent

<img src="docs/assets/dsoa_logo.svg" alt="Dynatrace Snowflake Observability Agent logo" width="200" class="dsoa-logo">

**Dynatrace Snowflake Observability Agent** is a powerful tool designed to enhance [Data Platform Observability](DPO.md) within the
Snowflake environment. It complements Dynatrace's capabilities by [extending observability](PLUGINS.md) into areas where traditional
OneAgent or synthetic monitoring may not reach. Dynatrace Snowflake Observability Agent provides [comprehensive telemetry](SEMANTICS.md) for
monitoring, analyzing, and detecting anomalies in data processing. It delivers observability data in the form of OpenTelemetry
[logs](ARCHITECTURE.md#sending-logs) and [spans](ARCHITECTURE.md#sending-tracesspans), as well as Dynatrace
[metrics](ARCHITECTURE.md#sending-metrics), [events](ARCHITECTURE.md#sending-events), and
[business events (CloudEvents)](ARCHITECTURE.md#sending-bizevents), ensuring a seamless integration with Dynatrace's observability platform.

Table of content:

- [Data Platform Observability](docs/DPO.md)
- [Use cases](docs/USECASES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Plugins](docs/PLUGINS.md)
- [Semantic dictionary](docs/SEMANTICS.md)
- [How to install](docs/INSTALL.md)
- [Example dashboards](docs/dashboards)
- [Changelog](docs/CHANGELOG.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Implementing new plugins](docs/PLUGIN_DEVELOPMENT.md)

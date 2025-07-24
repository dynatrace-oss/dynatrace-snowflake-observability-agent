# Dynatrace Snowflake Observability Agent

![Dynatrace Snowflake Observability Agent log|100x100](src/assets/dsoa_logo.svg){width=200px}

**Dynatrace Snowflake Observability Agent** is a powerful tool designed to enhance [Data Platform Observability](DPO.md) within the Snowflake environment. It complements Dynatrace's capabilities by [extending observability](README.md#plugins) into areas where traditional OneAgent or synthetic monitoring may not reach. Dynatrace Snowflake Observability Agent provides comprehensive telemetry for monitoring, analyzing, and detecting anomalies in data processing. It delivers observability data in the form of OpenTelemetry [logs](ARCHITECTURE.md#sending-logs) and [spans](ARCHITECTURE.md#sending-tracesspans), as well as Dynatrace [metrics](ARCHITECTURE.md#sending-metrics), [events](ARCHITECTURE.md#sending-events), and [business events (CloudEvents)](ARCHITECTURE.md#sending-bizevents), ensuring a seamless integration with Dynatrace's observability platform.

Table of content:

* [Data Platform Observability](DPO.md)
* [Use cases](USECASES.md)
* [Architecture](ARCHITECTURE.md)
* [Plugins](README.md#plugins)
* [Semantic dictionary](README.md#semantic-dictionary)
* [How to install](INSTALL.md)
* [Changelog](CHANGELOG.md)
* [Contributing](CONTRIBUTING.md)

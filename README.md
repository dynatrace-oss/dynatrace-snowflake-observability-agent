# Dynatrace Snowflake Observability Agent

<div class="header" style="margin-top: 2em; margin-bottom: 2em;">
<img src="docs/assets/dynatrace-logo.svg" alt="Dynatrace logo" height="100" class="dynatrace-logo">
<img src="docs/assets/left-arrow.svg" alt="arrow" height="100" class="left-arrow">
<img src="docs/assets/snowflake-logo.svg" alt="Snowflake logo" height="100" class="snowflake-logo">
</div>

**Dynatrace Snowflake Observability Agent (DSOA)** is a powerful tool designed to enhance [Data Platform Observability](DPO.md) within the
Snowflake environment. It complements Dynatrace's capabilities by [extending observability with plugins](PLUGINS.md) into areas where
traditional OneAgent or synthetic monitoring may not reach. DSOA provides [comprehensive telemetry data](SEMANTICS.md) for monitoring,
analyzing, and detecting anomalies in data processing. It delivers observability data in the form of OpenTelemetry
[logs](ARCHITECTURE.md#sending-logs) and [spans](ARCHITECTURE.md#sending-tracesspans), as well as Dynatrace
[metrics](ARCHITECTURE.md#sending-metrics), [events](ARCHITECTURE.md#sending-events), and
[business events (CloudEvents)](ARCHITECTURE.md#sending-bizevents), ensuring a seamless integration with Dynatrace's observability platform.

**Table of contents:**

- [Understanding Data Platform Observability](docs/DPO.md)
- [Common use cases](docs/USECASES.md)
- [Architecture and core capabilities](docs/ARCHITECTURE.md)
- [Available plugins](docs/PLUGINS.md)
- [Telemetry semantic dictionary](docs/SEMANTICS.md)
- [Installation guide](docs/INSTALL.md)
- [Example dashboards](docs/dashboards)
- [Version changelog](docs/CHANGELOG.md)
- [Contribution guidelines](docs/CONTRIBUTING.md)
- [Plugin development guide](docs/PLUGIN_DEVELOPMENT.md)
- [Appendix and reference](docs/APPENDIX.md)

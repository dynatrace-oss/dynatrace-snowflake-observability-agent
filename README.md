# Dynatrace Snowflake Observability Agent

<div class="header" style="margin-top: 2em; margin-bottom: 2em;">
<img src="docs/assets/dynatrace-logo.svg" alt="Dynatrace logo" height="100" class="dynatrace-logo">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="100" height="100" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
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

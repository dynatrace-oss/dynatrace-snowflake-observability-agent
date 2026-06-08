# New Plugin: Metering

- **Problem**: `event_usage` plugin reads only `EVENT_USAGE_HISTORY`, covering a single service type (`TELEMETRY_DATA_INGEST`). `METERING_HISTORY` covers all service types, enabling full FinOps visibility.
- **Solution**: New `metering` plugin reading `SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY` with `WHERE SERVICE_TYPE != 'WAREHOUSE_METERING'` to avoid duplication with `warehouse_usage`.
- **Metrics**: `snowflake.credits.used`, `snowflake.credits.used.compute`, `snowflake.credits.used.cloud_services`, `snowflake.data.size`, `snowflake.data.rows`, `snowflake.data.files` — all with `snowflake.service.type` and `snowflake.service.name` dimensions.
- **Migration**: `event_usage` disabled by default, logs deprecation warning. `snowflake.credits.used` metric name preserved for backward compatibility. Filter `snowflake.service.type == "TELEMETRY_DATA_INGEST"` reproduces old data.
- **Files**: `src/dtagent/plugins/metering.py`, `metering.sql/` (view, task, config proc), `metering.config/` (config, instruments-def, bom, readme), test fixtures and test file.
- **Removal plan**: `event_usage` will be fully removed in 0.9.6.

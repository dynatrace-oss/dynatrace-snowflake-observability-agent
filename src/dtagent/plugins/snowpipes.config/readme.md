This plugin enables monitoring of Snowflake Snowpipes, tracking real-time pipe status, ingestion latency, throughput, costs, and load errors.

The plugin uses a **dual-schedule architecture**:

- **Fast mode** (every 5 minutes, no warehouse): `SHOW PIPES` + `SYSTEM$PIPE_STATUS()` for real-time status, backlog, and latency.
- **Deep mode** (hourly, warehouse required): `ACCOUNT_USAGE.COPY_HISTORY` and `PIPE_USAGE_HISTORY` for volume, cost, errors, throughput, and per-file latency.

The `MONITOR` privilege on pipes is required for `SYSTEM$PIPE_STATUS()`. When the `admin` scope is installed, this is handled automatically by `P_GRANT_MONITOR_SNOWPIPES()`.

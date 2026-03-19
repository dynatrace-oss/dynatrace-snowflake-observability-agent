# Dashboard: Snowpipes Monitoring

This dashboard provides comprehensive monitoring of Snowflake Snowpipe continuous data ingestion pipelines. It tracks pipeline health, ingestion latency, stage backlog, error rates, data volumes, and credit consumption, enabling operators to quickly detect and diagnose issues with their automated data loading workflows.

## Executive Overview

Six KPI tiles give an immediate, at-a-glance view of your Snowpipes estate:

- **Pipe Health** — percentage of pipes currently in `RUNNING` state. Color-coded green (100%), orange (80–99%), or red (below 80%).
- **Credits Consumed** — total Snowpipe credits used in the selected timeframe.
- **Files Processed** — total number of files successfully ingested across all pipes.
- **p95 Ingestion Latency** — 95th-percentile end-to-end ingestion latency. Color-coded against the configurable warning (default 5 min) and critical (default 30 min) thresholds.
- **Load Errors** — total count of load errors. Turns red immediately if any errors are detected.
- **Data Ingested** — total bytes ingested, displayed with automatic unit scaling.

## Pipe Health Status

The **Pipe Status** honeycomb shows every pipe in your estate as a colored tile:

- **Green** — pipe is `RUNNING` and actively ingesting data.
- **Orange** — pipe is `PAUSED`.
- **Red** — pipe is in a `STOPPED` or `STALLED` state and requires attention.

Hovering over a tile reveals the pipe name, account, and exact status string.

## Latency & Throughput

Three charts track the throughput and latency profile of your ingestion pipelines:

- **Ingestion Latency by Pipe** — time-series line chart of average end-to-end ingestion latency per pipe, with configurable warning and critical threshold bands.
- **Stage Backlog (Pending Files)** — bar chart showing the number of files queued but not yet ingested per pipe. Use the `$Threshold_Backlog_Warning` and `$Threshold_Backlog_Critical` variables to define acceptable backlog sizes.
- **Data Volume Ingested** — bar chart of ingested data volume grouped by database, showing which databases are receiving the most data.

## Error Analytics

Two tiles focus on load errors:

- **Errors by Target Table** — honeycomb colored by total error count per target table. Red cells indicate tables experiencing load failures.
- **Top Pipes by Error Count** — sortable table listing the top 50 pipes by error count, along with their database and target table. Rows with errors are highlighted red.

## Cost & Credits

- **Credits Consumed over Time** — line chart showing Snowpipe credit usage over time, broken down by individual pipe. Useful for identifying which pipes are driving the most cost.

## Dashboard Variables

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `Accounts` | query | all | Filter by Snowflake account (`deployment.environment`) |
| `Pipe` | query | all | Filter by pipe name (`snowflake.pipe.name`) |
| `Threshold_Latency_Warning` | text | `300000` ms | Latency warning threshold (5 min) |
| `Threshold_Latency_Critical` | text | `1800000` ms | Latency critical threshold (30 min) |
| `Threshold_Backlog_Warning` | text | `100` files | Stage backlog warning threshold |
| `Threshold_Backlog_Critical` | text | `1000` files | Stage backlog critical threshold |

The `$Accounts` and `$Pipe` variables support multi-select, allowing you to narrow the dashboard to a specific account or set of pipes (e.g., only pipes loading CSV files from S3 into a particular schema).

## Required Plugin

This dashboard requires the `snowpipes` plugin to be enabled in your DSOA configuration. The plugin uses a dual-schedule architecture:

- **Fast context** (`snowpipes`, every 5 min) — pipe status, pending file count, and oldest-file latency.
- **Deep context** (`snowpipes_copy_history`, hourly) — ingestion latency, file/row counts, and error details from `ACCOUNT_USAGE.COPY_HISTORY`.
- **Usage context** (`snowpipes_usage_history`, hourly) — data volume and credit consumption from `ACCOUNT_USAGE.PIPE_USAGE_HISTORY`.

Note that hourly context metrics (latency, data volume, credits) will not appear until the first hourly collection completes after the plugin is enabled.

## Default Timeframe

The dashboard defaults to the last 24 hours. For cost and credit analysis, extend the timeframe to 7 or 14 days to see meaningful trends.

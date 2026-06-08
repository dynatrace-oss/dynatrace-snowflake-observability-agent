# Pipes, Streams, Stage, and Data Lineage Monitoring Plugins

## Pipes Monitoring Plugin

- Implemented `PipesPlugin` to monitor Snowpipe status and validation
- Uses `SYSTEM$PIPE_STATUS` function for real-time pipe monitoring
- Uses `VALIDATE_PIPE_LOAD` function for validation checks
- Delivers telemetry as logs, metrics, and events

## Streams Monitoring Plugin

- Implemented `StreamsPlugin` to monitor Snowflake Streams
- Tracks stream staleness using `SHOW STREAMS` output
- Monitors pending changes and stream health
- Reports stale streams as warning events

## Stage Monitoring Plugin

- Implemented `StagePlugin` to monitor staged data
- Tracks internal and external stages
- Monitors COPY INTO activities from `QUERY_HISTORY` and `COPY_HISTORY` views
- Reports on staged file sizes, counts, and load patterns

## Data Lineage Plugin

- Implemented `DataLineagePlugin` combining static and dynamic lineage
- Static lineage from `OBJECT_DEPENDENCIES` view (DDL-based relationships)
- Dynamic lineage from `ACCESS_HISTORY` view (runtime data flow)
- Column-level lineage tracking with direct and indirect dependencies
- Lineage graphs delivered as structured events

# Workflow: Warehouse Sensitive Change Alert (Experimental)

Raises a Dynatrace event whenever a Snowflake warehouse or resource monitor is altered with
a property change in the sensitive allowlist (size, scaling policy, auto-suspend,
resource-monitor reassignment, cluster-count bounds). Built on the experimental DDL
attribution feature in the `query_history` plugin.

## Overview

| Property        | Value                                                                                  |
|-----------------|----------------------------------------------------------------------------------------|
| DPO Theme       | Security                                                                               |
| Required Plugin | `query_history` with `plugins.query_history.track_ddl_changes=true` (experimental)     |
| Trigger         | Every 60 minutes (interval)                                                            |
| Alert condition | Any DDL on `Warehouse` or `Resource Monitor` touching a sensitive property             |
| Event source    | `dsoa.warehouse_sensitive_change`                                                      |
| Expected lag    | Up to ~3 hours after the actual change (driven by ACCESS_HISTORY catchup in Snowflake) |

## How It Works

1. **`detect_sensitive_changes`** — DQL query against `events` looking back 90 minutes for
   any record where `snowflake.object.ddl.operation` is non-null, `snowflake.object.type`
   is `Warehouse` or `Resource Monitor`, and `snowflake.object.ddl.properties` contains at
   least one sensitive property name. The 90-minute window is intentionally larger than the
   60-minute interval to provide overlap and tolerate ingestion delays.

1. **`build_events`** — Constructs one Dynatrace event per detected change with the user,
   role, object name, operation, and full property delta as event properties.

1. **`ingest_events`** — Pushes events via the Environment v2 events API. The event type
   is `CustomInfo` by default; switch to `CustomAlert` to enable Davis problem correlation.

## Telemetry Source

Reads the following attributes from `query_history` events (all five are emitted only when
`plugins.query_history.track_ddl_changes=true`):

| Attribute                          | Role                                                  |
|------------------------------------|-------------------------------------------------------|
| `snowflake.object.type`            | Filtered to `Warehouse` / `Resource Monitor`          |
| `snowflake.object.name`            | Identifies the affected warehouse / resource monitor  |
| `snowflake.object.ddl.operation`   | `CREATE` / `ALTER` / `DROP` / etc.                    |
| `snowflake.object.ddl.properties`  | JSON delta; scanned for sensitive-property keys       |
| `db.user`, `snowflake.role.name`   | Actor attribution                                     |

The two standard query_history dimensions `deployment.environment` and `db.system` scope the
query to Snowflake telemetry from a specific DSOA deployment.

## Sensitive property allowlist

The workflow scans the JSON-stringified property delta for any of these keys:

- `WAREHOUSE_SIZE`
- `SCALING_POLICY`
- `RESOURCE_MONITOR`
- `AUTO_SUSPEND`
- `MIN_CLUSTER_COUNT`
- `MAX_CLUSTER_COUNT`

To extend, edit the `contains(...)` clauses in `detect_sensitive_changes`. Cosmetic-only
property changes (such as `COMMENT`) deliberately do not fire.

## Caveats

- **Experimental.** Tied to the `track_ddl_changes` flag in the `query_history` plugin;
  may be refactored when that feature graduates.
- **Lag.** `ACCESS_HISTORY.OBJECT_MODIFIED_BY_DDL` is populated up to ~3 hours after the
  DDL statement, so this workflow will not fire in real time. For sub-hour alerting on
  the legacy unstructured signal use a separate workflow on `db.operation.name`.
- **`ALTER WAREHOUSE … SUSPEND` / `RESUME`** are session operations in Snowflake and are
  not expected to appear in `OBJECT_MODIFIED_BY_DDL` — they will not trigger this workflow.
  If you need them, alert on `db.operation.name` directly.

## Configuration

Edit the JavaScript `CONFIG` block in `build_events` to:

- switch the event type (`CustomInfo` → `CustomAlert`)
- change the event timeout (default 60 min)
- change the `ad.source` tag used by Dynatrace for grouping

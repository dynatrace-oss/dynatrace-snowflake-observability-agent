# Workflow: Warehouse Sensitive Change Alert

Raises a Dynatrace event whenever a Snowflake warehouse is altered with a property change
in the sensitive allowlist (size, scaling policy, auto-suspend, cluster-count bounds).

## Overview

| Property        | Value                                                                           |
|-----------------|---------------------------------------------------------------------------------|
| DPO Theme       | Security                                                                        |
| Required Plugin | `query_history`                                                                 |
| Trigger         | Every 60 minutes (interval)                                                     |
| Alert condition | Any warehouse DDL with a sensitive keyword in the query text                    |
| Event source    | `dsoa.warehouse_sensitive_change`                                               |
| Expected lag    | Near-real-time (driven by query_history plugin run interval, typically ≤10 min) |

## How It Works

1. **`detect_sensitive_changes`** — DQL query against `logs` looking back 90 minutes for
   any log where `db.operation.name` is a warehouse DDL type (`ALTER`, `CREATE`, `DROP`,
   `RENAME_WAREHOUSE`) and `db.query.text` contains at least one sensitive property keyword.
   The 90-minute window is intentionally larger than the 60-minute interval to provide
   overlap and tolerate ingestion delays.

1. **`build_events`** — Constructs one Dynatrace event per detected change with the user,
   role, operation name, and raw query text as event properties.

1. **`ingest_events`** — Pushes events via the Environment v2 events API. The event type
   is `CustomInfo` by default; switch to `CustomAlert` to enable Davis problem correlation.

## Telemetry Source

Reads the following attributes from `query_history` logs:

| Attribute                | Role                                                     |
|--------------------------|----------------------------------------------------------|
| `db.operation.name`      | Filtered to warehouse DDL types                          |
| `db.query.text`          | Raw SQL; scanned for sensitive-property keywords         |
| `db.user`                | Actor (user who ran the DDL)                             |
| `snowflake.role.name`    | Role used                                                |
| `deployment.environment` | Scopes query to a specific DSOA deployment               |

Empirically confirmed `db.operation.name` values for warehouse DDL: `ALTER`, `CREATE`,
`DROP`, `RENAME_WAREHOUSE`.

## Sensitive property allowlist

The workflow scans `db.query.text` for any of these keywords:

- `WAREHOUSE_SIZE`
- `SCALING_POLICY`
- `AUTO_SUSPEND`
- `MIN_CLUSTER_COUNT`
- `MAX_CLUSTER_COUNT`

To extend, edit the `contains(...)` clauses in `detect_sensitive_changes`. Cosmetic-only
property changes (such as `COMMENT`) deliberately do not fire.

## Caveats

- **`db.query.text` obfuscation.** If `plugins.query_history.obfuscation_mode` is not `off`,
  query text may be obfuscated and the keyword scan will not match. Ensure obfuscation is
  disabled or set to a mode that preserves DDL keywords for this workflow to function.
- **`ALTER WAREHOUSE … SUSPEND` / `RESUME`** are session operations and do not carry
  sensitive property keywords — they will not trigger this workflow. This is intentional.

## Configuration

Edit the JavaScript `CONFIG` block in `build_events` to:

- switch the event type (`CustomInfo` → `CustomAlert`)
- change the event timeout (default 60 min)
- change the `ad.source` tag used by Dynatrace for grouping

# Workflow: Broken Share Detection

Monitors inbound Snowflake shares for three silent failure modes: shares that have become
UNAVAILABLE, shares that have silently disappeared (no report in the last 2 hours despite
activity in the last 7 days), and shares whose table row counts have dropped abnormally
below the learned seasonal baseline. All detection paths emit Dynatrace events for alerting.
Complements the [Shares & Governance Dashboard](../dashboards/shares-governance/readme.md).

## Overview

| Property          | Value                                                    |
|-------------------|----------------------------------------------------------|
| DPO Theme         | Quality / Security                                       |
| Required Plugin   | `shares`                                                 |
| Trigger           | Every 6 hours (interval)                                 |
| Detection paths   | DQL (status), DQL (disappeared), Davis AI (volume)       |
| Analyzer          | `SeasonalBaselineAnomalyDetectionAnalyzer`               |
| Alert condition   | BELOW baseline + missing data                            |
| Training window   | 30 days                                                  |
| Event source      | `dsoa.shares_broken_detection`                           |

## How It Works

1. **`detect_broken_shares`** — Queries `inbound_shares` logs for entries where
   `snowflake.share.status == "UNAVAILABLE"`. Summarizes by share name, database, and
   environment. Each unique broken share becomes one event.

1. **`detect_disappeared_shares`** — Scans `inbound_shares` logs over the last 7 days.
   Finds shares whose most recent log entry is older than 2 hours — indicating the share
   may have been revoked, dropped, or stopped refreshing without explicit status change.

1. **`detect_volume_anomaly`** — Uses Davis AI (`SeasonalBaselineAnomalyDetectionAnalyzer`)
   on `snowflake.data.rows` per share table at daily intervals. Detects unexpected drops in
   row counts compared to the learned seasonal baseline. Also alerts when a table stops
   reporting entirely (`alertOnMissingData: true`). Note: `snowflake.data.rows` is a string
   attribute on inbound share logs — the query uses `makeTimeseries` with `toLong()`.

1. **`extract_share_events`** — Collects results from all three detection tasks and builds
   Dynatrace event payloads. DQL results are mapped directly; Davis AI results use the
   standard `raisedAlerts` pattern.

1. **`ingest_share_events`** — Sends each event to Dynatrace via the Environment V2 Events API.

## Telemetry Source

All detection queries target the `inbound_shares` context from the `shares` plugin:

| Field                       | Role                                                    |
|-----------------------------|---------------------------------------------------------|
| `telemetry.exporter.module` | Filter: `inbound_shares`                                |
| `snowflake.share.status`    | Broken detection: filter for `UNAVAILABLE`              |
| `snowflake.error.message`   | Broken detection: error context                         |
| `snowflake.share.name`      | Dimension (per-share series and event property)         |
| `snowflake.data.rows`       | Volume detection: STRING — converted with `toLong()`    |
| `db.namespace`              | Dimension (shared database name)                        |
| `db.collection.name`        | Volume detection: per-table series                      |
| `deployment.environment`    | Dimension (Snowflake account / environment)             |

## Event Properties

Each ingested event carries a base set of properties. Additional properties depend on the
detection path (`ad.category`):

| Property                 | unavailable                    | disappeared                    | volume_drop                    |
|--------------------------|--------------------------------|--------------------------------|--------------------------------|
| `event.type`             | `CustomInfo`                   | `CustomInfo`                   | `CustomInfo`                   |
| `ad.source`              | `dsoa.shares_broken_detection` | `dsoa.shares_broken_detection` | `dsoa.shares_broken_detection` |
| `ad.category`            | `unavailable`                  | `disappeared`                  | `volume_drop`                  |
| `snowflake.share.name`   | share name                     | share name                     | share name                     |
| `deployment.environment` | account                        | account                        | account                        |
| `db.namespace`           | database name                  | —                              | —                              |
| `db.collection.name`     | —                              | —                              | table name                     |
| `ad.source_metric`       | —                              | —                              | `snowflake.data.rows`          |
| `event.start` / `end`    | —                              | —                              | anomaly timeframe              |

## Customization

At the top of the `extract_share_events` task there is a `CONFIG` block:

```js
const CONFIG = {
  eventType: EventIngestEventType.CustomInfo,   // change to CustomAlert for Davis problems
  eventTimeout: 360,
  adSource: 'dsoa.shares_broken_detection'
};
```

- **`eventType`**: Switch to `EventIngestEventType.CustomAlert` to enable Davis problem
  correlation and receive problem notifications.
- **`eventTimeout`**: Event lifetime in minutes before auto-close.

**Scope to specific shares** — In the `detect_volume_anomaly` task, uncomment the filter line:

```dql
// | filter snowflake.share.name == "MY_SHARE"
```

**Adjust the disappeared threshold** — The default 2-hour gap threshold accounts for the
default 30-minute shares plugin schedule plus processing delays. Increase it (e.g., `now()-6h`)
for less frequent plugin schedules or noisier environments. Edit the filter line in
`detect_disappeared_shares`:

```dql
| filter last_seen < now()-2h
```

**Adjust trigger frequency** — The default 6-hour trigger is appropriate since shares change
infrequently. For high-compliance environments, `intervalMinutes: 60` gives hourly detection.
For low-churn accounts, `720` (12h) or `1440` (24h) reduces noise.

## Prerequisites

- `shares` plugin enabled with the `inbound_shares` context active.
- At least one inbound share in the Snowflake account.
- At least 7 days of `inbound_shares` log history for meaningful baseline detection.
  30 days recommended for reliable Davis AI seasonal modeling.

## Known Limitations

- **`snowflake.data.rows` is a string attribute** on `inbound_shares` logs (not a native metric).
  The workflow uses `makeTimeseries` with `toLong()` as a workaround — this is intentional.
  See the [Shares & Governance Dashboard known limitations](../dashboards/shares-governance/readme.md).
- **Volume anomaly requires history** — Davis AI needs at least 7 days of data to establish a
  baseline. The analyzer will not raise alerts until sufficient history is available.
- **Disappeared threshold is clock-based** — If the shares plugin is disabled, paused, or
  encounters an error during a run, all shares will appear as "disappeared". Check the DSOA
  self-monitoring dashboard before acting on disappeared-share events.

## Screenshots

<!-- Add screenshots after deployment -->

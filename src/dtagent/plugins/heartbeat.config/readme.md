This plugin is the heartbeat of the Dynatrace Snowflake Observability Agent. Once a day it compares what the agent is configured to run with what actually runs in Snowflake.

For every agent task (`TASK_DTAGENT_*`) it reports:

- whether the owning plugin is enabled in the configuration, and the configured schedule,
- whether the task is deployed in Snowflake, its state (`started`, `suspended`, or `missing`), and its actual schedule,
- how many runs the schedule implies over the configured window (`expected_runs`) versus how many runs actually happened, split by outcome (succeeded, failed, skipped, cancelled).

Alongside the task health, the plugin reports the **export success rate**: for every plugin and signal (`logs`, `spans`, `metrics`, `events`, `davis_events`, `biz_events`) it reports how many records the agent attempted to send to Dynatrace and how many Dynatrace accepted since the previous successful report (see [Export success rate](#export-success-rate)).

The plugin also raises flags that make misconfiguration easy to alert on:

- `is_missing` - the task is enabled in the configuration but not deployed,
- `is_unexpected` - the task is started although it is disabled in the configuration,
- `is_suspended` - the task is enabled in the configuration but suspended,
- `has_schedule_drift` - the deployed schedule differs from the configured one,
- `schedule_supported` - `false` when the expected runs could not be calculated.

Expected runs are calculated for cron schedules (`USING CRON ... <time zone>`) and fixed intervals (for example, `30 MINUTES`). Schedules that depend on other tasks (`AFTER ...`) are not supported; such tasks are flagged with `schedule_supported = false` and get no `expected_runs`.

Log level reflects health: `ERROR` for a missing task; `WARN` for an unexpected, suspended, drifted, or unsupported-schedule task; `INFO` otherwise.

By default, the plugin executes once a day at 06:00 UTC and compares the previous 24 hours.

> **Note:** The heartbeat is itself an agent task. If the agent stops running, the heartbeat stops too; detect this in Dynatrace by alerting on the **absence** of `heartbeat` logs for longer than the schedule interval (for example, 26 hours for the default schedule).

> **Note:** A task that was resumed or suspended during the window is not corrected for: `expected_runs` always covers the whole window. Read coverage together with `dsoa.heartbeat.actual_state`.

## Export success rate

After every run the agent records, for each plugin and signal, how many records it handed over for sending (`attempted`) and how many Dynatrace accepted (`delivered`), and keeps them in the `STATUS.EXPORT_STATS` table (30 days by default). The heartbeat sums the rows it has not reported yet and reports them in the `heartbeat_exports` context, one row per plugin and signal, as the metrics `dsoa.heartbeat.export.attempted` and `dsoa.heartbeat.export.delivered` with the dimensions `dsoa.export.plugin` and `dsoa.export.signal`.

Both numbers come from the same rows, so `delivered / attempted` is an accurate success rate and does not depend on how the numbers are aligned in time on the tenant.

- Every record is counted once as attempted, no matter how many times its sending was retried. Events that could not be sent are kept and resent; they are counted as attempted only once.
- Records that Dynatrace rejected, also in partially successful requests, are not counted as delivered.
- Counts are persisted in Snowflake after the run, so runs during which Dynatrace was unreachable are reported by the next successful heartbeat.
- Every report covers the interval since the previous *successful* one, not a fixed window (`plugins.heartbeat.window_hours` applies to task runs only). The heartbeat marks the rows it reported (`REPORTED_TS`) only once its own telemetry was delivered, so a missed or failed heartbeat is followed by one that also reports the missed interval; the rows carry `dsoa.heartbeat.export.reported_from` and `dsoa.heartbeat.export.reported_until`. Delivery counts as confirmed when every signal the heartbeat sent delivered at least one record. A report delivered but not marked (for example, when marking failed) is repeated, so `timeseries` sums can count such an interval twice.
- Rows from the last minute are left for the next heartbeat, and the statistics of the heartbeat's own run appear in the next report.
- Rows not reported within the retention period are deleted; an outage longer than that loses its statistics.
- Turn the recording off with `plugins.self_monitoring.export_stats_enabled: false`; set the retention with `plugins.self_monitoring.export_stats_retention_days` (default `30`).

## Multitenancy

Task names do not contain the multitenancy `TAG`, so several agent instances in one Snowflake account have identically named tasks. Run counts are therefore restricted to this instance's database and `APP` schema, and every row carries `db.namespace` (the instance's database) as a dimension. `deployment.environment.name` (and `deployment.environment.tag` when `core.tag` is set) are attached by the agent to every log and metric like for any other plugin.

## Querying in Dynatrace

Tasks that need attention:

```dql
fetch logs
| filter db.system == "snowflake" and dsoa.run.plugin == "heartbeat"
| filter dsoa.heartbeat.is_missing == true or dsoa.heartbeat.is_unexpected == true
    or dsoa.heartbeat.is_suspended == true or dsoa.heartbeat.has_schedule_drift == true
| fields timestamp, dsoa.heartbeat.task, dsoa.heartbeat.actual_state, dsoa.heartbeat.configured_schedule, dsoa.heartbeat.actual_schedule
| sort timestamp desc
```

Run coverage per task:

```dql
timeseries {
    expected = sum(dsoa.heartbeat.expected_runs),
    succeeded = sum(dsoa.heartbeat.runs.succeeded)
  },
  by: { dsoa.heartbeat.task, deployment.environment.name }
```

Export success rate per plugin and signal:

```dql
timeseries {
    attempted = sum(dsoa.heartbeat.export.attempted),
    delivered = sum(dsoa.heartbeat.export.delivered)
  },
  by: { dsoa.export.plugin, dsoa.export.signal, deployment.environment.name }
| fieldsAdd success_rate_pct = 100 * delivered[] / attempted[]
```

## Heartbeat summary in the User-Agent

Unless `plugins.heartbeat.report_via_user_agent` is `false`, the plugin also reports a summary in the `User-Agent` of small dedicated requests to
Dynatrace (empty requests to the metrics endpoint, which answers `400`; only their `User-Agent` matters, and it is routed all the same; they are separate from the plugin's own telemetry), which is routed to the DSOA self-monitoring tenant. The
`User-Agent` is cut to 64 characters there, so there is one request per report and each report is complete on its own: filter by `hb` and add up.
A report has no `plugin` segment and its environment is cut to 16 characters; the time of the report is the time the request arrived.

```text
dsoa/1.0.0;env=PROD;hb=t;exp=48;ok=47;fail=1
dsoa/1.0.0;env=PROD;hb=l;exp=1200;dlv=1198
dsoa/1.0.0;env=PROD;tk=query_history;exp=48;ok=47
```

- `hb=t` - task runs: `exp` expected, `ok` succeeded and `fail` failed runs in the configured window (`plugins.heartbeat.window_hours`; window
  total: use the latest report).
- `hb=l|s|m|e|d|b` - records of a signal (logs, spans, metrics, events, davis events, biz events): `exp` attempted and `dlv` delivered since the
  previous report (delta: sum the reports).
- `tk=<task>` - task completion, one report per task: `exp` how many times the task should have run (left out when its schedule cannot be
  evaluated) and `ok` how many times it succeeded in the configured window (window total: use the latest report). The task name is the name of
  the task without the `TASK_DTAGENT_` prefix, in lower case, and is shortened, when necessary, so that the counts fit. Tasks that are neither
  expected to run nor ran are not reported. The reports are sent one after another, and sending stops at the first one that cannot be sent (connection error or timeout); the status of the response does not matter.

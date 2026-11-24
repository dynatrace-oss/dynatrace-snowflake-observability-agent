This plugin is the heartbeat of the Dynatrace Snowflake Observability Agent. Once a day it compares what the agent is configured to run with what actually runs in Snowflake.

For every agent task (`TASK_DTAGENT_*`) it reports:

- whether the owning plugin is enabled in the configuration, and the configured schedule,
- whether the task is deployed in Snowflake, its state (`started`, `suspended`, or `missing`), and its actual schedule,
- how many runs the schedule implies over the configured window (`expected_runs`) versus how many runs actually happened, split by outcome (succeeded, failed, skipped, cancelled).

Alongside the task health, the plugin reports the **export success rate**: for every plugin and signal (`logs`, `spans`, `metrics`, `events`, `davis_events`, `biz_events`) it reports how many records the agent attempted to send to Dynatrace and how many Dynatrace accepted over the window (see [Export success rate](#export-success-rate)).

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

After every run the agent records, for each plugin and signal, how many records it handed over for sending (`attempted`) and how many Dynatrace accepted (`delivered`), and keeps them in the `STATUS.EXPORT_STATS` table (30 days by default). The heartbeat sums them over the window and reports them in the `heartbeat_exports` context, one row per plugin and signal, as the metrics `dsoa.heartbeat.export.attempted` and `dsoa.heartbeat.export.delivered` with the dimensions `dsoa.export.plugin` and `dsoa.export.signal`.

Both numbers come from the same rows, so `delivered / attempted` is an accurate success rate and does not depend on how the numbers are aligned in time on the tenant.

- Every record is counted once as attempted, no matter how many times its sending was retried. Events that could not be sent are kept and resent; they are counted as attempted only once.
- Records that Dynatrace rejected, also in partially successful requests, are not counted as delivered.
- Counts are persisted in Snowflake after the run, so runs during which Dynatrace was unreachable are reported by the next successful heartbeat.
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

This plugin is the heartbeat of the Dynatrace Snowflake Observability Agent. Once a day it compares what the agent is configured to run with what actually runs in Snowflake.

For every agent task (`TASK_DTAGENT_*`) it reports:

- whether the owning plugin is enabled in the configuration, and the configured schedule,
- whether the task is deployed in Snowflake, its state (`started`, `suspended`, or `missing`), and its actual schedule,
- how many runs the schedule implies over the configured window (`expected_runs`) versus how many runs actually happened, split by outcome (succeeded, failed, skipped, cancelled).

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

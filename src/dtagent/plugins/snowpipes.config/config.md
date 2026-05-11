> **IMPORTANT**: For this plugin to function correctly, `MONITOR on PIPES` must be granted to the `DTAGENT_VIEWER` role (required for `SYSTEM$PIPE_STATUS()`).
> By default, when the `admin` scope is installed, this is handled by the `P_GRANT_MONITOR_SNOWPIPES()` procedure, which is executed with the elevated privileges of the `DTAGENT_ADMIN` role (created only when the `admin` scope is installed), via the `APP.TASK_DTAGENT_SNOWPIPES_GRANTS` task.
> The schedule for this task can be configured separately using the `PLUGINS.SNOWPIPES.SCHEDULE_GRANTS` configuration option.
>
> When the `admin` scope is **not** installed, these grants are **never applied automatically**. The plugin will report
> **no telemetry for monitored pipes** without any errors or warnings. You must apply the grants manually
> (see below) before going to production without admin scope.

The grant granularity is derived automatically from the `include` pattern:

| Include pattern             | Grant level | SQL issued                                        |
|-----------------------------|-------------|---------------------------------------------------|
| `%.%.%` or `PROD_DB.%.%`    | Database    | `GRANT MONITOR ON ALL/FUTURE PIPES IN DATABASE …` |
| `PROD_DB.ANALYTICS.%`       | Schema      | `GRANT MONITOR ON ALL/FUTURE PIPES IN SCHEMA …`   |
| `PROD_DB.ANALYTICS.MY_PIPE` | Pipe        | `GRANT MONITOR ON PIPE …` (no FUTURE grant)       |

Alternatively, you may choose to grant the required permissions manually, using the appropriate `GRANT MONITOR ON ALL/FUTURE PIPES IN …` statement, depending on the desired granularity.

### Configuration keys

| Key                                      | Default                               | Description                                       |
|------------------------------------------|---------------------------------------|---------------------------------------------------|
| `plugins.snowpipes.include`              | `['%.%.%']`                           | Pipe name patterns to include (fully qualified)   |
| `plugins.snowpipes.exclude`              | `[DTAGENT_DB.%.%]`                    | Pipe name patterns to exclude                     |
| `plugins.snowpipes.schedule`             | `USING CRON */5 * * * * UTC`          | Fast-mode schedule (SHOW PIPES + PIPE_STATUS)     |
| `plugins.snowpipes.schedule_history`     | `USING CRON 0 * * * * UTC`            | Deep-mode schedule (COPY_HISTORY + USAGE_HISTORY) |
| `plugins.snowpipes.schedule_grants`      | `USING CRON 30 */12 * * * UTC`        | Admin grant task schedule                         |
| `plugins.snowpipes.lookback_hours`       | `4`                                   | Lookback window for COPY_HISTORY (hours)          |
| `plugins.snowpipes.lookback_hours_usage` | `6`                                   | Lookback window for PIPE_USAGE_HISTORY (hours)    |
| `plugins.snowpipes.is_disabled`          | `false`                               | Disable the plugin                                |
| `plugins.snowpipes.telemetry`            | `[metrics, logs, events, biz_events]` | Enabled telemetry types                           |

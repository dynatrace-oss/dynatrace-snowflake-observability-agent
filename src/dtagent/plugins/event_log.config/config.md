## Configuration Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `PLUGINS.EVENT_LOG.MAX_ENTRIES` | int | `10000` | Maximum number of event log entries fetched per run. Acts as a safety cap to avoid long-running queries. |
| `PLUGINS.EVENT_LOG.LOOKBACK_HOURS` | int | `24` | How far back (in hours) the plugin looks for new events on each run. Only applies when no prior processed timestamp exists. Increase for initial setup or after a long gap; decrease to reduce query cost. |
| `PLUGINS.EVENT_LOG.RETENTION_HOURS` | int | `12` | How long (in hours) the cleanup task retains entries in `STATUS.EVENT_LOG`. Only applies if this agent instance owns the event table. |
| `PLUGINS.EVENT_LOG.SCHEDULE` | string | `USING CRON */30 * * * * UTC` | Cron schedule for the main event log processing task. |
| `PLUGINS.EVENT_LOG.SCHEDULE_CLEANUP` | string | `USING CRON 0 * * * * UTC` | Cron schedule for the cleanup task that removes old entries from `STATUS.EVENT_LOG`. |
| `PLUGINS.EVENT_LOG.IS_DISABLED` | bool | `false` | Set to `true` to disable this plugin entirely. |
| `PLUGINS.EVENT_LOG.TELEMETRY` | list | `["metrics", "logs", "biz_events", "spans"]` | Telemetry types to emit. Remove items to suppress specific output types. |

## Cost Optimization Guidance

The event log plugin queries `STATUS.EVENT_LOG` on every run. The following settings directly affect compute cost:

- **`LOOKBACK_HOURS`**: This window is used only when no prior processed timestamp is available (first run, or after a reset). During normal operation the plugin advances from the last processed timestamp automatically. A large lookback window on first run can cause a heavy initial query — consider starting with `12` or `24` and increasing only if needed.
- **`MAX_ENTRIES`**: Hard cap on rows processed per run. The default (`10000`) protects against runaway queries. If your Snowflake account generates very high event volumes, lower this value and rely on the schedule frequency to catch up incrementally.
- **`RETENTION_HOURS`**: Shorter retention reduces the size of `STATUS.EVENT_LOG`, which improves scan performance. Set this lower than `LOOKBACK_HOURS` to avoid situations where the cleanup removes events before the plugin can process them. The recommended ratio is `retention_hours >= lookback_hours`.
- **`SCHEDULE`**: Running more frequently (e.g., every 5 minutes) increases credit usage. The default every-30-minutes cadence balances freshness against cost. For high-volume accounts, consider running less frequently with higher `MAX_ENTRIES`.

> **IMPORTANT**: A dedicated cleanup task, `APP.TASK_DTAGENT_EVENT_LOG_CLEANUP`, ensures that the `EVENT_LOG` table contains only data no older than the duration you define with the `PLUGINS.EVENT_LOG.RETENTION_HOURS` configuration option.
> You can schedule this task separately using the `PLUGINS.EVENT_LOG.SCHEDULE_CLEANUP` configuration option, run the cleanup procedure `APP.P_CLEANUP_EVENT_LOG()` manually, or manage the retention of data in the `EVENT_LOG` table yourself.

> **INFO**: The `EVENT_LOG` table cleanup process works only if this specific instance of Dynatrace Snowflake Observability Agent set up the table.

## Configuration Options

| Key                                        | Type   | Default                               | Description                                                                                                                                                               |
| ------------------------------------------ | ------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.event_log.max_entries`            | int    | `10000`                               | Maximum number of event log entries fetched per run. Acts as a safety cap to avoid long-running queries.                                                                  |
| `plugins.event_log.lookback_hours`         | int    | `24`                                  | How far back (in hours) the plugin looks for new events on each run. Only applies when no prior processed timestamp exists. Increase for initial setup or after a long gap; decrease to reduce query cost. |
| `plugins.event_log.retention_hours`        | int    | `12`                                  | How long (in hours) the cleanup task retains entries in `STATUS.EVENT_LOG`. Only applies if this agent instance owns the event table.                                     |
| `plugins.event_log.schedule`               | string | `USING CRON */30 * * * * UTC`         | Cron schedule for the main event log processing task.                                                                                                                     |
| `plugins.event_log.schedule_cleanup`       | string | `USING CRON 0 * * * * UTC`            | Cron schedule for the cleanup task that removes old entries from `STATUS.EVENT_LOG`.                                                                                      |
| `plugins.event_log.is_disabled`            | bool   | `false`                               | Set to `true` to disable this plugin entirely.                                                                                                                            |
| `plugins.event_log.telemetry`              | list   | `["metrics", "logs", "biz_events", "spans"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                           |

## Cost Optimization Guidance

The event log plugin queries `STATUS.EVENT_LOG` on every run. The following settings directly affect compute cost:

- **`lookback_hours`**: This window is used only when no prior processed timestamp is available (first run, or after a reset). During normal operation the plugin advances from the last processed timestamp automatically. A large lookback window on first run can cause a heavy initial query — consider starting with `12` or `24` and increasing only if needed.
- **`max_entries`**: Hard cap on rows processed per run. The default (`10000`) protects against runaway queries. If your Snowflake account generates very high event volumes, lower this value and rely on the schedule frequency to catch up incrementally.
- **`retention_hours`**: Shorter retention reduces the size of `STATUS.EVENT_LOG`, which improves scan performance. Set this lower than `lookback_hours` to avoid situations where the cleanup removes events before the plugin can process them. The recommended ratio is `retention_hours >= lookback_hours`.
- **`schedule`**: Running more frequently (e.g., every 5 minutes) increases credit usage. The default every-30-minutes cadence balances freshness against cost. For high-volume accounts, consider running less frequently with higher `max_entries`.

> **IMPORTANT**: A dedicated cleanup task, `APP.TASK_DTAGENT_EVENT_LOG_CLEANUP`, ensures that the `EVENT_LOG` table contains only data no older than the duration you define with the `plugins.event_log.retention_hours` configuration option.
> You can schedule this task separately using the `plugins.event_log.schedule_cleanup` configuration option, run the cleanup procedure `APP.P_CLEANUP_EVENT_LOG()` manually, or manage the retention of data in the `EVENT_LOG` table yourself.

> **INFO**: The `EVENT_LOG` table cleanup process works only if this specific instance of Dynatrace Snowflake Observability Agent set up the table.

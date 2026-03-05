| Key                                  | Type   | Default                                      | Description                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------ | ------ | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.event_log.max_entries`      | int    | `10000`                                      | Maximum number of event log entries fetched per run. Acts as a safety cap to avoid long-running queries.                                                                                                                                                                                                                                                                                        |
| `plugins.event_log.lookback_hours`   | int    | `24`                                         | How far back (in hours) the plugin looks for new events on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Increase for initial setup; decrease to reduce query cost. |
| `plugins.event_log.retention_hours`  | int    | `24`                                         | How long (in hours) the cleanup task retains entries in `STATUS.EVENT_LOG`. Only applies if this agent instance owns the event table.                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule`         | string | `USING CRON */30 * * * * UTC`                | Cron schedule for the main event log processing task.                                                                                                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule_cleanup` | string | `USING CRON 0 * * * * UTC`                   | Cron schedule for the cleanup task that removes old entries from `STATUS.EVENT_LOG`.                                                                                                                                                                                                                                                                                                            |
| `plugins.event_log.is_disabled`      | bool   | `false`                                      | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                  |
| `plugins.event_log.telemetry`        | list   | `["metrics", "logs", "biz_events", "spans"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                        |

### Cost Optimization Guidance

The event log plugin queries `STATUS.EVENT_LOG` on every run. The following settings directly affect compute cost:

- **`lookback_hours`**: This window defines how far back the plugin reads on each run. If no prior processed timestamp is available (first run, or after a reset), the plugin starts from `now - lookback_hours`. During normal operation the plugin starts from the more recent of the last processed timestamp and `now - lookback_hours`, capping catch-up after long gaps. A large lookback window can cause heavy queries after a reset — consider starting with `12` or `24` and increasing only if needed.
- **`max_entries`**: Hard cap on rows processed per run. The default (`10000`) protects against runaway queries. If your Snowflake account generates very high event volumes, lower this value and rely on the schedule frequency to catch up incrementally.
- **`retention_hours`**: Shorter retention reduces the size of `STATUS.EVENT_LOG`, which improves scan performance. Set this higher than `lookback_hours` to avoid situations where the cleanup removes events before the plugin can process them. The recommended ratio is `retention_hours >= lookback_hours`.
- **`schedule`**: Running more frequently (e.g., every 5 minutes) increases credit usage. The default every-30-minutes cadence balances freshness against cost. For high-volume accounts, consider running less frequently with higher `max_entries`.

> **IMPORTANT**: A dedicated cleanup task, `APP.TASK_DTAGENT_EVENT_LOG_CLEANUP`, ensures that the `EVENT_LOG` table contains only data no older than the duration you define with the `plugins.event_log.retention_hours` configuration option.
> You can schedule this task separately using the `plugins.event_log.schedule_cleanup` configuration option, run the cleanup procedure `APP.P_CLEANUP_EVENT_LOG()` manually, or manage the retention of data in the `EVENT_LOG` table yourself.

> **INFO**: The `EVENT_LOG` table cleanup process works only if this specific instance of Dynatrace Snowflake Observability Agent set up the table.

### Cross-Tenant Monitoring

By default (`plugins.event_log.cross_tenant_monitoring: true`) the plugin also reports `WARN`/`ERROR` log entries, metrics, and spans originating from **other** `DTAGENT_*_DB` instances visible in the same event table. This allows one DSOA deployment to surface health issues from sibling deployments without logging into Snowflake directly.

It is recommended to enable cross-tenant monitoring in **only one primary DSOA tenant** and set `cross_tenant_monitoring: false` in all others to avoid duplicate reporting across deployments.

```yaml
plugins:
  event_log:
    cross_tenant_monitoring: false  # disable on secondary tenants
```

### Database Filtering

Use `plugins.event_log.databases` to restrict event log monitoring to specific databases. The list accepts SQL `LIKE` patterns (`%` matches any sequence of characters, `_` matches any single character). When the list is absent or empty, **all databases** are included.

```yaml
plugins:
  event_log:
    databases:
      - MYAPP_DB       # exact match
      - ANALYTICS%     # all databases starting with ANALYTICS_
```

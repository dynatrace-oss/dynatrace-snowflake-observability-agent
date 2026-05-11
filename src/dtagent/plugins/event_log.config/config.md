| Key                                          | Type   | Default                                      | Description                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------------------- | ------ | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.event_log.max_entries`              | int    | `10000`                                      | Maximum number of event log entries fetched per run. Acts as a safety cap to avoid long-running queries.                                                                                                                                                                                                                                                                                        |
| `plugins.event_log.lookback_hours`           | int    | `24`                                         | How far back (in hours) the plugin looks for new events on each run. If no prior processed timestamp exists, the plugin starts from `now - lookback_hours`. If a prior timestamp exists, the plugin starts from the more recent of that timestamp and `now - lookback_hours`, so it never reads data older than the lookback window. Increase for initial setup; decrease to reduce query cost. |
| `plugins.event_log.retention_hours`          | int    | `24`                                         | How long (in hours) the cleanup task retains entries in `STATUS.EVENT_LOG`. Only applies if this agent instance owns the event table.                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule`                 | string | `USING CRON */30 * * * * UTC`                | Cron schedule for the main event log processing task.                                                                                                                                                                                                                                                                                                                                           |
| `plugins.event_log.schedule_cleanup`         | string | `USING CRON 0 * * * * UTC`                   | Cron schedule for the cleanup task that removes old entries from `STATUS.EVENT_LOG`.                                                                                                                                                                                                                                                                                                            |
| `plugins.event_log.is_disabled`              | bool   | `false`                                      | Set to `true` to disable this plugin entirely.                                                                                                                                                                                                                                                                                                                                                  |
| `plugins.event_log.telemetry`                | list   | `["metrics", "logs", "biz_events", "spans"]` | Telemetry types to emit. Remove items to suppress specific output types.                                                                                                                                                                                                                                                                                                                        |
| `plugins.event_log.discover_db_event_tables` | bool   | `false`                                      | When `true`, discovers per-database `EVENT_TABLE` parameter overrides and unions them into `STATUS.EVENT_LOG`. Each record is tagged with `_dsoa_source_table` in `_RESOURCE_ATTRIBUTES`. Opt-in — existing deployments unchanged on upgrade. Requires a custom account-level event table (no effect when DSOA owns the event table).                                                           |

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

In case you would like to enable cross-tenant monitoring on **only one DSOA tenant**, e.g., to avoid duplicate reporting across deployments,
you need to set `cross_tenant_monitoring: false` in all other tenants.

```yaml
plugins:
  event_log:
    cross_tenant_monitoring: false # disable on tenants that should report only their own WARN/ERROR self-monitoring entries
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

### Per-Database Event Tables

When Snowflake customers use per-database event table overrides (`ALTER DATABASE X SET EVENT_TABLE = ...`), telemetry emitted inside those databases goes to a separate table that DSOA would normally miss. Set `discover_db_event_tables: true` to opt in to multi-source discovery.

When enabled, `SETUP_EVENT_TABLE()` runs at agent startup and on config change. It enumerates databases in scope (filtered by `databases` allow-list if set), checks each database for a `DATABASE`-level `EVENT_TABLE` parameter override, and rebuilds `STATUS.EVENT_LOG` as a `UNION ALL` view:

- **Account table branch**: rows whose `snow.database.name` is _not_ in an override DB — tagged with the account event table FQN as `_dsoa_source_table`.
- **Per-DB override branches**: one branch per override DB — rows tagged with the override table FQN as `_dsoa_source_table`.

The `_dsoa_source_table` key is added to `RESOURCE_ATTRIBUTES` via `OBJECT_INSERT` and surfaces in Dynatrace as the `_dsoa_source_table` log attribute.

**Permission handling**: DSOA attempts `GRANT SELECT` on each newly discovered override table. Failures are logged as warnings and skipped — they do not abort setup.

**Re-resolve behavior**: the view is rebuilt on every agent restart (via `UPDATE_EVENT_LOG_CONF()`). If a DB is dropped between restarts, it is removed from the next rebuild. Newly added DB overrides are picked up on the next restart.

```yaml
plugins:
  event_log:
    discover_db_event_tables: true  # opt-in; default false
    databases:
      - MYAPP_DB    # only check this DB for overrides (and filter event log entries)
```

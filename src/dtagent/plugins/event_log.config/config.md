> **IMPORTANT**: A dedicated cleanup task, `APP.TASK_DTAGENT_EVENT_LOG_CLEANUP`, ensures that the `EVENT_LOG` table contains only data no older than the duration you define with the `PLUGINS.EVENT_LOG.RETENTION_HOURS` configuration option.
> You can schedule this task separately using the `PLUGINS.EVENT_LOG.SCHEDULE_CLEANUP` configuration option, run the cleanup procedure `APP.P_CLEANUP_EVENT_LOG()` manually, or manage the retention of data in the `EVENT_LOG` table yourself.

> **INFO**: The `EVENT_LOG` table cleanup process works only if this specific instance of Dynatrace Snowflake Observability Agent set up the table.

## Cross-Tenant Monitoring

By default (`plugins.event_log.cross_tenant_monitoring: true`) the plugin also reports `WARN`/`ERROR` log entries, metrics, and spans originating from **other** `DTAGENT_*_DB` instances visible in the same event table. This allows one DSOA deployment to surface health issues from sibling deployments without logging into Snowflake directly.

In case you would like to enable cross-tenant monitoring on **only one DSOA tenant**, e.g., to avoid duplicate reporting across deployments,
you need to set `cross_tenant_monitoring: false` in all other tenants.

```yaml
plugins:
  event_log:
    cross_tenant_monitoring: false # disable on tenants that should report only their own WARN/ERROR self-monitoring entries
```

## Database Filtering

Use `plugins.event_log.databases` to restrict event log monitoring to specific databases. The list accepts SQL `LIKE` patterns (`%` matches any sequence of characters, `_` matches any single character). When the list is absent or empty, **all databases** are included.

```yaml
plugins:
  event_log:
    databases:
      - MYAPP_DB       # exact match
      - ANALYTICS%     # all databases starting with ANALYTICS_
```

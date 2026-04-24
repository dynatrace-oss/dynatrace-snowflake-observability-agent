| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `plugins.org_costs.lookback_hours` | int | `48` | How far back (in hours) the plugin looks for organization metering data on each run. A 48-hour window accommodates Snowflake's ~2-hour view latency and ensures no daily records are missed across collection cycles. |
| `plugins.org_costs.schedule` | string | `USING CRON 0 */6 * * * UTC` | Cron schedule for the org costs collection task (every 6 hours). |
| `plugins.org_costs.is_disabled` | bool | `true` | Set to `false` to enable this plugin. Requires `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` database role granted to `DTAGENT_VIEWER` (see readme). |
| `plugins.org_costs.telemetry` | list | `["logs", "metrics", "biz_events"]` | Telemetry types to emit. Remove items to suppress specific output types. |

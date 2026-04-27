| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `plugins.cold_tables.lookback_days` | int | `365` | How far back (in days) the plugin scans `ACCESS_HISTORY` to count table accesses. |
| `plugins.cold_tables.cold_threshold_days` | int | `90` | Tables not accessed within this many days are classified as `cold`. |
| `plugins.cold_tables.schedule` | string | `USING CRON 0 6 * * * UTC` | Cron schedule for the cold tables collection task. |
| `plugins.cold_tables.is_disabled` | bool | `false` | Set to `true` to disable this plugin entirely. |
| `plugins.cold_tables.telemetry` | list | `["metrics", "logs"]` | Telemetry types to emit. Remove items to suppress specific output types. |

## Configuration Options

| Key                                    | Type   | Default                       | Description                                                                                                                               |
| -------------------------------------- | ------ | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.login_history.lookback_hours` | int    | `24`                          | How far back (in hours) the plugin looks for login and session events on each run. Only applies when no prior processed timestamp exists. |
| `plugins.login_history.schedule`       | string | `USING CRON */30 * * * * UTC` | Cron schedule for the login history collection task.                                                                                      |
| `plugins.login_history.is_disabled`    | bool   | `false`                       | Set to `true` to disable this plugin entirely.                                                                                            |
| `plugins.login_history.telemetry`      | list   | `["logs", "biz_events"]`      | Telemetry types to emit. Remove items to suppress specific output types.                                                                  |

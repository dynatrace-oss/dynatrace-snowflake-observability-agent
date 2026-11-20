| Key                              | Type   | Default                    | Description                                                                                                                                         |
| -------------------------------- | ------ | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.heartbeat.window_hours` | int    | `24`                       | Length (in hours) of the rolling window, ending at the heartbeat run, over which expected and actual task runs are compared.                        |
| `plugins.heartbeat.schedule`     | string | `USING CRON 0 6 * * * UTC` | Cron schedule for the heartbeat task. With the default window, a daily run covers the previous 24 hours; keep the window in line with the schedule. |
| `plugins.heartbeat.is_disabled`  | bool   | `false`                    | Set to `true` to disable this plugin entirely.                                                                                                      |
| `plugins.heartbeat.telemetry`    | list   | `["metrics", "logs"]`      | Telemetry types to emit. Remove items to suppress specific output types.                                                                            |

> **Note:** `TASK_HISTORY()` is queried with a result limit of 10,000 rows. On accounts where the agent tasks together run more often than that within the window, the counts are truncated; shorten `window_hours` in that case.

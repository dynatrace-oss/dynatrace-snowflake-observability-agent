> **IMPORTANT**: For this plugin to monitor inbound shares correctly, `DTAGENT_VIEWER` must have
> `IMPORTED PRIVILEGES` on each shared database.
> By default, when the `admin` scope is installed, `APP.P_GRANT_IMPORTED_PRIVILEGES()` is called
> automatically whenever an inbound share database cannot be queried — granting access on demand.
>
> When the `admin` scope is **not** installed, this grant is **never applied automatically**.
> The plugin will silently skip inbound share table discovery for any shared database that
> `DTAGENT_VIEWER` cannot access — no errors, just missing data. You must grant manually for
> each shared database before going to production without admin scope:
>
> ```sql
> GRANT IMPORTED PRIVILEGES ON DATABASE <shared_database_name> TO ROLE DTAGENT_VIEWER;
> ```
>
> Repeat for every inbound shared database your account has access to.

## Configuration keys

| Key                                      | Default                            | Description                                      |
|------------------------------------------|------------------------------------|--------------------------------------------------|
| `plugins.shares.schedule`                | `USING CRON */30 * * * * UTC`      | Schedule for the shares collection task.         |
| `plugins.shares.is_disabled`             | `false`                            | Set to `true` to disable this plugin entirely.   |
| `plugins.shares.exclude_from_monitoring` | `[]`                               | Share names to exclude from detailed monitoring. |
| `plugins.shares.exclude`                 | `[""]`                             | Object name patterns to exclude from tracking.   |
| `plugins.shares.include`                 | `['%.%.%']`                        | Object name patterns to include in tracking.     |
| `plugins.shares.telemetry`               | `["logs", "events", "biz_events"]` | Telemetry types to emit.                         |

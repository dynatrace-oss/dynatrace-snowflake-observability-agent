> **IMPORTANT**: For this plugin to function correctly, `MONITOR on DYNAMIC TABLES` must be granted to the `DTAGENT_VIEWER` role.
> By default, when the `admin` scope is installed, this is handled by the `P_GRANT_MONITOR_DYNAMIC_TABLES()` procedure, which is executed with the elevated privileges of the `DTAGENT_ADMIN` role (created only when the `admin` scope is installed), via the `APP.TASK_DTAGENT_DYNAMIC_TABLES_GRANTS` task.
> The schedule for this task can be configured separately using the `PLUGINS.DYNAMIC_TABLES.SCHEDULE_GRANTS` configuration option.
>
> When the `admin` scope is **not** installed, these grants are **never applied automatically**. The plugin will report
> **no telemetry for monitored dynamic tables** without any errors or warnings. You must apply the grants manually
> (see below) before going to production without admin scope.

The grant granularity is derived automatically from the `include` pattern:

| Include pattern               | Grant level | SQL issued                                                 |
| ----------------------------- | ----------- | ---------------------------------------------------------- |
| `%.%.%` or `PROD_DB.%.%`      | Database    | `GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN DATABASE …` |
| `PROD_DB.ANALYTICS.%`         | Schema      | `GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN SCHEMA …`   |
| `PROD_DB.ANALYTICS.ORDERS_DT` | Table       | `GRANT MONITOR ON DYNAMIC TABLE …` (no FUTURE grant)       |

Alternatively, you may choose to grant the required permissions manually, using the appropriate `GRANT MONITOR ON ALL/FUTURE DYNAMIC TABLES IN …` statement, depending on the desired granularity.

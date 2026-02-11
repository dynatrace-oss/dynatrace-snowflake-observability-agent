> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be granted `MONITOR` privileges on all warehouses.
> By default, when the `admin` scope is installed, this is ensured through the periodic execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task.
> The schedule for this special task can be configured using the `PLUGINS.QUERY_HISTORY.SCHEDULE_GRANTS` configuration option.
> Since this procedure runs with the elevated privileges of the `DTAGENT_ADMIN` role (which is only created when the `admin` scope is installed), you may choose to:
>

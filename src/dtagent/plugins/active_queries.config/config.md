> **IMPORTANT**: For the `query_history` and `active_queries` plugins to report telemetry for all queries, the `DTAGENT_VIEWER` role must be granted `MONITOR` privileges on all warehouses.  
> This is ensured by default through the periodic execution of the `APP.P_MONITOR_WAREHOUSES()` procedure, triggered by the `APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS` task.  
> The schedule for this special task can be configured using the `PLUGINS.QUERY_HISTORY.SCHEDULE_GRANTS` configuration option.  
> Since this procedure runs with the elevated privileges of the `DTAGENT_ADMIN` role, you may choose to disable it and manually ensure that the `DTAGENT_VIEWER` role is granted the appropriate `MONITOR` rights.

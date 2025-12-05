The `warehouse usage` plugin delivers detailed information regarding warehouses' credit usage, workload, and events triggered on them. This plugin provides telemetry based on the `WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, and `WAREHOUSE_METERING_HISTORY` views.

It sends:

- metrics on hourly credit usage of warehouses,
- metrics on query load values for executed queries,
- log entries on warehouse events, such as creating, dropping, altering, resizing, resuming, or suspending a cluster or the entire warehouse.

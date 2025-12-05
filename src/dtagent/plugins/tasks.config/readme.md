This plugin provides detailed information on the usage and performance of tasks within a Snowflake account. It leverages three key functions/views from Snowflake:

- `TASK_HISTORY`: Delivers the history of task usage for the entire Snowflake account, a specified task, or task graph.
- `TASK_VERSIONS`: Enables retrieval of the history of task versions, with entries indicating the tasks that comprised a task graph and their properties at a given time.
- `SERVERLESS_TASK_HISTORY`: Provides information on the serverless task usage history, including the serverless task name and credits consumed by serverless task usage.

In short, the plugin delivers, as logs by default, information on:

- timestamps of the task execution,
- warehouse ID the task is performed on,
- database ID the task is performed on,
- credits used (as metric).

Additionally, an event is sent when a new task graph version is created. By default, the plugin executes every 90 minutes.

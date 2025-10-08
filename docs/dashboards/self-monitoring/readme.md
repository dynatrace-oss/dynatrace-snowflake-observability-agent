# Dashboard: DSOA Self-Monitoring

This dashboard provides a comprehensive overview of the Dynatrace Snowflake Open Source Agent (DSOA) itself, focusing on its operational health, performance, and resource consumption. It is designed to help administrators monitor the agent's activity, identify performance bottlenecks, and troubleshoot any issues that may arise during its execution.

## Agent Health and Performance

- Displays the number of monitored Snowflake accounts.
- Shows the volume of log lines produced by the agent, categorized by data type.
- Tracks the total elapsed time and execution count for each plugin, helping to identify the most resource-intensive tasks.
![Agent Health Overview](./img/01-plugin-execution-overview.png)

## Plugin Execution Analysis

- Visualizes the execution time for each plugin, based on both business events and query history. This allows for a detailed analysis of how long each data collection task takes to complete.
- Helps in identifying performance trends and spotting anomalies in plugin execution times.
![Plugin Execution Time](./img/02-plugin-execution-times.png)

## Execution Failures and Details

- Monitors for any failed plugin executions, providing immediate visibility into operational errors.
- Lists the most recent plugin executions with their status and environment, allowing for quick inspection and troubleshooting.
![Plugin Execution Failures](./img/03-plugin-tasks-executions.png)

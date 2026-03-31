# Dashboard: Costs Monitoring

This dashboard provides insights into the costs associated with your Snowflake usage. It includes visualizations and metrics that help you monitor and analyze your spending patterns, identify cost drivers, and optimize your resource allocation.

## Cost Monitoring

- Tracks credits used over time.
- Displays the credit quota for resource monitors.
- Shows the percentage of credit quota used, with forecasting to predict future usage.
![Monitoring Credits Consumption](./img/rs-credits-analysis.png)
- Identifies warehouses that are not assigned to a resource monitor, which can lead to uncontrolled costs.
![Missing Resource Monitors Monitoring Warehouses](./img/whs-missing-rs.png)

## Warehouse Performance

- Visualizes query execution time, queued overload time, and queued provisioning time per warehouse.
![Warehouse Performance Metrics](./img/whs-analysis.png)
- Shows delays in resuming and suspending warehouses.
![Warehouse Resume and Suspend Delays](./img/whs-resume-suspend-delay.png)

## Slow Query Analysis

- Identifies queries running longer than a configurable threshold.
- Lists currently active slow queries, with additional analysis to detect queries which might exhaust warehouse credits.
- Provides details on historical slow queries, including the user, warehouse, and query text.
![Slow Queries Analysis Section](./img/slow-queries-analysis.png)

## Credits Exhaustion Forecast

- Displays daily credits consumption trends alongside quota limits as a line chart, enabling visual identification of consumption velocity and remaining runway.
- Lists resource monitors sorted by percentage of quota used (descending), highlighting monitors approaching exhaustion with their remaining credits and frequency settings.
![Credits Exhaustion Forecast](./img/credits-exhaustion-forecast.png)

## Resource Monitor Health

- Honeycomb visualization of resource monitor active/inactive states with color-coded status (green = active, red = inactive) for rapid identification of disabled monitors.
- Comprehensive table of all resource monitors showing frequency, active state, quota, used credits, and remaining credits for configuration review.
![Resource Monitor Health](./img/resource-monitor-health.png)

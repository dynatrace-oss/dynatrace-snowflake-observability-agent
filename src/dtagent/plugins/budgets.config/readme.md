This plugin enables monitoring of Snowflake budgets, resources linked to them, and their expenditures. It sets up and manages the Dynatrace Snowflake Observability Agent's own budget.

All budgets the agent has been granted access to are reported as logs and metrics; this includes their details, spending limit, and recent
expenditures. The plugin runs once a day and excludes already reported expenditures.

> **Note**: This plugin is **disabled by default** because custom budget monitoring requires per-budget privilege grants.
> The account budget (visible via `SNOWFLAKE.BUDGET_VIEWER`) is accessible automatically once enabled. For custom budgets,
> use `P_GRANT_BUDGET_MONITORING()` (requires admin scope) or grant privileges manually — see below.

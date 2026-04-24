# Org-Level Costs Observability Dashboard

Organization-wide Snowflake cost and usage monitoring. Requires the `org_costs` plugin to be
enabled and the Snowflake account to have access to `SNOWFLAKE.ORGANIZATION_USAGE`.

## Tiles

| Tile                                       | Metric                                  | Description                                                                     |
|--------------------------------------------|-----------------------------------------|---------------------------------------------------------------------------------|
| Organization Credits Used by Service Type  | `snowflake.org.credits.used`            | Daily credit consumption broken down by service type and service name           |
| Organization Cloud Services Credits        | `snowflake.org.credits.cloud_services`  | Cloud-services adjustment credits by service type                               |
| Organization Storage by Type               | `snowflake.org.storage.bytes`           | Storage bytes by storage type (database, stage, failsafe) and account           |
| Organization Data Transfer Volume          | `snowflake.org.transfer.bytes`          | Cross-cloud and cross-region data transfer bytes                                |
| Organization Billing Amount by Service     | `snowflake.org.billing.amount`          | Billed currency amounts per service type and account                            |
| Remaining Contract Balance                 | `snowflake.org.balance.*.remaining`     | Free-usage, capacity, on-demand, rollover, and total remaining balances         |

## Variables

| Variable    | Description                                          |
|-------------|------------------------------------------------------|
| `$Accounts` | Deployment environment filter (Snowflake account tag)|

## Prerequisites

- `org_costs` plugin enabled (`plugins.org_costs.is_disabled: false`)
- Snowflake account linked to an organization (`ORGADMIN` access or organization-linked)
- `DTAGENT_VIEWER` granted `IMPORTED PRIVILEGES` on the `SNOWFLAKE` database (handled during init)

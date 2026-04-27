# Org Contract Balance Warning Workflow

Monitors organization-level Snowflake remaining contract balances and sends an alert when any
balance category drops below a configurable threshold.

## Trigger

Runs every 6 hours on a schedule.

## Tasks

| Task            | Action                                  | Description                                                                                                                                    |
|-----------------|--------------------------------------   |------------------------------------------------------------------------------------------------------------------------------------------------|
| `check_balance` | `dynatrace.automations:run-javascript`  | Queries the last known values for all five `snowflake.org.balance.*.remaining` metrics and alerts when any drops below the configured threshold|

## Configuration

Edit the `BALANCE_THRESHOLD` constant inside the `check_balance` script to set the alert
threshold (default: `1000` in your contract currency).

## Prerequisites

- `org_costs` plugin enabled with `org_billing_remaining_balance` context active
- Snowflake account linked to an organization with access to `SNOWFLAKE.ORGANIZATION_USAGE`
- Dynatrace Automations access token with `metrics:read` scope

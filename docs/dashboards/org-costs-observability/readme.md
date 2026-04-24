# Snowflake Consumption (Organization Level) Dashboard

Organization-wide Snowflake consumption monitoring across all accounts. Requires the `org_costs`
plugin to be enabled and the Snowflake account to have `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` granted.

## Prerequisites

- `org_costs` plugin enabled (`plugins.org_costs.is_enabled: true`)
- Snowflake account linked to an organization (ORGADMIN access or organization-linked account)
- `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` role granted to `DTAGENT_VIEWER` (handled during init)

## Variables

| Variable       | Type  | Visible | Description                                                                       |
|----------------|-------|---------|-----------------------------------------------------------------------------------|
| `$Accounts`    | query | yes     | Multi-select filter for Snowflake account identifiers (`deployment.environment`)  |
| `$credit_rate` | text  | no      | Credit rate in USD (default: `3.00`) — reserved for Phase B cost calculations     |
| `$bu_mapping`  | text  | no      | JSON mapping of account names to Business Units — reserved for Phase C BU view    |

## Sections and Tiles (Phase A)

### §2 Credit Consumption

| Tile                              | Visualization | Metric / Query                                                      |
|-----------------------------------|---------------|---------------------------------------------------------------------|
| Credits Used Over Time by Account | lineChart     | `snowflake.org.credits.used` by `deployment.environment`            |
| Credits by Service Type           | barChart      | `snowflake.org.credits.used` summarized by `snowflake.service.type` |
| Total Credits by Account          | table         | compute + cloud_services + total credits summarized by account      |

### §4 Storage

| Tile                         | Visualization | Metric / Query                                                       |
|------------------------------|---------------|----------------------------------------------------------------------|
| Storage Over Time by Account | lineChart     | `snowflake.org.storage.bytes` (avg) by `deployment.environment`      |
| Storage by Type              | barChart      | `snowflake.org.storage.bytes` summarized by `snowflake.storage.type` |
| Total Storage by Account     | table         | `snowflake.org.storage.bytes` summarized by account (bytes unit)     |

### §5 Data Transfer

| Tile                          | Visualization | Metric / Query                                                   |
|-------------------------------|---------------|------------------------------------------------------------------|
| Transfer Over Time by Account | lineChart     | `snowflake.org.transfer.bytes` by `deployment.environment`       |
| Transfer by Region            | table         | `snowflake.org.transfer.bytes` by source/target cloud and region |

### §6 Billing & Contract Balance

| Tile                       | Visualization | Metric / Query                                                                                                                      |
|----------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Billing Amount by Service  | lineChart     | `snowflake.org.billing.amount` by service type and account                                                                          |
| Remaining Contract Balance | lineChart     | `capacity_balance`, `rollover_balance`, `free_usage_balance`, `on_demand_consumption`, `overage` (all `snowflake.org.billing.*`)    |

> **Note:** `avg()` is used for balance metrics because `REMAINING_BALANCE_DAILY` emits one row
> per organization per day — summing would inflate values.

## Planned Sections (Future Phases)

- **§1 Contract Capacity KPIs** (Phase B): Single-value tiles for total capacity used, remaining
  capacity, 30-day consumption, YoY burn rate, days to overage, and overage date. Requires
  billing context data from `org_billing_remaining_balance` and `org_billing_usage_in_currency`.
- **§3 USD Consumption** (Phase B): Consumption trends and totals in contract currency using
  `snowflake.org.billing.amount`.
- **§6 Department / BU View** (Phase C): Credits and consumption grouped by Business Unit using
  the `$bu_mapping` JSON variable for account-to-BU assignment.

## Default Timeframe

30 days (`now()-30d`). Auto-refresh is off.

## Metric Sources

All tiles use `timeseries` DQL against DSOA metric keys. No `fetch events` is used — the
`org_costs` plugin emits logs and metrics only.

| Context                         | Metrics                                                                                                                   |
|---------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| `org_costs_metering`            | `snowflake.org.credits.used`, `.compute`, `.cloud_services`, `.adjustment_cloud_services`                                 |
| `org_costs_storage`             | `snowflake.org.storage.bytes`                                                                                             |
| `org_costs_data_transfer`       | `snowflake.org.transfer.bytes`                                                                                            |
| `org_billing_usage_in_currency` | `snowflake.org.billing.amount`                                                                                            |
| `org_billing_remaining_balance` | `.capacity_balance`, `.rollover_balance`, `.free_usage_balance`, `.on_demand_consumption`, `.overage`                     |

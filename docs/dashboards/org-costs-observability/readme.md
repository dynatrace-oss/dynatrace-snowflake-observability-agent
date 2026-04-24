# Snowflake Consumption (Organization Level) Dashboard

Organization-wide Snowflake consumption monitoring across all accounts. Requires the `org_costs`
plugin to be enabled and the Snowflake account to have `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` granted.

## Prerequisites

- `org_costs` plugin enabled (`plugins.org_costs.is_enabled: true`)
- Snowflake account linked to an organization (ORGADMIN access or organization-linked account)
- `SNOWFLAKE.ORGANIZATION_USAGE_VIEWER` role granted to `DTAGENT_VIEWER` (handled during init)
- For §1 and §3 tiles: `org_billing_usage_in_currency` and `org_billing_remaining_balance` contexts
  must be collecting data (both are enabled by default when `org_costs` is enabled)

## Variables

| Variable       | Type  | Visible | Description                                                                       |
|----------------|-------|---------|-----------------------------------------------------------------------------------|
| `$Accounts`    | query | yes     | Multi-select filter for Snowflake account identifiers (`deployment.environment`)  |
| `$credit_rate` | text  | no      | Credit rate in USD (default: `3.00`) — reserved for Phase C BU cost calculations  |
| `$bu_mapping`  | text  | no      | JSON mapping of account names to Business Units — reserved for Phase C BU view    |

## Sections and Tiles

### §1 Contract Capacity KPIs

| Tile                                    | Visualization | Metric / Query                                                                                                    |
|-----------------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------|
| Capacity Used (USD)                     | singleValue   | `snowflake.org.billing.amount` — total sum over selected timeframe                                                |
| Remaining Capacity (USD)                | singleValue   | `capacity_balance` + `rollover_balance` — last known value                                                        |
| 30-Day Run Rate (USD)                   | singleValue   | `snowflake.org.billing.amount` — sum over last 30 days                                                            |
| YoY Burn Rate — Current vs Previous 30d | table         | Current 30d vs previous 30d USD spend with annualized run rate and % change                                       |
| Estimated Days to Overage               | singleValue   | Derived from 30-day balance burn rate: `balance_end / monthly_burn * 30`                                          |
| Projected Overage Date                  | table         | Estimated date when capacity + rollover balance reaches zero based on 30-day burn rate                            |

### §2 Credit Consumption

| Tile                              | Visualization | Metric / Query                                                      |
|-----------------------------------|---------------|---------------------------------------------------------------------|
| Credits Used Over Time by Account | lineChart     | `snowflake.org.credits.used` by `deployment.environment`            |
| Credits by Service Type           | barChart      | `snowflake.org.credits.used` summarized by `snowflake.service.type` |
| Total Credits by Account          | table         | compute + cloud_services + total credits summarized by account      |

### §3 USD Consumption

| Tile                     | Visualization | Metric / Query                                                                  |
|--------------------------|---------------|---------------------------------------------------------------------------------|
| USD Over Time by Account | lineChart     | `snowflake.org.billing.amount` by `deployment.environment`                      |
| USD by Service Type      | barChart      | `snowflake.org.billing.amount` summarized by `snowflake.service.type`           |
| Total USD by Account     | table         | `snowflake.org.billing.amount` total per account (uses `arraySum` for accuracy) |

> When billing contexts are disabled, estimated USD = credits × `$credit_rate`
> (hidden variable, default 3.00 USD/credit).

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

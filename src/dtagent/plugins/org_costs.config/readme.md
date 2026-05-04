The `org_costs` plugin delivers cross-account FinOps telemetry from `SNOWFLAKE.ORGANIZATION_USAGE` views. It provides organization-wide credit consumption, storage usage, data transfer costs, USD billing, and contract balance data — enabling multi-account cost visibility in Dynatrace.

## Prerequisites

Access to `SNOWFLAKE.ORGANIZATION_USAGE` views requires one of the following grants. This plugin is **disabled by default** (`is_disabled: true`) and must be explicitly enabled after completing the prerequisite step.

### Option A — Database role (recommended)

```sql
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.ORGANIZATION_USAGE_VIEWER TO ROLE DTAGENT_VIEWER;
```

### Option B — ORGADMIN role (legacy fallback for older tenants)

```sql
USE ROLE ACCOUNTADMIN;
GRANT ROLE ORGADMIN TO ROLE DTAGENT_OWNER;
```

## Contexts

| Context | Source view | Telemetry |
| --- | --- | --- |
| `org_costs_metering` | `ORGANIZATION_USAGE.METERING_DAILY_HISTORY` | metrics, logs |
| `org_costs_storage` | `ORGANIZATION_USAGE.STORAGE_DAILY_HISTORY` | metrics, logs |
| `org_costs_data_transfer` | `ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY` | metrics, logs |
| `org_billing_usage_in_currency` | `ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY` | metrics, logs |
| `org_billing_remaining_balance` | `ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY` | metrics, logs |

## Schedule

Runs every 6 hours (`USING CRON 0 */6 * * * UTC`). Source data has approximately 2 hours of latency; daily-granularity views update once per day.

## Metrics emitted

### org_costs_metering

| Metric | Unit | Description |
| --- | --- | --- |
| `snowflake.org.credits.used` | credits | Total credits used by account per day |
| `snowflake.org.credits.compute` | credits | Compute credits used per day |
| `snowflake.org.credits.cloud_services` | credits | Cloud services credits used per day |
| `snowflake.org.credits.adjustment_cloud_services` | credits | Cloud services credit adjustment (10% rule) |

### org_costs_storage

| Metric | Unit | Description |
| --- | --- | --- |
| `snowflake.org.storage.bytes` | Byte | Storage bytes used per storage type per day |

### org_costs_data_transfer

| Metric | Unit | Description |
| --- | --- | --- |
| `snowflake.org.transfer.bytes` | Byte | Bytes transferred between clouds/regions per day |

### org_billing_usage_in_currency

| Metric | Unit | Description |
| --- | --- | --- |
| `snowflake.org.billing.amount` | currency | Billing amount in currency per service type per day |

### org_billing_remaining_balance

| Metric | Unit | Description |
| --- | --- | --- |
| `snowflake.org.billing.capacity_balance` | currency | Remaining contracted capacity balance |
| `snowflake.org.billing.rollover_balance` | currency | Remaining rollover balance |
| `snowflake.org.billing.free_usage_balance` | currency | Remaining free usage balance |
| `snowflake.org.billing.on_demand_consumption` | currency | On-demand consumption charged against contract |
| `snowflake.org.billing.overage` | currency | Overage charged beyond contracted capacity |

## Enablement

1. Complete the prerequisite grant (Option A or B above).
1. Set `plugins.org_costs.is_disabled: false` in your configuration.
1. Deploy: `./scripts/deploy/deploy.sh <env> --scope=plugins,config --options=skip_confirm`

## Troubleshooting

- **No data for a new account:** Organization-level views may not reflect new accounts for up to 24 hours after creation.
- **Empty results:** Verify the prerequisite grant was applied and the plugin is enabled.
- **Stale data:** Daily-granularity views update once per day; data may appear up to 26 hours old (2h Snowflake latency + 6h collection cadence + daily boundary).

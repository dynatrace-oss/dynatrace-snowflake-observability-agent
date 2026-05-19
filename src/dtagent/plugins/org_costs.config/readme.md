The `org_costs` plugin delivers cross-account FinOps telemetry from `SNOWFLAKE.ORGANIZATION_USAGE` views. It provides organization-wide credit consumption, storage usage, data transfer costs, USD billing, and contract balance data — enabling multi-account cost visibility in Dynatrace.

> [!WARNING] IMPORTANT
> This plugin is **disabled by default** (`is_disabled: true`). It requires a Snowflake organization account.
> Run `--scope=init` with ACCOUNTADMIN rights before enabling.

## Contexts

| Context                         | Source view                                      | Telemetry     |
|---------------------------------|--------------------------------------------------|---------------|
| `org_costs_metering`            | `ORGANIZATION_USAGE.METERING_DAILY_HISTORY`      | metrics, logs |
| `org_costs_storage`             | `ORGANIZATION_USAGE.STORAGE_DAILY_HISTORY`       | metrics, logs |
| `org_costs_data_transfer`       | `ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY` | metrics, logs |
| `org_billing_usage_in_currency` | `ORGANIZATION_USAGE.USAGE_IN_CURRENCY_DAILY`     | metrics, logs |
| `org_billing_remaining_balance` | `ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY`     | metrics, logs |

## Schedule

Runs every 6 hours (`USING CRON 0 */6 * * * UTC`). Source data has approximately 2 hours of latency; daily-granularity views update once per day.

## Enablement

1. Set `plugins.org_costs.is_disabled: false` in your configuration.
1. Deploy: `./scripts/deploy/deploy.sh <env> --scope=plugins,config --options=skip_confirm`

## Troubleshooting

- **No data for a new account:** Organization-level views may not reflect new accounts for up to 24 hours after creation.
- **Empty results:** Verify the prerequisite grant was applied (`--scope=init`) and the plugin is enabled.
- **Stale data:** Daily-granularity views update once per day; data may appear up to 26 hours old (2h Snowflake latency + 6h collection cadence + daily boundary).

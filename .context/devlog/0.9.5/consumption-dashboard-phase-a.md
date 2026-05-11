# [Unreleased] — Snowflake Consumption Dashboard Phase A

## Dashboard Overhaul: Snowflake Consumption (Organization Level)

**Scope**: Phase A of the org-level consumption dashboard. Extends `docs/dashboards/org-costs-observability/`
in place (preserves deployed UUID `6881ff48-0945-4e94-94af-2e4bb338724e`). Bumps version to 2.

**Changes**:

- **Title** updated from `Org-Level Costs Observability` to `Snowflake Consumption (Organization Level)`.
- **Variables** replaced: `$Accounts` (query, multi-select, uses `fetch logs` with `dsoa.run.plugin == "org_costs"`
  to avoid empty-variable risk); `$credit_rate` (hidden text, default `"3.00"`, reserved for Phase B);
  `$bu_mapping` (hidden text, default `"{}"`, reserved for Phase C BU grouping).
- **§2 Credit Consumption** (3 tiles): line chart of credits over time by account; bar chart of credits
  by service type; table of compute + cloud_services + total credits by account.
- **§4 Storage** (3 tiles): line chart of storage bytes over time by account; bar chart by storage type;
  table of total bytes by account. All byte fields have `unitsOverrides` with `unitCategory: data`.
- **§5 Data Transfer** (2 tiles): line chart of transfer bytes over time; table by source/target cloud
  and region. Byte fields have `unitsOverrides`.
- **§6 Billing & Contract Balance** (2 tiles): billing amount line chart; Remaining Contract Balance
  tile **fixed** — old query used non-existent `snowflake.org.balance.*.remaining` metric keys.
  New query uses real keys: `snowflake.org.billing.capacity_balance`, `rollover_balance`,
  `free_usage_balance`, `on_demand_consumption`, `overage`. Uses `avg()` (not `sum()`) because
  `REMAINING_BALANCE_DAILY` emits one row per org per day.
- **`instruments-def.yml`** updated: added `snowflake.storage.type` as a declared dimension for
  `org_costs_storage` context (was emitted by the SQL view but not declared in the semantic dictionary).
- **`readme.md`** updated: new title, 3-variable table, full Phase-A tile inventory, Phase B/C roadmap notes.
- **`docs/dashboards/README.md`** updated: entry renamed and description expanded.

**Metric-name bug root cause**: The original dashboard was authored before the `org_billing_remaining_balance`
context was finalized. The metric keys `snowflake.org.balance.*.remaining` were placeholder names that
never matched the emitted keys. The correct keys are in `instruments-def.yml` under `org_billing_remaining_balance`.

**Phase plan**:

- Phase A (this change): §2 Credits, §4 Storage, §5 Data Transfer, §6 Billing/Balance fix.
- Phase B (future): §1 Contract Capacity KPIs (single-value tiles for capacity used, remaining, burn rate,
  days to overage, overage date) and §3 USD Consumption. Requires billing context data.
- Phase C (future): §6 Department/BU View using `$bu_mapping` JSON variable for account-to-BU grouping.

# [0.9.5] — org_costs Plugin: Organization-Level Costs and Usage

## org_costs Plugin — Full Implementation

**Scope**: New `org_costs` plugin collecting organization-level cost and usage metrics from
`SNOWFLAKE.ORGANIZATION_USAGE`. Five contexts, disabled by default, 6-hour cron schedule.

**Architecture**:

- **`src/dtagent/plugins/org_costs.py`**: Multi-context plugin following the `warehouse_usage`
  pattern. Registers five contexts via `process()` dispatching to private per-context methods.
- **Five views** (`051`–`055`):
  - `V_ORG_METERING_DAILY` — credit consumption by service type and service name
  - `V_ORG_STORAGE_DAILY` — storage bytes by storage type and account locator
  - `V_ORG_DATA_TRANSFER_DAILY` — data transfer bytes by cloud, region, and transfer type
  - `V_ORG_BILLING_USAGE_IN_CURRENCY` — billed amounts in contract currency by account and service
  - `V_ORG_BILLING_REMAINING_BALANCE` — five balance categories (free usage, capacity, on-demand,
    rollover, total)
- **Metrics** (10 total): `snowflake.org.credits.used`, `snowflake.org.credits.cloud_services`,
  `snowflake.org.storage.bytes`, `snowflake.org.transfer.bytes`, `snowflake.org.billing.amount`,
  and five `snowflake.org.balance.*.remaining` metrics.
- **Admin proc** (`admin/050_p_check_organization_usage_access.sql`): Diagnostic stored procedure
  `DTAGENT_DB.APP.P_CHECK_ORGANIZATION_USAGE_ACCESS()` that can be called manually after
  deployment to verify ORGANIZATION_USAGE access. Returns a success or failure message.
- **Deploy advisory** (`scripts/deploy/lib.sh::check_org_costs_access()`): Non-blocking warning
  emitted during `prepare_deploy_script.sh` when `org_costs` is in scope and not excluded. Reminds
  operators to verify ORGADMIN access before enabling the plugin.

**Test coverage**: Five tests in `test/plugins/test_org_costs.py` using mock NDJSON fixtures.
Each test exercises multiple `disabled_telemetry` combos and validates metric counts against
golden files in `test/test_results/`.

**Dashboards**:

- New **`Org-Level Costs Observability`** dashboard (`docs/dashboards/org-costs-observability/`):
  9 tiles covering all five metric groups. UUID `6881ff48-0945-4e94-94af-2e4bb338724e`.
- Extended **`Costs Monitoring`** dashboard with org-level credits overview section (tiles 22/23,
  version bumped to 21).

**Workflow**: New **`Org Contract Balance Warning`** (`docs/workflows/org-contract-balance-warning/`):
6-hour schedule, queries five `snowflake.org.billing.*` metrics (`capacity_balance`,
`rollover_balance`, `free_usage_balance`, `on_demand_consumption`, `overage`) and logs alert if any
drops below configurable threshold.

**Doc updates**: `docs/USECASES.md` extended with "Costs — Tier 0 — Organization-Level FinOps"
section (3 new use cases). `docs/dashboards/README.md` and `docs/workflows/README.md` updated.

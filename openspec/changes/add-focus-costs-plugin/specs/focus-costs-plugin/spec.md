## ADDED Requirements

### Requirement: Step Zero `SEND_TELEMETRY` Validation for `real.costs` BizEvents
The system SHALL support sending `cost.real.spend` business events matching the `real.costs` Semantic Dictionary model directly via `DTAGENT_DB.APP.SEND_TELEMETRY` (with `auto_mode=false`, `biz_events=true`) using either a synthetic payload object or a live query against `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3`.

#### Scenario: Ad-hoc single-row synthetic `SEND_TELEMETRY` call

- **WHEN** an operator calls `DTAGENT_DB.APP.SEND_TELEMETRY` with an `OBJECT_CONSTRUCT` containing `event.type = 'cost.real.spend'`, `focus.*` attributes, and `snowflake.x_*` attributes, and `params = OBJECT_CONSTRUCT('context', 'focus_costs', 'auto_mode', false, 'logs', false, 'metrics', false, 'events', false, 'biz_events', true)`
- **THEN** Dynatrace receives a CloudEvent at `/api/v2/bizevents/ingest` with `type = "cost.real.spend"`, `id = <event.id>`, and all `focus.*` and `snowflake.x_*` attributes preserved with their native JSON types (`double` for costs/quantities, `string` for identifiers and ISO-8601 UTC timestamps).

#### Scenario: Live sample emission via `P_SEND_FOCUS_COSTS_SAMPLE`

- **WHEN** an operator calls `DTAGENT_DB.APP.P_SEND_FOCUS_COSTS_SAMPLE(10, 72)` on an org-enabled Snowflake account
- **THEN** up to 10 rows from `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` updated within the last 72 hours are queried using double-quoted column identifiers and sent as `cost.real.spend` bizevents via `SEND_TELEMETRY`.

### Requirement: Snowflake Privilege Provisioning for Standalone and Full Deployments
The `focus_costs` plugin SHALL document in `bom.yml` and provision in `init/` all Snowflake privileges required to query `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` even when `focus_costs` is the only enabled plugin.

#### Scenario: Standalone plugin initialization (`scope=init`)

- **WHEN** `deploy.sh` runs with `--scope=init` and `focus_costs` enabled
- **THEN** Core Init (`001_viewer_role.sql`) grants `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE DTAGENT_VIEWER` AND `focus_costs.sql/init/009_focus_costs_init.sql` grants `DATABASE ROLE SNOWFLAKE.ORGANIZATION_BILLING_VIEWER TO ROLE DTAGENT_VIEWER` (falling back to `GRANT ROLE ORGADMIN TO ROLE DTAGENT_VIEWER` if the database role grant raises a statement error).

#### Scenario: Post-deployment access verification

- **WHEN** an operator calls `DTAGENT_DB.APP.P_CHECK_BILLING_ACCESS()`
- **THEN** the procedure probes `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` and returns `'OK: SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3 is accessible — focus_costs plugin is ready.'` or a descriptive `WARNING:` message if the account is not org-enabled or lacks `SNOWFLAKE.ORGANIZATION_BILLING_VIEWER`.

### Requirement: Case-Sensitive Querying and Mapping of `FOCUS_COST_USAGE_V1_3`
The view `DTAGENT_DB.APP.V_FOCUS_COST_USAGE_INSTRUMENTED` SHALL enclose all source column references from `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` in double quotes (`"..."`) to preserve MixedCase identifiers and map all 35 FOCUS v1.3 standard columns plus 5 Snowflake `x_*` extension columns to the `real.costs` payload structure.

#### Scenario: Incremental watermark filtering via `"x_UpdatedAt"`

- **WHEN** `V_FOCUS_COST_USAGE_INSTRUMENTED` is queried during a `focus_costs` plugin run
- **THEN** only rows where `"x_UpdatedAt"` is greater than `GREATEST(DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('focus_costs'), DATEADD(HOUR, -1 * DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.focus_costs.lookback_hours', 72), CURRENT_TIMESTAMP()))` are returned, capturing both new daily charges and late-arriving mid-month updates or `"ChargeClass" = 'Correction'` rows.

#### Scenario: Deterministic `event.id` generation

- **WHEN** a row is mapped by `V_FOCUS_COST_USAGE_INSTRUMENTED`
- **THEN** `event.id` is computed as a deterministic SHA-256 hex digest over the row's natural grain (`BillingAccountId`, `SubAccountId`, `ChargePeriodStart`, `ChargePeriodEnd`, `ServiceCategory`, `ServiceName`, `ChargeCategory`, `ChargeClass`, `ChargeFrequency`, `ChargeDescription`, `PricingCategory`, `RegionId`, `x_ServiceLevel`, `ContractApplied.x_BalanceSource`) and propagated to the CloudEvents `id` header.

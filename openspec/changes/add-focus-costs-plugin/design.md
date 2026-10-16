## Context

1. **Source View (`SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3`):**
   - Exposes daily charge line items across all sub-accounts in a Snowflake organization following FOCUS v1.3.
   - All column names in Snowflake are defined with case-sensitive MixedCase identifiers (`"BillingPeriodStart"`, `"BilledCost"`, `"ContractApplied"`, `"x_UpdatedAt"`, etc.). Unquoted SQL references fail because Snowflake folds unquoted identifiers to UPPERCASE.
   - Refreshes hourly, but latent usage can take up to 72 hours to appear, and rows for the current open month can be updated or supplemented with `"ChargeClass" = 'Correction'` rows until month close. Every update bumps `"x_UpdatedAt"`.
2. **Target Schema (`.context/semantic-dictionary/source/model/business_analytics/real.costs.yaml`):**
   - Grail table: `bizevents` (`data_object: bizevents`), ingested via `/api/v2/bizevents/ingest` (`application/cloudevent-batch+json`).
   - Required filter discriminator for the Dynatrace Costs App: `event.type == "cost.real.spend"`.
   - Standard FOCUS columns use the `focus.<ColumnName>` prefix (33 of 35 columns already exist in `model_group_business_analytics.yaml`; `focus.HostProviderName` and `focus.ContractApplied` are new in FOCUS 1.3).
   - Vendor-specific extension columns use `<vendor>.x_<ColumnName>` (`aws.x_*`, `azure.x_*`); Snowflake's 5 extension fields map to `snowflake.x_*`.

## Goals / Non-Goals

**Goals:**

- Provide an immediate **Step Zero** `SEND_TELEMETRY` SQL call and wrapper procedure `P_SEND_FOCUS_COSTS_SAMPLE` to validate the `real.costs` event shape in Dynatrace Costs App before full plugin rollout.
- Deliver a complete `focus_costs` DSOA plugin (SQL view, init script, diagnostic check procedure, task, config, BOM, `instruments-def.yml`, tests, docs).
- Add first-class `biz_events` support to `Plugin._log_entries()`, `BizEvents._pack_event_data()`, `util.py` (`Decimal` handling), and `test/_utils.py` (`execute_telemetry_test`).
- Ensure accurate Semantic Dictionary provenance (`__semdict: ref` for existing `real.costs` fields, `__semdict: new` for new `snowflake.x_*` and FOCUS 1.3 fields) and consult `@information-architect` during implementation.

**Non-Goals:**

- Modifying the Dynatrace Costs App UI code itself (lives in a separate repository; Step Zero validates how the app ingests the payload).
- Replacing `org_costs` (which queries `SNOWFLAKE.ORGANIZATION_USAGE` for credit/storage/transfer/balance metrics); `focus_costs` specifically targets the FOCUS v1.3 billing view for `bizevents` FinOps ingestion.

## Decisions

### Decision 1: Step Zero `SEND_TELEMETRY` Call & Wrapper Procedure
Before deploying the full plugin, we can test the exact `real.costs` payload shape using the already-deployed `DTAGENT_DB.APP.SEND_TELEMETRY(sources variant, params object)` procedure (`src/dtagent/connector.py`).
When called with:

```sql
OBJECT_CONSTRUCT(
    'context', 'focus_costs',
    'auto_mode', FALSE,
    'logs', FALSE,
    'metrics', FALSE,
    'events', FALSE,
    'biz_events', TRUE
)
```

`TelemetrySender.send_data()` routes `sources` (which can be a single `OBJECT_CONSTRUCT`, an `ARRAY_CONSTRUCT`, or a `SELECT` query string) through `self._biz_events.report_via_api(..., is_data_structured=False)`.
Because `BizEvents._pack_event_data()` sets `"type": str(event_data.get("event.type", event_type))`, including `'event.type', 'cost.real.spend'` in the source object sets both the CloudEvents envelope `"type"` and `data["event.type"]` to `"cost.real.spend"`.
Using `OBJECT_CONSTRUCT(...)` in SQL with explicit `::FLOAT` casts for `NUMBER(38,9)` columns also avoids `decimal.Decimal` serialization issues and automatically omits SQL `NULL` values even on an unpatched agent.

### Decision 2: Privilege Model (Core Init vs Plugin Init)

- **Core Init (`src/dtagent.sql/init/001_viewer_role.sql`):** Already grants `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE DTAGENT_VIEWER;`.
- **Snowflake's `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` Requirement:** Requires an org-enabled account and the `SNOWFLAKE.ORGANIZATION_BILLING_VIEWER` database role.
- **Why Plugin Init (`src/dtagent/plugins/focus_costs.sql/init/009_focus_costs_init.sql`) is also included:**
  1. When `deploy.sh` runs `--scope=init` (even if **only** `focus_costs` is enabled), `build/00_init.sql` executes `001_viewer_role.sql` followed by `--%PLUGIN:focus_costs:` -> `009_focus_costs_init.sql`.
  2. Explicitly running `GRANT DATABASE ROLE SNOWFLAKE.ORGANIZATION_BILLING_VIEWER TO ROLE DTAGENT_VIEWER;` (wrapped in `EXECUTE IMMEDIATE $$ BEGIN ... EXCEPTION WHEN STATEMENT_ERROR THEN GRANT ROLE ORGADMIN TO ROLE DTAGENT_VIEWER; END; $$`, mirroring `org_costs`) guarantees least-privilege access on accounts that scope `SNOWFLAKE` access by database role rather than broad `IMPORTED PRIVILEGES`, while never failing `init` if an account does not yet have the database role.
  3. `bom.yml` lists both `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` (`SELECT`) and `SNOWFLAKE.ORGANIZATION_BILLING_VIEWER` (`DATABASE ROLE` granted to `DTAGENT_VIEWER`).

### Decision 3: Complete Column Mapping (`SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` -> `real.costs` BizEvent)
All 35 FOCUS standard columns and 5 Snowflake `x_` extension columns are mapped as follows (with all Snowflake column identifiers enclosed in `""`):

| Snowflake Column (Double-Quoted)                | Snowflake Type | SQL Transformation                                                                        | Target Dynatrace Field                  | SD Type  | SD Provenance                              |
| ----------------------------------------------- | -------------- | ----------------------------------------------------------------------------------------- | --------------------------------------- | -------- | ------------------------------------------ |
| *(constant)*                                    | —              | `'cost.real.spend'`                                                                       | `event.type`                            | `string` | `ref` (`real.costs`)                       |
| *(constant)*                                    | —              | `'dynatrace.snowagent'`                                                                   | `event.provider`                        | `string` | `ref` (`real.costs`)                       |
| *(composite hash)*                              | —              | `SHA2(CONCAT_WS('\| ', ...), 256)`                                                        | `event.id`                              | `string` | `ref` (`real.costs`)                       |
| `"ChargePeriodStart"`                           | `TIMESTAMP_TZ` | `TO_VARCHAR(EXTRACT(EPOCH_NANOSECOND FROM "ChargePeriodStart"))`                          | `event.start`                           | `string` | `ref` (`real.costs`)                       |
| `"ChargePeriodEnd"`                             | `TIMESTAMP_TZ` | `TO_VARCHAR(EXTRACT(EPOCH_NANOSECOND FROM "ChargePeriodEnd"))`                            | `event.end`                             | `string` | `ref` (`real.costs`)                       |
| *(constant)*                                    | —              | `'snowflake'`                                                                             | `cloud.provider`                        | `string` | `ref` (`real.costs`)                       |
| *(constant)*                                    | —              | `'daily'`                                                                                 | `price.total.granularity`               | `string` | `ref` (`real.costs`)                       |
| *(constant)*                                    | —              | `'1.3'`                                                                                   | `focus.spec.version`                    | `string` | `ref` (`real.costs`)                       |
| `"BillingPeriodStart"`                          | `TIMESTAMP_TZ` | `TO_VARCHAR(CONVERT_TIMEZONE('UTC', "BillingPeriodStart"), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')` | `focus.BillingPeriodStart`              | `string` | `ref` (`real.costs`)                       |
| `"BillingPeriodEnd"`                            | `TIMESTAMP_TZ` | `TO_VARCHAR(CONVERT_TIMEZONE('UTC', "BillingPeriodEnd"), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')`   | `focus.BillingPeriodEnd`                | `string` | `ref` (`real.costs`)                       |
| `"ChargePeriodStart"`                           | `TIMESTAMP_TZ` | `TO_VARCHAR(CONVERT_TIMEZONE('UTC', "ChargePeriodStart"), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')`  | `focus.ChargePeriodStart`               | `string` | `ref` (`real.costs`)                       |
| `"ChargePeriodEnd"`                             | `TIMESTAMP_TZ` | `TO_VARCHAR(CONVERT_TIMEZONE('UTC', "ChargePeriodEnd"), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')`    | `focus.ChargePeriodEnd`                 | `string` | `ref` (`real.costs`)                       |
| `"BillingAccountName"`                          | `TEXT`         | `"BillingAccountName"`                                                                    | `focus.BillingAccountName`              | `string` | `ref` (`real.costs`)                       |
| `"BillingAccountId"`                            | `TEXT`         | `"BillingAccountId"`                                                                      | `focus.BillingAccountId`                | `string` | `ref` (`real.costs`)                       |
| `"SubAccountId"`                                | `TEXT`         | `"SubAccountId"`                                                                          | `focus.SubAccountId`                    | `string` | `ref` (`real.costs`)                       |
| `"SubAccountName"`                              | `TEXT`         | `"SubAccountName"`                                                                        | `focus.SubAccountName`                  | `string` | `ref` (`real.costs`)                       |
| `"SubAccountType"`                              | `TEXT`         | `"SubAccountType"`                                                                        | `focus.SubAccountType`                  | `string` | `ref` (`real.costs`)                       |
| `"ChargeCategory"`                              | `TEXT`         | `"ChargeCategory"`                                                                        | `focus.ChargeCategory`                  | `string` | `ref` (`real.costs`)                       |
| `"ChargeClass"`                                 | `TEXT`         | `"ChargeClass"`                                                                           | `focus.ChargeClass`                     | `string` | `ref` (`real.costs`)                       |
| `"ChargeFrequency"`                             | `TEXT`         | `"ChargeFrequency"`                                                                       | `focus.ChargeFrequency`                 | `string` | `ref` (`real.costs`)                       |
| `"ServiceCategory"`                             | `TEXT`         | `"ServiceCategory"`                                                                       | `focus.ServiceCategory`                 | `string` | `ref` (`real.costs`)                       |
| `"ServiceName"`                                 | `TEXT`         | `"ServiceName"`                                                                           | `focus.ServiceName`                     | `string` | `ref` (`real.costs`)                       |
| `"ChargeDescription"`                           | `TEXT`         | `"ChargeDescription"`                                                                     | `focus.ChargeDescription`               | `string` | `ref` (`real.costs`)                       |
| `"ConsumedQuantity"`                            | `NUMBER(38,9)` | `"ConsumedQuantity"::FLOAT`                                                               | `focus.ConsumedQuantity`                | `double` | `ref` (`real.costs`)                       |
| `"ConsumedUnit"`                                | `TEXT`         | `"ConsumedUnit"`                                                                          | `focus.ConsumedUnit`                    | `string` | `ref` (`real.costs`)                       |
| `"PricingQuantity"`                             | `NUMBER(38,9)` | `"PricingQuantity"::FLOAT`                                                                | `focus.PricingQuantity`                 | `double` | `ref` (`real.costs`)                       |
| `"PricingUnit"`                                 | `TEXT`         | `"PricingUnit"`                                                                           | `focus.PricingUnit`                     | `string` | `ref` (`real.costs`)                       |
| `"ListUnitPrice"`                               | `NUMBER(38,9)` | `"ListUnitPrice"::FLOAT`                                                                  | `focus.ListUnitPrice`                   | `double` | `ref` (`real.costs`)                       |
| `"ListCost"`                                    | `NUMBER(38,9)` | `"ListCost"::FLOAT`                                                                       | `focus.ListCost`                        | `double` | `ref` (`real.costs`)                       |
| `"ContractedUnitPrice"`                         | `NUMBER(38,9)` | `"ContractedUnitPrice"::FLOAT`                                                            | `focus.ContractedUnitPrice`             | `double` | `ref` (`real.costs`)                       |
| `"ContractedCost"`                              | `NUMBER(38,9)` | `"ContractedCost"::FLOAT`                                                                 | `focus.ContractedCost`                  | `double` | `ref` (`real.costs`)                       |
| `"EffectiveCost"`                               | `NUMBER(38,9)` | `"EffectiveCost"::FLOAT`                                                                  | `focus.EffectiveCost`                   | `double` | `ref` (`real.costs`)                       |
| `"BilledCost"`                                  | `NUMBER(38,9)` | `"BilledCost"::FLOAT`                                                                     | `focus.BilledCost`                      | `double` | `ref` (`real.costs`)                       |
| `"BillingCurrency"`                             | `TEXT`         | `"BillingCurrency"`                                                                       | `focus.BillingCurrency`                 | `string` | `ref` (`real.costs`)                       |
| `"PricingCategory"`                             | `TEXT`         | `"PricingCategory"`                                                                       | `focus.PricingCategory`                 | `string` | `ref` (`real.costs`)                       |
| `"CapacityReservationId"`                       | `NUMBER`       | `"CapacityReservationId"::VARCHAR`                                                        | `focus.CapacityReservationId`           | `string` | `ref` (`real.costs`)                       |
| `"CapacityReservationStatus"`                   | `TEXT`         | `"CapacityReservationStatus"`                                                             | `focus.CapacityReservationStatus`       | `string` | `ref` (`real.costs`)                       |
| `"RegionId"`                                    | `TEXT`         | `"RegionId"`                                                                              | `focus.RegionId`                        | `string` | `ref` (`real.costs`)                       |
| `"RegionName"`                                  | `TEXT`         | `"RegionName"`                                                                            | `focus.RegionName`                      | `string` | `ref` (`real.costs`)                       |
| `"HostProviderName"`                            | `TEXT`         | `"HostProviderName"`                                                                      | `focus.HostProviderName`                | `string` | `new` (FOCUS 1.3)                          |
| `"InvoiceIssuerName"`                           | `TEXT`         | `"InvoiceIssuerName"`                                                                     | `focus.InvoiceIssuerName`               | `string` | `ref` (`real.costs`)                       |
| `"InvoiceIssuerName"`                           | `TEXT`         | `COALESCE("InvoiceIssuerName", 'Snowflake')`                                              | `focus.ProviderName`                    | `string` | `ref` (`real.costs`, FOCUS 1.0–1.2 compat) |
| `"InvoiceId"`                                   | `TEXT`         | `"InvoiceId"`                                                                             | `focus.InvoiceId`                       | `string` | `ref` (`real.costs`)                       |
| `"ContractApplied"`                             | `OBJECT`       | `TO_JSON("ContractApplied")`                                                              | `focus.ContractApplied`                 | `string` | `new` (FOCUS 1.3, serialized JSON)         |
| `"x_UpdatedAt"`                                 | `TIMESTAMP_TZ` | `TO_VARCHAR(CONVERT_TIMEZONE('UTC', "x_UpdatedAt"), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')`        | `snowflake.x_UpdatedAt`                 | `string` | `new` (Snowflake `x_*`)                    |
| `"x_OrganizationName"`                          | `TEXT`         | `"x_OrganizationName"`                                                                    | `snowflake.x_OrganizationName`          | `string` | `new` (Snowflake `x_*`)                    |
| `"x_ServiceLevel"`                              | `TEXT`         | `"x_ServiceLevel"`                                                                        | `snowflake.x_ServiceLevel`              | `string` | `new` (Snowflake `x_*`)                    |
| `"ContractApplied".x_BalanceSource`             | `TEXT`         | `"ContractApplied":x_BalanceSource::VARCHAR`                                              | `snowflake.x_BalanceSource`             | `string` | `new` (Snowflake `x_*`)                    |
| `"ContractApplied".x_ContractCommitCostBalance` | `NUMBER`       | `"ContractApplied":x_ContractCommitCostBalance::FLOAT`                                    | `snowflake.x_ContractCommitCostBalance` | `double` | `new` (Snowflake `x_*`)                    |

### Decision 4: Provider Discrimination (`cloud.provider` vs `focus.HostProviderName`)

- In `real.costs.yaml`, `cloud.provider` is used to filter by billing vendor (`aws`, `azure`, `gcp`). In `source/fields/resource_fields/cloud.yaml`, `cloud.provider` is an open enum (`allow_custom_values: true`).
- Setting `cloud.provider = 'snowflake'` (and `focus.ProviderName = 'Snowflake'`, `focus.InvoiceIssuerName = 'Snowflake'`) while mapping `"HostProviderName"` (`'Aws'`, `'Azure'`, `'Gcp'`) to `focus.HostProviderName` avoids conflating Snowflake SaaS spend with underlying AWS/Azure/GCP infrastructure bills.

### Decision 5: DSOA SDK & Tooling Changes

1. **`BizEvents._pack_event_data()` (`src/dtagent/otel/events/bizevents.py`):**
   - Change `"id": str(uuid.uuid4().hex)` to `"id": str(event_data.get("event.id") or event_data.get("id") or uuid.uuid4().hex)` so deterministic `event.id` from the view is used as the CloudEvents `id`.
   - Clean `event_data` via `_cleanup_dict` so `None` values are stripped before packing.
2. **`_cleanup_data()` & `_cleanup_dict()` (`src/dtagent/util.py`):**
   - Add `decimal.Decimal` conversion (`int(v)` when integral/zero-scale, else `float(v)`) so Snowpark `Decimal` objects never cause `TypeError: Object of type Decimal is not JSON serializable` in `json.dumps()`.
3. **`Plugin._log_entries()` (`src/dtagent/plugins/__init__.py`):**
   - Add `self._report_via_bizevents()` (mirroring `self._report_via_davis_events()` at line 494 of `src/dtagent/plugins/__init__.py`) and update `_log_entries()` so that when `f_report_event == self._report_via_bizevents`, it checks `not getattr(self._bizevents, "NOT_ENABLED", False)` (instead of `self._events`), flushes `self._bizevents.flush_events()` on batch boundaries and loop completion, and records `entries_dict["biz_events"] = processed_events_cnt` with zero breaking changes to `_log_entries()`'s 4-tuple return signature.
4. **Test Harness (`test/_utils.py`):**
   - In `execute_telemetry_test()`, include `"biz_events"` in the `for telemetry_type in ("spans", "logs", "metrics", "events", "biz_events"):` loop, include `biz_events_expected` in `entries_expected`, and assert `results[test_name][RUN_RESULTS_KEY][plugin_key].get("biz_events", 0) == biz_events_expected` when `"biz_events"` is specified in `base_count[plugin_key]`.

## Risks / Trade-offs

- **[Risk] Snowflake `FOCUS_COST_USAGE_V1_3` latency (up to 72h) and mid-month updates** → **Mitigation:** Default `plugins.focus_costs.lookback_hours` to `72` (configurable) combined with `F_LAST_PROCESSED_TS('focus_costs')` on `"x_UpdatedAt"`, plus deterministic `event.id` SHA-256 hashing so updated rows carry a predictable identifier.
- **[Risk] Semantic Dictionary ownership of `focus.*` vs `snowflake.x_*`** → **Mitigation:** Mark the 33 existing `focus.*` fields + envelope fields as `__semdict: ref` (referencing `model/business_analytics/real.costs.yaml`), and consult `@information-architect` during implementation on whether the 5 `snowflake.x_*` fields and 2 FOCUS 1.3 fields (`focus.HostProviderName`, `focus.ContractApplied`) should be added to `model_group_business_analytics.yaml` + `real.costs.yaml` or `fields/signal_fields/snowflake.yaml`.

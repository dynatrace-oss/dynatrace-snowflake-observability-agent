## Why

Dynatrace's Costs App ingests FinOps Open Cost and Usage Specification (FOCUS) billing line items as Grail business events (`data_object: bizevents`, `event.type == "cost.real.spend"`), defined in the Dynatrace Semantic Dictionary under `model/business_analytics/real.costs.yaml`. Snowflake now exposes `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` (FOCUS v1.3), providing daily charge line items across all sub-accounts in a Snowflake organization (35 standard FOCUS columns + 5 Snowflake `x_*` extension columns); adding a DSOA plugin (`focus_costs`) that delivers this view as `cost.real.spend` bizevents enables Snowflake spend to be analyzed alongside hyperscaler spend in the Dynatrace Costs App.

## What Changes

- **Step Zero (`SEND_TELEMETRY` prototype & helper procedure):**
  - Provide ready-to-run `CALL DTAGENT_DB.APP.SEND_TELEMETRY(...)` examples (synthetic 1-row test and live query) and a helper procedure `DTAGENT_DB.APP.P_SEND_FOCUS_COSTS_SAMPLE(INT, INT)` to validate the `real.costs` bizevent shape in Dynatrace before full plugin rollout.
- **DSOA Core SDK & Test Harness Enhancements for BizEvents Plugins:**
  - `src/dtagent/otel/events/bizevents.py`: Preserve caller-supplied `event.id` / `id` in the CloudEvents top-level `id` attribute (`str(event_data.get("event.id") or event_data.get("id") or uuid.uuid4().hex)`) for deterministic deduplication, and strip `None`/empty attributes via `_cleanup_dict`.
  - `src/dtagent/util.py`: Convert `decimal.Decimal` values to `int` (when integral/zero-scale) or `float` inside `_cleanup_data()` and `_cleanup_dict()` so Snowflake `NUMBER(38,9)` columns never fail `json.dumps()` or serialize as strings.
  - `src/dtagent/plugins/__init__.py`: Add `_report_via_bizevents()` and first-class `biz_events` gating, periodic/final `self._bizevents.flush_events()`, and `"biz_events"` count reporting in `Plugin._log_entries()`.
  - `test/_utils.py`: Extend `execute_telemetry_test()` to toggle `config._config["otel"]["biz_events"]["is_disabled"]`, compute `biz_events_expected`, include it in `entries_expected`, and assert `biz_events` count when present in `base_count`.
- **New `focus_costs` Plugin (`src/dtagent/plugins/focus_costs*`):**
  - `init/009_focus_costs_init.sql`: Grants `DATABASE ROLE SNOWFLAKE.ORGANIZATION_BILLING_VIEWER TO ROLE DTAGENT_VIEWER` (with fallback to `ORGADMIN` in an exception block) so standalone installation (`scope=init`) works alongside Core Init's `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE`.
  - `admin/050_p_check_billing_access.sql`: Diagnostic helper `DTAGENT_DB.APP.P_CHECK_BILLING_ACCESS()` to verify access to `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3`.
  - `051_v_focus_cost_usage_instrumented.sql`: View `DTAGENT_DB.APP.V_FOCUS_COST_USAGE_INSTRUMENTED` querying `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` with all MixedCase column names double-quoted (`"BillingPeriodStart"`, `"ContractApplied"`, `"x_UpdatedAt"`, etc.), incremental watermark filtering on `"x_UpdatedAt"`, and deterministic SHA-256 `event.id` hashing.
  - `801_focus_costs_task.sql` & `901_update_focus_costs_conf.sql`: Scheduled task (default every 6 hours, disabled by default as it requires an org-enabled account) and config update procedure.
  - `focus_costs.config/`: `focus_costs-config.yml`, `bom.yml`, `instruments-def.yml`, `readme.md`, `config.md`.
- **Semantic Dictionary Alignment & Export (`src/build/semantic_exporter/`, `scripts/tools/`):**
  - Register existing `real.costs` fields (`event.type`, `event.provider`, `event.start`, `event.end`, `cloud.provider`, `price.total.granularity`, `focus.spec.version`, and the 33 pre-existing `focus.*` fields) as `__semdict: ref` in `KNOWN_REFS` and `_KNOWN_SEMDICT_REFS`.
  - Contribute the 5 new Snowflake extension fields (`snowflake.x_UpdatedAt`, `snowflake.x_OrganizationName`, `snowflake.x_ServiceLevel`, `snowflake.x_BalanceSource`, `snowflake.x_ContractCommitCostBalance`) and 2 FOCUS v1.3 standard fields (`focus.HostProviderName`, `focus.ContractApplied`) as `__semdict: new`, consulting `@information-architect` during implementation.

## Capabilities

### New Capabilities

- `focus-costs-plugin`: Collects FOCUS v1.3 billing and usage line items from `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` and delivers them to Dynatrace as `cost.real.spend` business events conforming to the `real.costs` Semantic Dictionary model, including Step Zero `SEND_TELEMETRY` validation and Snowflake privilege provisioning.
- `bizevents-plugin-sdk`: First-class support in `Plugin._log_entries()`, `BizEvents._pack_event_data()`, `util.py`, and `execute_telemetry_test()` for plugins whose primary telemetry output is `biz_events`.
- `semantic-dictionary-focus-export`: Support for `bizevents` DQL query contexts, `FOCUS` acronym casing, `real.costs` (`focus.*`) reference allowlisting, and `snowflake.x_*` / FOCUS 1.3 field export.

### Modified Capabilities

## Impact

- **Core Python SDK:** `src/dtagent/otel/events/bizevents.py`, `src/dtagent/util.py`, `src/dtagent/plugins/__init__.py`
- **Plugin SQL & Python:** `src/dtagent/plugins/focus_costs.py`, `src/dtagent/plugins/focus_costs.sql/**`, `src/dtagent/plugins/focus_costs.config/**`, `src/dtagent.sql/agents/700_dtagent.sql`, `conf/config-template.yml`
- **Build & Semantic Exporter:** `scripts/tools/instruments-def.schema.json`, `src/build/semantic_exporter/field_emitters.py`, `src/build/semantic_exporter/document_builders.py`
- **Tests:** `test/_utils.py`, `test/plugins/test_focus_costs.py`, `test/test_data/focus_costs.ndjson`, `test/test_results/test_focus_costs/`, `test/core/test_instruments_def_completeness.py`, `test/core/test_semdict_output_compliance.py`
- **Docs:** `docs/USECASES.md`, `docs/CHANGELOG.md`, `.context/devlog/1.0.1/focus-cost-usage.md`

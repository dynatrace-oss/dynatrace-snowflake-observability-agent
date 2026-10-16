## 1. Step Zero — Prototype & Validate `real.costs` Shape with `SEND_TELEMETRY`

- [ ] 1.1 Run the synthetic 1-row `CALL DTAGENT_DB.APP.SEND_TELEMETRY(...)` query on `test-qa` and verify ingestion in Grail (`fetch bizevents | filter event.type == "cost.real.spend"`) and Dynatrace Costs App
- [ ] 1.2 Create and test `DTAGENT_DB.APP.P_SEND_FOCUS_COSTS_SAMPLE(limit_rows INT, lookback_hours INT)` against `SNOWFLAKE.BILLING.FOCUS_COST_USAGE_V1_3` on an org-enabled account

## 2. Core SDK & Test Harness Support for BizEvents Plugins

- [ ] 2.1 Update `src/dtagent/util.py` (`_cleanup_data` and `_cleanup_dict`) to convert `decimal.Decimal` values to `int`/`float` and add unit tests in `test/core/test_util.py`
- [ ] 2.2 Update `src/dtagent/otel/events/bizevents.py` (`BizEvents._pack_event_data`) to preserve `event_data.get("event.id") or event_data.get("id")` in the CloudEvents `id` header and strip `None` values via `_cleanup_dict`; add unit tests in `test/otel/test_events.py`
- [ ] 2.3 Add `_report_via_bizevents()` and `biz_events` gating/flushing/counting support to `Plugin._log_entries()` in `src/dtagent/plugins/__init__.py`
- [ ] 2.4 Update `test/_utils.py::execute_telemetry_test()` to support `"biz_events"` in `disabled_telemetry` and `base_count`

## 3. `focus_costs` Plugin Implementation (SQL, Python, Config)

- [ ] 3.1 Create `src/dtagent/plugins/focus_costs.sql/init/009_focus_costs_init.sql` granting `DATABASE ROLE SNOWFLAKE.ORGANIZATION_BILLING_VIEWER TO ROLE DTAGENT_VIEWER` (with `ORGADMIN` fallback in exception block)
- [ ] 3.2 Create `src/dtagent/plugins/focus_costs.sql/admin/050_p_check_billing_access.sql` (`DTAGENT_DB.APP.P_CHECK_BILLING_ACCESS()`)
- [ ] 3.3 Create `src/dtagent/plugins/focus_costs.sql/051_v_focus_cost_usage_instrumented.sql` with double-quoted MixedCase columns, `"x_UpdatedAt"` incremental filtering, and `OBJECT_CONSTRUCT` mapping to `focus.*` and `snowflake.x_*`
- [ ] 3.4 Create `src/dtagent/plugins/focus_costs.sql/801_focus_costs_task.sql` and `901_update_focus_costs_conf.sql`
- [ ] 3.5 Implement `FocusCostsPlugin` in `src/dtagent/plugins/focus_costs.py` and register `focus_costs` in `src/dtagent.sql/agents/700_dtagent.sql` and `conf/config-template.yml`
- [ ] 3.6 Create `src/dtagent/plugins/focus_costs.config/focus_costs-config.yml` and `bom.yml`

## 4. Semantic Dictionary & Documentation

- [ ] 4.1 Create `src/dtagent/plugins/focus_costs.config/instruments-def.yml` with `__semdict: ref` for existing `real.costs` fields and `__semdict: new` for `snowflake.x_*` + FOCUS 1.3 fields
- [ ] 4.2 Update `scripts/tools/instruments-def.schema.json` (allow `"bizevents"` in `DqlQuery.context`), `src/build/semantic_exporter/field_emitters.py` (`KNOWN_REFS`, `DISPLAY_NAME_ACRONYMS`, `SIG_NS`), and `test/core/test_instruments_def_completeness.py` (`_KNOWN_SEMDICT_REFS`, `_ALLOWED_CAPS`)
- [ ] 4.3 Consult `@information-architect` to validate the Semantic Dictionary export and `real.costs.yaml` / `model_group_business_analytics.yaml` alignment for `snowflake.x_*` and FOCUS 1.3 fields
- [ ] 4.4 Write `src/dtagent/plugins/focus_costs.config/readme.md` and `config.md`, update `docs/USECASES.md`, `docs/CHANGELOG.md`, and `.context/devlog/1.0.1/focus-cost-usage.md`, and run `./scripts/dev/build_docs.sh`

## 5. Testing, Build & Deployment Gate

- [ ] 5.1 Create `test/test_data/focus_costs.ndjson`, `test/plugins/test_focus_costs.py`, and golden results in `test/test_results/test_focus_costs/`
- [ ] 5.2 Run `.venv/bin/pytest`, `make lint` (pylint 10.00/10), `./scripts/dev/build.sh`, and `./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm,dry_run`

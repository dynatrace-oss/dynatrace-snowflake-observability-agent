# DSOA Release QA Checklist

This checklist covers all manual and live-system tests required before tagging a
DSOA release. Work through each section in order. Record results as
`[PASS]`, `[FAIL]`, or `[SKIP reason]` next to each item.

For an AI-guided walkthrough of the live-telemetry tests (Section C), load the
`qa-runner` skill in OpenCode — it automates version detection, deployment
commands, notebook deployment, and guides you tile by tile.

**Tags:** Items are tagged with evaluation mode:

- `[AUTO-EVAL]` — can be verified programmatically via DQL; qa-runner handles
- `[VISUAL]` — requires human visual inspection (dashboard rendering, UI)
- `[BOTH]` — auto-eval provides pass/fail, but human should double-check on
  the corresponding dashboard or in Distributed Traces view
- `[DEFERRED]` — requires data latency >6h; seed data now, verify next day

---

## Section A — Offline / Automated

These checks do not require a live Snowflake or Dynatrace environment. Confirm
each passes locally or in CI before proceeding to live testing.

- [ ] **A1** — Documentation reviewed against the
  [Dynatrace content checklist](https://developer.dynatrace.com/design/foundations/content-checklist/)

- [ ] **A2** — `./scripts/dev/build.sh` succeeds with no errors

- [ ] **A3** — `make lint` passes — pylint must score **10.00/10**

- [ ] **A4** — `.venv/bin/pytest` passes — full test suite green (BDX-1830:
  also verify `pip show snowflake-connector-python` reports `>= 4.4.0`)

- [ ] **A5** — `./scripts/dev/build_docs.sh` succeeds with no errors

- [ ] **A6** — `pytest test/lint/test_plugin_contexts_declared.py` — every
  `Plugin` subclass declares non-empty `PLUGIN_CONTEXTS`; all `dsoa.run.context`
  values in fixtures are declared (BDX-1795)

- [ ] **A7** — `pytest test/lint/test_select_star_audit.py` — zero `SELECT *`
  from `SNOWFLAKE.ACCOUNT_USAGE.*` or `SNOWFLAKE.INFORMATION_SCHEMA.*` in any
  SQL view (BDX-1928 / BCR-2275)

- [ ] **A8** — `pytest test/perf/test_memory_pack_values.py` — 5000
  query_history rows fit within memory budget (BDX-1084)

- [ ] **A9** — `Dockerfile` builds successfully:
  `docker build -t dsoa-test .` (BDX-1968)

- [ ] **A10** — All dashboards pass `dtctl apply --dry-run` on test tenant.
  Run: `./scripts/deploy/deploy_dt_assets.sh --scope=dashboards --env=test-qa --dry-run`

- [ ] **A11** — All workflows pass `dtctl apply --dry-run` on test tenant.
  Run: `./scripts/deploy/deploy_dt_assets.sh --scope=workflows --env=test-qa --dry-run`

- [ ] **A12** — OpenPipeline settings object validates against tenant.
  Run: `dtctl apply --dry-run` on `docs/openpipeline/snowagent-logs-pipeline/snowagent-logs-pipeline.yml`
  (BDX-697)

- [ ] **A13** — Docker non-interactive deployment smoke test (BDX-1968).
  Pre-requisite: `docker build -t dsoa-test .` from A9. Run:

  ```bash
  docker run --rm \
    -e DSOA_DT_TENANT="dummy.tenant.example.com" \
    -e DTAGENT_TOKEN="dt0c01.DUMMY.DUMMYDUMMYDUMMY" \
    -e SNOWFLAKE_ACCOUNT="dummy-account" \
    -e SNOWFLAKE_USER="dummy-user" \
    dsoa-test \
    --env=test-qa --defaults --options=skip_confirm,manual
  ```

  Verify the container exits 0 and writes a deploy SQL file to stdout/output.
  This validates the non-interactive `--defaults` path used in GitHub Actions.

- [ ] **A14** — GitHub Actions workflow template is valid (BDX-1968).
  Verify `src/assets/ci-templates/github/dsoa-deploy.yml.template` passes
  `yamllint`, contains a `workflow_dispatch` trigger with `scope` input, and
  references `ghcr.io/dynatrace-oss/dsoa-deploy:` image.
  Run: `yamllint src/assets/ci-templates/github/dsoa-deploy.yml.template`
  Also verify `release.yml` still has the `build-and-push-docker` job that
  publishes to GHCR on each tagged release.

---

## Section B — Deployment Validation

These tests validate the deployment tooling. A single Snowflake environment is
sufficient (use `test-qa` unless noted). Run each scenario independently
and restore to a clean `--scope=all` state before the next scenario.

> **Standard fresh deployment command:**
>
> ```bash
> ./scripts/deploy/deploy.sh test-qa --scope=all --options=skip_confirm
> ```

- [ ] **B1** — Fresh deployment with `--scope=all` completes without errors.
  All tasks start successfully; no operational errors or warnings in logs.

- [ ] **B2** — Manual execution runs correctly from `700_dtagent.sql`.
  Execute the stored procedure **once per plugin** using the separate
  `call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'))` statements from the comment
  block at the bottom of `src/dtagent.sql/agents/700_dtagent.sql`.
  Do **not** call with all plugins in a single `ARRAY_CONSTRUCT` — the `snow sql`
  CLI will time out on a full run.

  **Pre-requisite:** ensure `~/.snowflake/config.toml` has the following set on
  the connection profile for this environment (5-minute timeout to handle cold
  starts on data-heavy plugins):

  ```toml
  login_timeout = 300
  network_timeout = 300
  ```

  After running all per-plugin calls, verify that all plugins appear as
  `FINISHED` in biz events within the last 30 minutes.

- [ ] **B3** — Deployment with pre-created init and admin objects and custom
  object names. Create the database, warehouse, and roles manually with
  non-default names, then deploy with matching `conf/` config; verify the agent
  uses the custom names.

- [ ] **B4** — Deployment with `--scope=agents,config`:

  ```bash
  ./scripts/deploy/deploy.sh test-qa --scope=agents,config --options=skip_confirm
  ```

- [ ] **B5** — Deployment with `--scope=plugins,agents`:

  ```bash
  ./scripts/deploy/deploy.sh test-qa --scope=plugins,agents --options=skip_confirm
  ```

- [ ] **B6** — Deployment without optional components. Set `roles.admin: "-"` and
  `snowflake.resource_monitor.name: "-"` in the config; deploy with
  `--scope=all`; verify the agent still runs correctly.

- [ ] **B7** — Deployment without plugins. Set `plugins.disabled_by_default: true`
  and `plugins.deploy_disabled_plugins: false`; deploy with `--scope=all`;
  verify no plugin SQL objects are created.

- [ ] **B8** — Deployment with selected plugins only. Enable a subset of plugins
  and set `plugins.deploy_disabled_plugins: false`; verify only those plugins
  are present in Snowflake and produce telemetry.

- [ ] **B9** — Configuration-only update:

  ```bash
  ./scripts/deploy/deploy.sh test-qa --scope=config --options=skip_confirm
  ```

  Verify task schedules resume and new config values take effect.

- [ ] **B10** — Disabled plugins are not deployed when
  `deploy_disabled_plugins: false`. Disable a plugin, set the flag, redeploy;
  confirm the plugin's SQL views and procedures are absent in Snowflake.

- [ ] **B11** — LOG_EVENT_LEVEL BCR adaptation (BDX-1936). Deploy on
  BCR-2026_02-capable account; verify `event_log` plugin uses
  `LOG_EVENT_LEVEL`. If pre-BCR account, verify fallback path works without
  errors. `[SKIP reason if account BCR status unknown]`

- [ ] **B12** — `disabled_by_default: true` config-only redeploy (BDX-1944 /
  BDX-1905). From B1 baseline: set `plugins.disabled_by_default: true` in
  config, then `--scope=config` redeploy. Verify ALL plugin tasks are
  suspended (`SHOW TASKS ... WHERE state = 'started'` returns 0 rows).
  Restore config afterward.

- [ ] **B13** — Interactive deploy wizard (BDX-1969). Move
  `conf/config-test-qa.yml` aside. Run `deploy.sh test-qa --interactive` with
  scripted stdin answers. Verify wizard produces a valid
  `conf/config-test-qa.yml` (passes yamllint) and deploy proceeds.
  Restore original config.

- [ ] **B14** — Non-admin deployment path (BDX-1992). Deploy with
  `roles.admin: "-"` (admin scope disabled). Verify `query_history` plugin
  still captures warehouse queries via the non-admin fallback of
  `P_MONITOR_WAREHOUSES`. Check telemetry count > 0 for query_history.

- [ ] **B15** — Install completeness check (BDX-714). After a fresh B1
  deployment, run `--scope=verify`. Verify the check reports all objects
  present and version matches.

- [ ] **B16** — GitHub Actions / `--temporary-connection` deployment path
  (BDX-1968). Set `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` environment
  variables (key-pair auth) and deploy **without** a named connection profile:

  ```bash
  export SNOWFLAKE_ACCOUNT="<orgname-accountname>"
  export SNOWFLAKE_USER="<service-account>"
  export SNOWFLAKE_PRIVATE_KEY_RAW="<pem-private-key>"
  ./scripts/deploy/deploy.sh test-qa --scope=config --options=skip_confirm
  ```

  Verify deploy.sh auto-detects the env vars and uses `--temporary-connection`
  (confirm in deploy log: no `snow_agent_test-qa` named connection used).
  This is the exact path exercised by the GitHub Actions workflow template.

---

## Section C — Live Telemetry Tests

These tests require **both** the current and previous release environments running
and sending data to the same Dynatrace tenant.

### Setup

1. Deploy the current release to `dev-{CURR_TAG}` (e.g. `DEV-{CURR_TAG}`):

   ```bash
   ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=all --options=skip_confirm
   ```

1. Deploy the previous release to `dev-{PREV_TAG}` (e.g. `DEV-{PREV_TAG}`):

   ```bash
   ./scripts/deploy/deploy.sh dev-{PREV_TAG} --scope=all --options=skip_confirm
   ```

1. Run synthetic simulation scripts (see `test/tools/setup_test_*.sql`):

   ```bash
   snow sql -c snow_agent_test-qa -f test/tools/setup_test_<name>.sql
   ```

1. Deploy the test notebook:

   ```bash
   ./scripts/test/deploy_test_notebook.sh --curr-version={CURR_VERSION} --prev-version={PREV_VERSION}
   ```

   Open the printed notebook URL in Dynatrace before proceeding.

1. Deploy OpenPipeline rules (BDX-697):

   ```bash
   ./scripts/deploy/deploy_dt_assets.sh --scope=openpipeline --env=test-qa
   ```

> Tiles marked **[COMPARE]** display both `DEV-{PREV_TAG}` and `DEV-{CURR_TAG}` series
> on the same chart. Verify that both series appear and neither shows unexpected
> volume changes. All other tiles are single-environment (current only).

---

### C1 — Data Volume and Ingestion Health

- [ ] **C1.1** `[AUTO-EVAL]` — **No tasks failing** — no Snowflake task
  failures visible in operational logs or Snowflake task history.

- [ ] **C1.2** `[AUTO-EVAL]` — **No operational errors or warnings in logs** —
  agent logs show no `ERROR` or `WARN` level entries unrelated to known issues.

- [ ] **C1.3** `[AUTO-EVAL]` — **No increase in `dt.ingest.warning`**
  `[COMPARE]`
  Notebook tile: *No increase in dt.ingest.warning*

- [ ] **C1.4** `[BOTH]` — **Volume of logs per module does not change a lot**
  `[COMPARE]`
  Notebook tile: *Volume of logs per module does not change a lot*

- [ ] **C1.5** `[BOTH]` — **Volume of spans per module does not change**
  `[COMPARE]`
  Notebook tile: *Volume of spans per module does not change*

- [ ] **C1.6** `[BOTH]` — **Tracking data volume by plugin** `[COMPARE]`
  Notebook tile: *Tracking data volume by plugin*

- [ ] **C1.7** `[BOTH]` — **Tracking data volume by context** `[COMPARE]`
  Notebook tile: *Tracking data volume by context*

- [ ] **C1.8** `[BOTH]` — **Tracking data volume by type** `[COMPARE]`
  Notebook tile: *Tracking data volume by type*

---

### C2 — Metrics Reporting

- [ ] **C2.1** `[AUTO-EVAL]` — **Budget metrics are reported**
  Notebook tile: *Budget metrics are reported*

- [ ] **C2.2** `[AUTO-EVAL]` — **Metrics are reported with
  deployment.environment**
  Notebook tile: *Metrics are reported with deployment.environment*

- [ ] **C2.3** `[AUTO-EVAL]` — **Query history metrics are reported**
  Notebook tile: *Query history metrics are reported*

- [ ] **C2.4** `[AUTO-EVAL]` — **Query time per table is available (metrics)**
  Notebook tile: *Query time per table is available — metrics*

- [ ] **C2.5** `[AUTO-EVAL]` — **Table volume is tracked (rows)**
  Notebook tile: *Table volume is tracked (rows)*

- [ ] **C2.6** `[AUTO-EVAL]` — **Table volume is tracked (size)**
  Notebook tile: *Table volume is tracked (size)*

- [ ] **C2.7** `[AUTO-EVAL]` — **Trust center metrics are reported**
  Notebook tile: *Trust center metrics are reported*

- [ ] **C2.8** `[AUTO-EVAL]` — **Metrics for dynamic tables are reported**
  Notebook tile: *Metrics for dynamic tables are reported*

- [ ] **C2.9** `[BOTH]` — **Table health: storage metrics are reported**
  (BDX-1829)
  Notebook tile: *Table health storage metrics*
  DQL: `timeseries avg(snowflake.table.active_bytes), by:{deployment.environment}`
  filtered to `dsoa.run.plugin == "table_health"` — expect data points.
  Dashboard: *Data Volume & Storage* or custom QA tile.

- [ ] **C2.10** `[BOTH]` — **Table health: clustering metrics are reported**
  (BDX-1829)
  Notebook tile: *Table health clustering metrics*
  DQL: `timeseries avg(snowflake.table.clustering.depth), by:{deployment.environment}`
  — expect data points if `clustering_enabled: true` in config.

- [ ] **C2.11** `[AUTO-EVAL]` — **Metering metrics across >=3 service types**
  (BDX-1865)
  Notebook tile: *Metering metrics by service type*
  DQL: `timeseries sum(snowflake.credits.used), by:{snowflake.service.type}`
  filtered to `dsoa.run.plugin == "metering"` — expect >=3 distinct types.

- [ ] **C2.12** `[BOTH]` — **Org costs: credit metrics are reported**
  (BDX-682, requires ORGADMIN)
  Notebook tile: *Org costs credit metrics*
  DQL: `timeseries avg(snowflake.org.credits.used), by:{deployment.environment}`
  — expect data points. Dashboard: *Org-Level Costs Observability*.

- [ ] **C2.13** `[AUTO-EVAL]` — **Org costs: storage metrics are reported**
  (BDX-682, requires ORGADMIN)
  DQL: `timeseries avg(snowflake.org.data.stored), by:{deployment.environment}`
  — expect data points.

- [ ] **C2.14** `[AUTO-EVAL]` — **Org costs: billing/contract balance
  reported** (BDX-682, requires ORGADMIN)
  DQL: `timeseries avg(snowflake.org.billing.capacity_balance)`
  — expect data points.

- [ ] **C2.15** `[DEFERRED]` — **Cold tables: access metrics reported**
  (BDX-676, daily schedule, 24h latency)
  DQL: `timeseries avg(snowflake.table.days_since_last_access)`
  — seed data today, verify tomorrow.

- [ ] **C2.16** `[DEFERRED]` — **Query cost attribution metrics reported**
  (BDX-703, 8h latency from QUERY_ATTRIBUTION_HISTORY)
  DQL: `timeseries avg(snowflake.credits.attributed_compute), by:{deployment.environment}`
  — seed queries today, verify after 8+ hours.

---

### C3 — Logs Reporting

- [ ] **C3.1** `[AUTO-EVAL]` — **Check if all queries are recorded in
  active_queries, logs, and spans**
  Notebook tile: *Queries with mismatched log/span coverage*
  `[SHOULD BE EMPTY]`

- [ ] **C3.2** `[AUTO-EVAL]` — **Query time per table — logs**
  Notebook tile: *Query time per table — logs*

- [ ] **C3.3** `[AUTO-EVAL]` — **Logs for dynamic tables are reported**
  Notebook tile: *Logs for dynamic tables are reported*

- [ ] **C3.4** `[AUTO-EVAL]` — **Event log entries are reported (logs)**
  Notebook tile: *Event log entries are reported (logs)*

- [ ] **C3.5** `[AUTO-EVAL]` — **Validating that status.message is correctly
  set for trust_center** `[COMPARE]`
  Notebook tile: *Validating that status.message is correctly set for
  trust_center*

- [ ] **C3.6** `[AUTO-EVAL]` — **Check if warnings on missing warehouse and
  global resource monitors are correct** `[COMPARE]`
  Notebook tile: *Check if warnings on missing warehouse and global resource
  monitors are correct*

- [ ] **C3.7** `[AUTO-EVAL]` — **Metering logs include service_type
  dimension** (BDX-1865)
  DQL: `fetch logs | filter dsoa.run.plugin == "metering" | filter isNotNull(snowflake.service.type) | summarize count()`
  — expect count > 0.

- [ ] **C3.8** `[AUTO-EVAL]` — **Event log per-DB source attribution**
  (BDX-716, requires `discover_db_event_tables: true`)
  DQL: `fetch logs | filter dsoa.run.plugin == "event_log" | filter isNotNull(_dsoa_source_table) | summarize count()`
  — expect count > 0 when DB event table override is configured.
  `[SKIP if discover_db_event_tables not enabled in test config]`

---

### C4 — Spans and Distributed Traces

- [ ] **C4.1** `[AUTO-EVAL]` — **Query history spans are reported**
  Notebook tile: *Volume of spans per module does not change*
  (query_history line)

- [ ] **C4.2** `[AUTO-EVAL]` — **Query time per table — spans**
  Notebook tile: *Query time per table — spans*

- [ ] **C4.3** `[AUTO-EVAL]` — **Coverage of spans for query_history logs**
  Notebook tile: *Coverage of spans for query_history logs*
  `[SHOULD BE EMPTY]`

- [ ] **C4.4** `[AUTO-EVAL]` — **Completeness: span.events +
  supportability.dropped_events_count reported**
  Notebook tile: *Completeness span.events +
  supportability.dropped_events_count reported* `[SHOULD BE EMPTY]`

- [ ] **C4.5** `[AUTO-EVAL]` — **Event log entries are reported (spans)**
  Notebook tile: *Event log entries are reported (spans)*

- [ ] **C4.6** `[AUTO-EVAL]` — **Checking if there are span.parent_id
  reported**
  Notebook tile: *Checking if there are span.parent_id reported*

- [ ] **C4.7** `[AUTO-EVAL]` — **Checking if for all queries in the same
  SnowAgent run span.parent_id is not missing**
  Notebook tile: *Checking if for all queries in the same SnowAgent run
  span.parent_id is not missing* `[SHOULD BE EMPTY]`

- [ ] **C4.8** `[BOTH]` — **Checking that spans are correctly rendered in
  Distributed Traces**
  Notebook tile: *Checking that spans are correctly rendered in Distributed
  Traces*
  **Human:** open a trace ID from C4.6 in the Distributed Traces UI and
  verify the waterfall renders correctly with parent-child hierarchy.

- [ ] **C4.9** `[AUTO-EVAL]` — **There are no
  supportability.non_persisted_attribute_keys reported**
  Notebook tile: *There are no supportability.non_persisted_attribute_keys
  reported* `[SHOULD BE EMPTY]`

- [ ] **C4.10** `[BOTH]` — **Cross-batch span parent persistence** (BDX-644)
  DQL: verify that a child query in agent run N+1 correctly links to
  parent span from agent run N via `span.parent_id`.
  **Human:** open cross-batch trace in Distributed Traces UI.
  Simulation: `test/tools/setup_test_span_cross_batch.sql`

- [ ] **C4.11** `[AUTO-EVAL]` — **task_history attempt is integer-typed**
  (BDX-1903)
  DQL: `fetch logs, from: now()-7d | filter dsoa.run.context == "task_history" | filter deployment.environment == "DEV-{CURR_TAG}" | filter isNotNull(snowflake.task.run.attempt) | fields snowflake.task.run.attempt | limit 5`
  — verify values are numeric (not strings like `"1"`). Note: tasks plugin emits **logs**, not spans; use 7-day window since task runs may not occur daily.

- [ ] **C4.12** `[AUTO-EVAL]` — **serverless_tasks db.namespace is NULL not
  empty string** (BDX-1904) `[SHOULD BE EMPTY]`
  DQL: `fetch logs | filter dsoa.run.context == "serverless_tasks" | filter db.namespace == "" | summarize count()`
  — expect 0 rows.

- [ ] **C4.13** `[BOTH]` — **DDL change detection on query spans** (BDX-1998)
  DQL: `fetch spans, from: now()-7d | filter deployment.environment == "DEV-{CURR_TAG}" | filter isNotNull(snowflake.object.ddl.operation) | fields snowflake.object.name, snowflake.object.type, snowflake.object.ddl.operation | limit 10`
  — expect rows with `snowflake.object.ddl.operation` in `{CREATE, REPLACE, ALTER, DROP}`.
  Note: Snowflake uses `REPLACE` (not `CREATE`) for `CREATE OR REPLACE` statements.
  Run `setup_test_warehouse_ddl.sql` to generate ALTER and DROP examples.

---

### C5 — Events and BizEvents

- [ ] **C5.1** `[BOTH]` — **Events are sent by plugins** `[COMPARE]`
  Notebook tile: *Events are sent by plugins*

- [ ] **C5.2** `[AUTO-EVAL]` — **BizEvents are sent by plugins**
  Notebook tile: *BizEvents are sent by plugins*

- [ ] **C5.3** `[AUTO-EVAL]` — **Self-monitoring BizEvents correlation**
  Notebook tile: *Self-monitoring BizEvents correlation*

- [ ] **C5.4** `[AUTO-EVAL]` — **Timestamps in BizEvents are correct and
  current** `[SHOULD BE EMPTY]`
  Notebook tile: *Timestamps in BizEvents are correct and current*

- [ ] **C5.5** `[AUTO-EVAL]` — **Event log entries are reported (process
  metrics)**
  Notebook tile: *Event log entries are reported (process metrics)*

- [ ] **C5.6** `[AUTO-EVAL]` — **Data schemas plugin report events**
  Notebook tile: *Data schemas plugin report events*

- [ ] **C5.7** `[AUTO-EVAL]` — **Check if the usage self-monitoring telemetry
  is delivered**
  Notebook tile: *Check if the usage self-monitoring telemetry is delivered*

- [ ] **C5.8** `[AUTO-EVAL]` — **Acquisition warning bizevents fire on known
  triggers** (BDX-1647)
  DQL: `fetch bizevents | filter event.type == "dsoa.acquisition.warning" | filter deployment.environment == "DEV-{CURR_TAG}" | summarize count()`
  — after running `setup_test_shares.sql` unhealthy-share scenario, expect
  count > 0. Verify `processing_errors` field is a valid JSON list.

- [ ] **C5.9** `[AUTO-EVAL]` — **No unexpected acquisition problems**
  (BDX-1647) `[SHOULD BE EMPTY]`
  DQL: `fetch bizevents | filter event.type == "dsoa.acquisition.problem" | filter deployment.environment == "DEV-{CURR_TAG}" | summarize count()`
  — expect 0 rows (problems indicate real SQL failures, not warnings).

- [ ] **C5.10** `[BOTH]` — **Resource monitor credit alert events** (BDX-623)
  DQL: `fetch events | filter dsoa.run.plugin == "resource_monitors" | filter event.kind == "CUSTOM_INFO" | filter deployment.environment == "DEV-{CURR_TAG}"`
  — after running `setup_test_resource_monitor_alert.sql`, expect threshold
  events at 50/80/90/100% levels.
  Dashboard: *Costs Monitoring* > Resource Monitor section.

---

### C6 — Active Queries

- [ ] **C6.1** `[AUTO-EVAL]` — **Check if long running queries are reported
  more than once in active_queries**
  Notebook tile: *Check if long running queries are reported more than once in
  active_queries*

- [ ] **C6.2** `[AUTO-EVAL]` — **Check the visibility of the statuses RUNNING
  and SUCCESS for execution_status in active_queries**
  Notebook tile: *Check the visibility of the statuses RUNNING and SUCCESS for
  execution_status in active_queries*

- [ ] **C6.3** `[AUTO-EVAL]` — **All statuses of active queries are reported**
  Notebook tile: *All statuses of active queries are reported*

- [ ] **C6.4** `[VISUAL]` — **Active queries raw sample** (spot-check raw log
  content)
  Notebook tile: *Active queries raw sample*

---

### C7 — Shares and Governance

- [ ] **C7.1** `[AUTO-EVAL]` — **All inbound and outbound shares are reported
  (logs)**
  Notebook tile: *All inbound and outbound shares are reported (logs)*

- [ ] **C7.2** `[AUTO-EVAL]` — **All inbound and outbound shares are reported
  (events)**
  Notebook tile: *All inbound and outbound shares are reported (events)*

- [ ] **C7.3** `[AUTO-EVAL]` — **Inbound shares with missing DB are reported**
  Notebook tile: *Inbound shares with missing DB are reported*

- [ ] **C7.4** `[AUTO-EVAL]` — **Query count per user is tracked**
  Notebook tile: *Query count per user is tracked*

---

### C8 — Plugin Lifecycle and Isolation

- [ ] **C8.1** `[AUTO-EVAL]` — **Checking if disabled plugins do not produce
  data** `[SHOULD BE EMPTY]`
  Notebook tile: *Checking if disabled plugins do not produce data*

- [ ] **C8.2** `[AUTO-EVAL]` — **Checking if disabled plugins are not deployed
  when requested** `[SHOULD BE EMPTY]`
  Notebook tile: *Checking if disabled plugins are not deployed when requested*

- [ ] **C8.3** `[AUTO-EVAL]` — **Disabled plugin tasks are suspended**
  (BDX-1905)
  After disabling a plugin and redeploying with `--scope=config`, verify its
  Snowflake task state is `suspended` (not `started`).
  DQL: `fetch bizevents | filter dsoa.run.context == "self_monitoring" | filter dsoa.task.exec.status == "FINISHED" | filter dsoa.run.plugin == "<disabled_plugin>" | summarize count()`
  — expect 0 for the disabled plugin.

- [ ] **C8.4** `[AUTO-EVAL]` — **event_usage plugin deprecated — no new
  telemetry** (BDX-1865)
  DQL: `fetch logs | filter dsoa.run.plugin == "event_usage" | filter deployment.environment == "DEV-{CURR_TAG}" | summarize count()`
  — expect 0 rows (metering replaces event_usage).

---

### C9 — OpenPipeline Derived Metrics (BDX-697)

> **Pre-requisite:** OpenPipeline rules must be deployed to the tenant via
> `deploy_dt_assets.sh --scope=openpipeline`. These metrics are generated by
> Dynatrace from DSOA log records — not emitted by the agent directly.
> Allow ~5-15 minutes after simulation traffic for metrics to appear.

- [ ] **C9.1** `[AUTO-EVAL]` — **Failed login attempts metric** (BDX-697)
  DQL: `timeseries count(snowflake.login.attempts.failed), by:{deployment.environment}`
  — expect > 0 after simulation traffic with failed logins
  (`setup_test_openpipeline_traffic.sql`).

- [ ] **C9.2** `[AUTO-EVAL]` — **Successful login attempts metric** (BDX-697)
  DQL: `timeseries count(snowflake.login.attempts.successful), by:{deployment.environment}`
  — expect > 0 (normal agent operation generates successful logins).

- [ ] **C9.3** `[AUTO-EVAL]` — **Total login attempts metric** (BDX-697)
  DQL: `timeseries count(snowflake.login.attempts.total), by:{deployment.environment}`
  — expect > 0.

- [ ] **C9.4** `[AUTO-EVAL]` — **Failed task runs metric** (BDX-697)
  DQL: `timeseries count(snowflake.task.run.failed), by:{deployment.environment}`
  — expect > 0 after simulation traffic with failing tasks.

- [ ] **C9.5** `[AUTO-EVAL]` — **Cancelled task runs metric** (BDX-697)
  DQL: `timeseries sum(snowflake.task.run.cancelled)` (no env dimension; `timeseries count()` syntax incorrect for this metric)
  — expect > 0 after simulation traffic with cancelled tasks.

- [ ] **C9.6** `[AUTO-EVAL]` — **Successful task runs metric** (BDX-697)
  DQL: `timeseries count(snowflake.task.run.successful), by:{deployment.environment}`
  — expect > 0 (DSOA's own tasks generate successful runs).

---

### C10 — Query Text Obfuscation (BDX-1916)

> **Pre-requisite:** Run `setup_test_query_obfuscation.sql` to generate queries
> with known literals. Then test each obfuscation mode by changing
> `plugins.query_history.obfuscation_mode` in config and redeploying with
> `--scope=config`. Wait for one agent cycle between mode switches.

- [ ] **C10.1** `[AUTO-EVAL]` — **Mode: off** — `db.query.text` contains
  original SQL with literals intact.
  DQL: `fetch spans, from: now()-7d | filter dsoa.run.context == "query_history" | filter deployment.environment == "DEV-{CURR_TAG}" | filter contains(db.query.text, "'DSOA_OBFUSCATION_TEST'") | summarize count()`
  — expect count > 0 when mode is `off`. Use 7-day window (simulation may have run on a prior day).

- [ ] **C10.2** `[AUTO-EVAL]` — **Mode: literals** — `db.query.text` has
  string and integer literals replaced.
  DQL: same query as C10.1 — expect count == 0 when mode is `literals`

- [ ] **C10.3** `[AUTO-EVAL]` — **Mode: full** — `db.query.text` contains
  only a normalized hash.
  DQL: `fetch spans | filter dsoa.run.context == "query_history" | filter matchesPhrase(db.query.text, "SELECT") | summarize count()`
  — expect count == 0 when mode is `full` (full obfuscation replaces entire
  text with hash).
  Note: narrow the notebook tile timeframe to approximately 30 minutes post-mode-switch to avoid false failures from pre-switch spans.

---

### C11 — Signal Protection and Overload (BDX-1965)

> **Pre-requisite:** Run `setup_test_overload.sql` to generate > max_entries
> query rows, then configure `plugins.query_history.max_entries` to a value
> lower than the generated row count.

- [ ] **C11.1** `[AUTO-EVAL]` — **max_entries cap is enforced** (BDX-1965)
  DQL: `fetch bizevents | filter deployment.environment == "DEV-{CURR_TAG}" | filter event.type == "dsoa.signal_overload_protection" | summarize count = count(), total_dropped = sum(toLong(dropped_count))`
  — expect count > 0 after overload simulation. Signal is a bizevent of type `dsoa.signal_overload_protection`
  with properties `dropped_count`, `total_processed`, `total_available`, `max_entries`.
  Note: `dsoa.acquisition.skipped_count` does not exist in the codebase.

- [ ] **C11.2** `[AUTO-EVAL]` — **Overload warning logged** (BDX-1965)
  DQL: `fetch logs | filter dsoa.run.plugin == "query_history" | filter deployment.environment == "DEV-{CURR_TAG}" | filter loglevel == "WARN" | filter contains(content, "Signal overload protection active") | summarize count()`
  — expect count > 0. Warning is emitted in the `query_history` plugin context (not `self_monitoring`).

---

## Section D — Dashboard Visual Inspection

Open each dashboard in the Dynatrace tenant and verify it renders correctly with
data from `DEV-{CURR_TAG}`. Check that all tiles load (no "No data" errors on
tiles that should have data), that time-series charts show expected shapes, and
that no tiles display error states.

> **QA test notebook:** <https://aym57094.sprint.apps.dynatracelabs.com/ui/document/v0/#share=notebook;id=5bf9b0d9-6ebe-473f-8847-fe2d787a6c61>
> All 14 dashboards deployed to aym57094 on 2026-05-18 via `./scripts/deploy/deploy_dt_assets.sh --scope=dashboards`

- [ ] **D1** `[VISUAL]` — **Query Performance** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/f245f73a-35f5-4298-8158-2a8aa4611a23>

- [ ] **D2** `[VISUAL]` — **Query Quality** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/4a90d08b-5c20-4e67-be3d-c78b57c16441>

- [ ] **D3** `[VISUAL]` — **Query Deep Dive** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/9dbac33a-25ba-4192-b748-c8b6fe561c3b>

- [ ] **D4** `[VISUAL]` — **Performance Explorer** dashboard renders correctly (BDX-951)
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/ebce348b-6b05-4b2b-9562-d30cdf14dcc3>

- [ ] **D5** `[VISUAL]` — **Costs Monitoring** dashboard renders correctly (BDX-686: warehouse idle time tiles)
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/e446e588-b917-4a63-867c-643ca783c79e>

- [ ] **D6** `[VISUAL]` — **Budgets & FinOps** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/64b09f3f-1faa-49c8-98ba-7aa496af8cdf>

- [ ] **D7** `[VISUAL]` — **Org-Level Costs Observability** dashboard renders correctly (BDX-682, BDX-1182: consumption tiles)
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/6881ff48-0945-4e94-94af-2e4bb338724e>

- [ ] **D8** `[VISUAL]` — **Data Volume & Storage** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/fdd7c1db-ffc0-4c75-adea-f60cadc120ad>

- [ ] **D9** `[VISUAL]` — **Tasks & Pipelines** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/5b3a0282-123e-416c-97bb-d8b6063e6323>

- [ ] **D10** `[VISUAL]` — **Snowpipes Monitoring** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/f3eda451-afe7-4035-bca8-7b09620de132>

- [ ] **D11** `[VISUAL]` — **Shares & Governance** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/579f882f-b7b7-4f78-a51f-64517849dbde>

- [ ] **D12** `[VISUAL]` — **Snowflake Security** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/0f2f0c6b-5250-4f88-bc78-fe58d80fd59a>

- [ ] **D13** `[VISUAL]` — **Self-Monitoring** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/0363ea51-aafe-4d5c-b76b-70342d5f70ed>

- [ ] **D14** `[VISUAL]` — **Warehouse Change Detection** dashboard renders correctly
  <https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/662ba27b-28ce-476a-b1bb-3d39ac613b0a>

---

## Result Summary

Fill in after completing all sections.

| Section                 | Passed | Failed | Skipped | Total   |
|-------------------------|--------|--------|---------|---------|
| A — Offline             |        |        |         | 14      |
| B — Deployment          |        |        |         | 16      |
| C1 — Data Volume        |        |        |         | 8       |
| C2 — Metrics            |        |        |         | 16      |
| C3 — Logs               |        |        |         | 8       |
| C4 — Spans              |        |        |         | 13      |
| C5 — Events             |        |        |         | 10      |
| C6 — Active Queries     |        |        |         | 4       |
| C7 — Shares             |        |        |         | 4       |
| C8 — Plugin Lifecycle   |        |        |         | 4       |
| C9 — OpenPipeline       |        |        |         | 6       |
| C10 — Obfuscation       |        |        |         | 3       |
| C11 — Signal Protection |        |        |         | 2       |
| D — Dashboards          |        |        |         | 14      |
| **Total**               |        |        |         | **119** |

**QA Signoff:**

```text
DSOA {VERSION} QA — {DATE} — {PASS}/{TOTAL} items passed ({DEFERRED} deferred)
Tester: {NAME}
Notebook: {NOTEBOOK_URL}
Deferred items: C2.15, C2.16, C4.13 — re-verify after 24h
```

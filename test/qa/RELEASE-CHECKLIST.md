# DSOA Release QA Checklist

This checklist covers all manual and live-system tests required before tagging a
DSOA release. Work through each section in order. Record results as
`[PASS]`, `[FAIL]`, or `[SKIP reason]` next to each item.

For an AI-guided walkthrough of the live-telemetry tests (Section C), load the
`qa-runner` skill in OpenCode — it automates version detection, deployment
commands, notebook deployment, and guides you tile by tile.

---

## Section A — Offline / Automated

These checks do not require a live Snowflake or Dynatrace environment. Confirm
each passes locally or in CI before proceeding to live testing.

- [ ] **A1** — Documentation reviewed against the
  [Dynatrace content checklist](https://developer.dynatrace.com/design/foundations/content-checklist/)
- [ ] **A2** — `./scripts/dev/build.sh` succeeds with no errors
- [ ] **A3** — `make lint` passes — pylint must score **10.00/10**
- [ ] **A4** — `.venv/bin/pytest` passes — full test suite green
- [ ] **A5** — `./scripts/dev/build_docs.sh` succeeds with no errors

---

## Section B — Deployment Validation

These tests validate the deployment tooling. A single Snowflake environment is
sufficient (use `dev-{CURR_TAG}` unless noted). Run each scenario independently
and restore to a clean `--scope=all` state before the next scenario.

> **Standard fresh deployment command:**
>
> ```bash
> ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=all --options=skip_confirm
> ```

- [ ] **B1** — Fresh deployment with `--scope=all` completes without errors.
  All tasks start successfully; no operational errors or warnings in logs.

- [ ] **B2** — Manual execution runs correctly from `700_dtagent.sql`.
  Execute the stored procedure directly in Snowflake; verify telemetry arrives
  in Dynatrace.

- [ ] **B3** — Deployment with pre-created init and admin objects and custom
  object names. Create the database, warehouse, and roles manually with
  non-default names, then deploy with matching `conf/` config; verify the agent
  uses the custom names.

- [ ] **B4** — Deployment with `--scope=agents,config`:

  ```bash
  ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=agents,config --options=skip_confirm
  ```

- [ ] **B5** — Deployment with `--scope=plugins,agents`:

  ```bash
  ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=plugins,agents --options=skip_confirm
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
  ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=config --options=skip_confirm
  ```

  Verify task schedules resume and new config values take effect.

- [ ] **B10** — Disabled plugins are not deployed when
  `deploy_disabled_plugins: false`. Disable a plugin, set the flag, redeploy;
  confirm the plugin's SQL views and procedures are absent in Snowflake.

---

## Section C — Live Telemetry Tests

These tests require **both** the current and previous release environments running
and sending data to the same Dynatrace tenant.

### Setup

1. Deploy the current release to `dev-{CURR_TAG}` (e.g. `DEV-094`):

   ```bash
   ./scripts/deploy/deploy.sh dev-{CURR_TAG} --scope=all --options=skip_confirm
   ```

1. Deploy the previous release to `dev-{PREV_TAG}` (e.g. `DEV-093`):

   ```bash
   ./scripts/deploy/deploy.sh dev-{PREV_TAG} --scope=all --options=skip_confirm
   ```

1. Deploy the test notebook:

   ```bash
   ./scripts/test/deploy_test_notebook.sh --curr-version={CURR_VERSION} --prev-version={PREV_VERSION}
   ```

   Open the printed notebook URL in Dynatrace before proceeding.

> Tiles marked **[COMPARE]** display both `DEV-{PREV}` and `DEV-{CURR}` series
> on the same chart. Verify that both series appear and neither shows unexpected
> volume changes. All other tiles are single-environment (current only).

---

### C1 — Data Volume and Ingestion Health

- [ ] **C1.1** — **No tasks failing** — no Snowflake task failures visible in
  operational logs or Snowflake task history.

- [ ] **C1.2** — **No operational errors or warnings in logs** — agent logs show
  no `ERROR` or `WARN` level entries unrelated to known issues.

- [ ] **C1.3** — **No increase in `dt.ingest.warning`** `[COMPARE]`
  Notebook tile: *No increase in dt.ingest.warning*

- [ ] **C1.4** — **Volume of logs per module does not change a lot** `[COMPARE]`
  Notebook tile: *Volume of logs per module does not change a lot*

- [ ] **C1.5** — **Volume of spans per module does not change** `[COMPARE]`
  Notebook tile: *Volume of spans per module does not change*

- [ ] **C1.6** — **Tracking data volume by plugin** `[COMPARE]`
  Notebook tile: *Tracking data volume by plugin*

- [ ] **C1.7** — **Tracking data volume by context** `[COMPARE]`
  Notebook tile: *Tracking data volume by context*

- [ ] **C1.8** — **Tracking data volume by type** `[COMPARE]`
  Notebook tile: *Tracking data volume by type*

---

### C2 — Metrics Reporting

- [ ] **C2.1** — **Budget metrics are reported**
  Notebook tile: *Budget metrics are reported*

- [ ] **C2.2** — **Metrics are reported with deployment.environment**
  Notebook tile: *Metrics are reported with deployment.environment*

- [ ] **C2.3** — **Query history metrics are reported**
  Notebook tile: *Query history metrics are reported*

- [ ] **C2.4** — **Query time per table is available (metrics)**
  Notebook tile: *Query time per table is available — metrics*

- [ ] **C2.5** — **Table volume is tracked (rows)**
  Notebook tile: *Table volume is tracked (rows)*

- [ ] **C2.6** — **Table volume is tracked (size)**
  Notebook tile: *Table volume is tracked (size)*

- [ ] **C2.7** — **Trust center metrics are reported**
  Notebook tile: *Trust center metrics are reported*

- [ ] **C2.8** — **Metrics for dynamic tables are reported**
  Notebook tile: *Metrics for dynamic tables are reported*

---

### C3 — Logs Reporting

- [ ] **C3.1** — **Check if all queries are recorded in active_queries, logs, and spans**
  Notebook tile: *Check if all queries are recorded in active_queries, logs, and spans*

- [ ] **C3.2** — **Query time per table — logs**
  Notebook tile: *Query time per table — logs*

- [ ] **C3.3** — **Logs for dynamic tables are reported**
  Notebook tile: *Logs for dynamic tables are reported*

- [ ] **C3.4** — **Event log entries are reported (logs)**
  Notebook tile: *Event log entries are reported (logs)*

- [ ] **C3.5** — **Validating that status.message is correctly set for trust_center** `[COMPARE]`
  Notebook tile: *Validating that status.message is correctly set for trust_center*

- [ ] **C3.6** — **Check if warnings on missing warehouse and global resource monitors are correct** `[COMPARE]`
  Notebook tile: *Check if warnings on missing warehouse and global resource monitors are correct*

---

### C4 — Spans and Distributed Traces

- [ ] **C4.1** — **Query history spans is reported**
  Notebook tile: *Volume of spans per module does not change* (query_history line)

- [ ] **C4.2** — **Query time per table — spans**
  Notebook tile: *Query time per table — spans*

- [ ] **C4.3** — **Coverage of spans for query_history logs**
  Notebook tile: *Coverage of spans for query_history logs*

- [ ] **C4.4** — **Completeness: span.events + supportability.dropped_events_count reported**
  Notebook tile: *Completeness span.events + supportability.dropped_events_count reported*

- [ ] **C4.5** — **Event log entries are reported (spans)**
  Notebook tile: *Event log entries are reported (spans)*

- [ ] **C4.6** — **Checking if there are span.parent_id reported**
  Notebook tile: *Checking if there are span.parent_id reported*

- [ ] **C4.7** — **Checking if for all queries in the same SnowAgent run span.parent_id is not missing**
  Notebook tile: *Checking if for all queries in the same SnowAgent run span.parent_id is not missing*

- [ ] **C4.8** — **Checking that spans are correctly rendered in Distributed Traces**
  Notebook tile: *Checking that spans are correctly rendered in Distributed Traces*

- [ ] **C4.9** — **There are no supportability.non_persisted_attribute_keys reported**
  Notebook tile: *There are no supportability.non_persisted_attribute_keys reported*

---

### C5 — Events and BizEvents

- [ ] **C5.1** — **Events are sent by plugins** `[COMPARE]`
  Notebook tile: *Events are sent by plugins*

- [ ] **C5.2** — **BizEvents are sent by plugins**
  Notebook tile: *BizEvents are sent by plugins*

- [ ] **C5.3** — **Self-monitoring BizEvents correlation**
  Notebook tile: *Self-monitoring BizEvents correlation*

- [ ] **C5.4** — **Timestamps in BizEvents are correct and current**
  Notebook tile: *Timestamps in BizEvents are correct and current*

- [ ] **C5.5** — **Event log entries are reported (process metrics)**
  Notebook tile: *Event log entries are reported (process metrics)*

- [ ] **C5.6** — **Data schemas plugin report events**
  Notebook tile: *Data schemas plugin report events*

- [ ] **C5.7** — **Check if the usage self-monitoring telemetry is delivered**
  Notebook tile: *Check if the usage self-monitoring telemetry is delivered*

---

### C6 — Active Queries

- [ ] **C6.1** — **Check if long running queries are reported more than once in active_queries**
  Notebook tile: *Check if long running queries are reported more than once in active_queries*

- [ ] **C6.2** — **Check the visibility of the statuses RUNNING and SUCCESS for execution_status in active_queries**
  Notebook tile: *Check the visibility of the statuses RUNNING and SUCCESS for execution_status in active_queries*

- [ ] **C6.3** — **All statuses of active queries are reported**
  Notebook tile: *All statuses of active queries are reported*

- [ ] **C6.4** — **Active queries raw sample** (spot-check raw log content)
  Notebook tile: *Active queries raw sample*

---

### C7 — Shares and Governance

- [ ] **C7.1** — **All inbound and outbound shares are reported (logs)**
  Notebook tile: *All inbound and outbound shares are reported (logs)*

- [ ] **C7.2** — **All inbound and outbound shares are reported (events)**
  Notebook tile: *All inbound and outbound shares are reported (events)*

- [ ] **C7.3** — **Inbound shares with missing DB are reported**
  Notebook tile: *Inbound shares with missing DB are reported*

- [ ] **C7.4** — **Query count per user is tracked**
  Notebook tile: *Query count per user is tracked*

---

### C8 — Plugin Lifecycle and Isolation

- [ ] **C8.1** — **Checking if disabled plugins do not produce data**
  Notebook tile: *Checking if disabled plugins do not produce data*

- [ ] **C8.2** — **Checking if disabled plugins are not deployed when requested**
  Notebook tile: *Checking if disabled plugins are not deployed when requested*

---

## Result Summary

Fill in after completing all sections.

| Section               | Passed | Failed | Skipped | Total  |
|-----------------------|--------|--------|---------|--------|
| A — Offline           |        |        |         | 5      |
| B — Deployment        |        |        |         | 10     |
| C1 — Data Volume      |        |        |         | 8      |
| C2 — Metrics          |        |        |         | 8      |
| C3 — Logs             |        |        |         | 6      |
| C4 — Spans            |        |        |         | 9      |
| C5 — Events           |        |        |         | 7      |
| C6 — Active Queries   |        |        |         | 4      |
| C7 — Shares           |        |        |         | 4      |
| C8 — Plugin Lifecycle |        |        |         | 2      |
| **Total**             |        |        |         | **63** |

**QA Signoff:**

```text
DSOA {VERSION} QA — {DATE} — {PASS}/{TOTAL} items passed
Tester: {NAME}
Notebook: {NOTEBOOK_URL}
```

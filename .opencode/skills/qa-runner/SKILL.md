---
name: qa-runner
description: >
  AI-guided QA walkthrough for DSOA releases. Automates version detection,
  deployment commands, notebook deployment, and interactive test walkthrough.
  Use when a QA engineer needs to execute the DSOA release test suite.
license: MIT
compatibility: opencode
metadata:
  audience: qa-engineers, developers
---

# Skill: DSOA Release QA Runner

Use this skill when asked to:

- Start the QA process for a DSOA release
- Walk a QA engineer through the release test suite
- Deploy and open the QA test notebook
- Generate a QA signoff summary

---

## Overview

The QA runner executes in five sequential phases. Complete each phase fully
before moving to the next. Do not skip phases.

| Phase | Name                | Who acts                     | Output                               |
|-------|---------------------|------------------------------|--------------------------------------|
| 1     | Version discovery   | AI (automated)               | Verified version tags + config files |
| 2     | Deployment guidance | Human (AI provides commands) | Both environments running            |
| 3     | Notebook deployment | AI (runs script)             | Notebook URL                         |
| 3.5   | Auto-evaluation     | AI (runs DQL via MCP)        | Pass/fail for auto-evaluable tests   |
| 4     | Test walkthrough    | Interactive                  | Pass/fail per checklist item         |
| 5     | QA signoff          | AI                           | Markdown report file                 |

---

## Phase 1 — Version Discovery

Run all of the following automatically without waiting for the human.

### 1a. Determine current version

```bash
grep '^VERSION' src/dtagent/version.py | head -1
```

Store as `CURR_VERSION` (e.g. `0.9.4`).

### 1b. Derive version tags

The 3-digit tag is: `printf "%03d" $((minor * 10 + patch))`

```bash
bash -c '
v="'"${CURR_VERSION}"'"
minor=$(echo "$v" | cut -d. -f2)
patch=$(echo "$v" | cut -d. -f3)
printf "%03d\n" $(( minor * 10 + patch ))
'
```

Store as `CURR_TAG` (e.g. `094`). The deployment environment is `DEV-${CURR_TAG}`.

### 1c. Determine previous version

**Default rule:** decrement the patch component of `CURR_VERSION` by 1.
Example: `0.9.4` → `0.9.3` → tag `093`.

**Override:** If the human specifies a different previous version
(e.g. because the previous release was a hotfix like `0.9.3.1`), use that
version instead. Ask:

> "The default previous version is `{auto_prev}`. Is that correct, or should I
> use a different version (e.g. `0.9.3.1`)? Type the version or press Enter to
> accept the default."

Store as `PREV_VERSION` and derive `PREV_TAG` using the same algorithm.

### 1d. Verify config files

```bash
ls conf/config-dev-{CURR_TAG}.yml conf/config-dev-{PREV_TAG}.yml 2>&1
```

- If `conf/config-dev-{CURR_TAG}.yml` is **missing**: stop and instruct the human
  to create it (pointing to the current Snowflake account and Dynatrace tenant).
- If `conf/config-dev-{PREV_TAG}.yml` is **missing**: warn the human that
  cross-version comparison tiles will show only the current environment. Ask
  whether to proceed or to create the file first.

### 1e. Extract tenant info

```bash
yq '.core.dynatrace_tenant_address' conf/config-dev-{CURR_TAG}.yml
yq '.core.deployment_environment'   conf/config-dev-{CURR_TAG}.yml
yq '.core.dynatrace_tenant_address' conf/config-dev-{PREV_TAG}.yml
yq '.core.deployment_environment'   conf/config-dev-{PREV_TAG}.yml
```

Verify both configs point to the same `dynatrace_tenant_address`. If they
differ, warn the human — both environments must send data to the same tenant for
comparison tiles to work.

### 1f. Detect ORGADMIN availability

Run silently. Stores whether the account has ORGADMIN access for Phase 3.5
org_costs checks (C2.12-C2.14). If Snowflake is not yet reachable, default to
`false` and re-check at the start of Phase 3.5.

```bash
snow sql -c snow_agent_dev-{CURR_TAG} \
    --role DTAGENT_{CURR_TAG}_OWNER \
    -q "SHOW ROLES LIKE 'ORGADMIN';" 2>/dev/null \
  | grep -qc ORGADMIN && echo "HAS_ORGADMIN=true" || echo "HAS_ORGADMIN=false"
```

Store as `HAS_ORGADMIN` (`true` or `false`). Do **not** block Phase 1 on this
check — it is informational only. If `false`, Phase 3.5 org_costs checks will
record `SKIP (no ORGADMIN)` automatically.

### Phase 1 output

Report the following before proceeding:

```text
Current version:   {CURR_VERSION}  (tag: {CURR_TAG},  env: DEV-{CURR_TAG})
Previous version:  {PREV_VERSION}  (tag: {PREV_TAG},  env: DEV-{PREV_TAG})
Dynatrace tenant:  {TENANT_ADDR}
Config files:      conf/config-dev-{CURR_TAG}.yml  ✓
                   conf/config-dev-{PREV_TAG}.yml  ✓ / ⚠ missing
ORGADMIN access:   {true / false}  (org_costs checks SKIP if false)
```

Ask the human to confirm before proceeding to Phase 2.

---

## Phase 2 — Deployment Guidance

Instruct the human to run the following commands. Both use `--scope=all` for a
fresh, complete deployment of the agent into each environment.

### Deploy the current version

```bash
./scripts/deploy/deploy.sh --env=dev-{CURR_TAG} --scope=all --options=skip_confirm
```

### Deploy the previous version

```bash
./scripts/deploy/deploy.sh --env=dev-{PREV_TAG} --scope=all --options=skip_confirm
```

**Important notes to share:**

- Both deployments must target the same Snowflake account (different schemas/roles
  differentiated by `deployment_environment` tag, not by database name).
- Both deployments must target the same Dynatrace tenant.
- Wait for each deployment to complete and the Snowflake task scheduler to run at
  least one execution cycle before proceeding.
- **Timing expectations:**
  - Most plugins start emitting telemetry within **30 minutes** of the first task run.
  - Some plugins (e.g. those querying heavy Snowflake views) may take **several hours**
    before their first successful execution.
  - Budget-related plugins run **at most once per day** — their data will not appear
    until the daily schedule fires.
  - **Recommendation: deploy today, then come back the next day to perform the
    full test walkthrough once all plugin data is available.**

After both deploys, ask:

> "Have both deployments completed successfully and is telemetry appearing in
> Dynatrace? (yes / no / need help)"

If the human says "need help":
- Check Snowflake task history for the DTAGENT task
- Check agent operational logs: `fetch logs | filter dsoa.run.context == "self_monitoring"`
- Check for ERROR-level log entries from the agent

---

## Phase 3 — Notebook Deployment

Run the deploy script:

```bash
./scripts/test/deploy_test_notebook.sh \
    --curr-version={CURR_VERSION} \
    --prev-version={PREV_VERSION}
```

**Before running the script**, verify that every `type: dql` tile in
`test/qa/test-suite/test-suite.yml` has `showInput: false` set — this hides
the DQL code in the rendered notebook ("Hide Input" option in the UI). The
expected count of `showInput: false` lines must equal the count of `type: dql`
lines:

```bash
grep -c "type: dql"      test/qa/test-suite/test-suite.yml
grep -c "showInput: false" test/qa/test-suite/test-suite.yml
```

If any tile is missing it, add `showInput: false` on the line immediately after
`type: dql`:

```bash
sed -i '' 's/^    type: dql$/    type: dql\n    showInput: false/' \
    test/qa/test-suite/test-suite.yml
```

The script:
1. Reads `conf/config-dev-{CURR_TAG}.yml` to get the tenant address
2. Finds the matching dtctl context
3. Converts `test/qa/test-suite/test-suite.yml` → JSON and injects the notebook name
4. Deploys via `dtctl apply` and prints the notebook URL
5. Writes the assigned notebook ID back into the YAML for future runs

If `dtctl` is not authenticated, instruct the human to run:

```bash
dtctl auth login
```

Then retry the script.

After a successful deploy, share the notebook URL with the human and ask them to
confirm it opens in Dynatrace. If the notebook ID needs to be committed to the
YAML, remind the human to do so after the QA session.

---

## Phase 3.5 — Auto-Evaluation (AI runs DQL via MCP)

Run **all** auto-evaluable tests using the `execute_dql` MCP tool **without
waiting for the human**. Due to the MCP rate limit (5 calls per 20 seconds),
send tests in batches of 5 with a brief pause between batches if needed.

**Substitutions:**
- `DEV-{CURR_TAG}` → current deployment environment (e.g. `DEV-095`)
- `DEV-{PREV_TAG}` → previous deployment environment (e.g. `DEV-094`)
- Default timeframe: `now()-24h` unless noted per test.

Each test specifies a **DQL** and a **Pass condition**. Record each result as
`PASS`, `FAIL`, or `SKIP` (with reason). Reference the matching checklist ID
(e.g. C4.9) in the report.

**Cowork mode:** When running with 4 parallel Claude sessions, assign batches to
agents as follows:

```
Coordinator / ant-1  →  Batch 1 (core health, always runs first)
ant-2 (after B8-B10) →  Batch 2 (additional metrics, logs, spans)
ant-3                →  Batch 3 (events, active queries, shares, lifecycle)
ant-4                →  Batch 4 (OpenPipeline, obfuscation, overload)
```

Start Batches 2-4 only after the coordinator confirms DEV-{CURR_TAG} telemetry
is flowing (Phase 2 complete, at least one full agent cycle observed).

---

### Batch 1 — Core health

Run by coordinator (or sequentially if not using Cowork).

#### Should-be-empty checks (0 rows = PASS)

#### AE-C4.9 — No supportability.non_persisted_attribute_keys

```dql
fetch spans
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(supportability.non_persisted_attribute_keys)
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C5.4 — Timestamps in BizEvents are current

```dql
fetch bizevents
| filter telemetry.exporter.name == "dynatrace.snowagent"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| filter dsoa.task.exec.status == "STARTED"
| fields timestamp, dsoa.run.id
| join [
  fetch logs
  | filter db.system == "snowflake"
  | filter deployment.environment == "DEV-{CURR_TAG}"
  | filter dsoa.run.context == "self_monitoring"
  | filter isNotNull(dsoa.run.id)
  | summarize {min_timestamp = min(timestamp)}, by: {dsoa.run.id}
]
, kind:leftOuter
, on: {left[dsoa.run.id] == right[dsoa.run.id]}
, fields: {min_timestamp}
| filter isNotNull(min_timestamp)
| fieldsAdd timeShift = abs(timestamp - min_timestamp)
| filterOut timeShift < 10min
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C4.4 — Completeness span.events

```dql
fetch spans, from: now()-7d
| filter dsoa.run.context == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| fields events_count = arraySize(span.events),
         events_added = snowagent.debug.span.events.added,
         events_failed = snowagent.debug.span.events.failed,
         supportability.dropped_events_count
| filter events_count + coalesce(supportability.dropped_events_count, 0) != events_added
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C4.7 — No missing span.parent_id for child queries in same DSOA run

```dql
fetch spans, from: now()-24h
| filter db.system == "snowflake"
| filter isNotNull(dsoa.run.context)
| filter isNotNull(snowflake.query.parent_id)
| filter deployment.environment == "DEV-{CURR_TAG}"
| joinNested parent_spans = [
  fetch spans
  | filter db.system == "snowflake"
  | filter isNotNull(dsoa.run.context)
  | filter isNotNull(snowflake.query.parent_id)
  | filter deployment.environment == "DEV-{CURR_TAG}"
  | fields span.id, snowflake.query.id, dsoa.run.id
], on: {left[snowflake.query.parent_id] == right[snowflake.query.id]}
, executionOrder:leftFirst
| filterOut isNull(parent_spans)
| expand parent_spans
| fieldsFlatten parent_spans, prefix: "parent."
| filter dsoa.run.id == parent.dsoa.run.id
| filter isNull(span.parent_id)
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C1.2 — No ERROR-level agent logs

```dql
fetch logs
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter loglevel == "ERROR"
| filter db.system == "snowflake"
| summarize count = count(), by: {content}
| sort count desc
```

**Pass:** 0 rows. If rows appear, list the `content` values as FAIL notes.

---

### Data-presence checks (data returned = PASS)

#### AE-C2.3 — Query history metrics are reported

```dql
timeseries avg(snowflake.time.execution), by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C5.5 — Process metrics are reported

```dql
timeseries avg(process.cpu.utilization), by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C5.7 — Self-monitoring BizEvents delivered for all plugins

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| filter in(dsoa.task.exec.status, {"STARTED", "FINISHED"})
| summarize count = count(), by: {dsoa.task.name, dsoa.task.exec.status}
| filter count == 0
```

**Pass:** 0 rows (every plugin has count > 0 for both STARTED and FINISHED).

#### AE-C5.8 — No unexpected ingest-quality warnings (BDX-695)

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter event.type == "dsoa.ingest.warning"
| summarize count = count(), by: { `dsoa.ingest.warning.type`, `dsoa.ingest.warning.exporter`, dsoa.run.plugin }
| sort count desc
```

**Pass:** 0 rows — no ingest-quality warnings were detected during the test run.
If rows are present, inspect `dsoa.ingest.warning.detail` for each row to determine whether
the warning is a known/expected condition (e.g. a known attribute cardinality issue) or a
regression. Fail the check if any new warning type appears that was not present in `DEV-{PREV_TAG}`.

#### AE-C5.9 — No unexpected acquisition problems (BDX-1647)

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter event.type == "dsoa.acquisition.problem"
| summarize count = count(), by: { `dsoa.acquisition.problem.type`, `dsoa.acquisition.problem.source`, dsoa.run.plugin }
| sort count desc
```

**Pass:** 0 rows — no acquisition problems (SQL errors during Snowflake data acquisition) were detected.
If rows are present, inspect `dsoa.acquisition.problem.detail` to determine whether the error is transient
(e.g. a view that temporarily had no data) or a regression (missing view, permission error). Fail the check
if any `sql_error` or `sub_row_error` appears on a view that was working in `DEV-{PREV_TAG}`.

---

#### AE-C4.6 — span.parent_id present for child queries

```dql
fetch spans
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(dsoa.run.context)
| filter isNotNull(snowflake.query.parent_id)
| filter isNotNull(span.parent_id)
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.1 — Budget metrics are reported

```dql
timeseries avg(snowflake.credits.limit), by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.
**Timing rule:** The budget plugin runs at most once per day. Do **not** skip this
check — instead, wait until at least 24 hours after deployment before evaluating.
If the environment is < 24h old, defer the check and come back later.

---

### Cross-version comparison checks

#### AE-C1.3 — No increase in dt.ingest.warnings (5% tolerance)

Run two queries — one per environment — then compare:

```dql
fetch logs
| filter telemetry.exporter.name == "dynatrace.snowagent"
| filter in(deployment.environment, {"DEV-{PREV_TAG}", "DEV-{CURR_TAG}"})
| filter isNotNull(dt.ingest.warnings)
| expand warning = dt.ingest.warnings
| summarize count = count(), by: {deployment.environment, warning}
| sort deployment.environment, warning
```

**Pass condition:** For each `warning` type, the count in `DEV-{CURR_TAG}` must
not exceed the count in `DEV-{PREV_TAG}` by more than **5%**, OR the absolute
count in `DEV-{CURR_TAG}` must be lower than in `DEV-{PREV_TAG}`.

Formally: `curr_count <= prev_count * 1.05` for each warning type. If
`DEV-{PREV_TAG}` has 0 of a given warning and `DEV-{CURR_TAG}` has any, that
is a FAIL. Record which warning types failed and their counts.

---

---

### Batch 2 — Additional metrics, logs, spans

Run by eval-batch-1 (ant-2 after B8-B10) in Cowork mode, or sequentially after
Batch 1 otherwise. All queries target `DEV-{CURR_TAG}` unless noted.

#### AE-C1.1 — No Snowflake task execution failures

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| filter dsoa.task.exec.status == "FAILED"
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C2.2 — Metrics reported with deployment.environment

```dql
timeseries avg(snowflake.credits.quota), by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.4 — Query time per table available (metrics)

```dql
timeseries avg(snowflake.time.total_elapsed),
     by: { db.namespace, db.collection.name, deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.5 — Table volume tracked (rows)

```dql
timeseries { max_row_count = max(snowflake.data.rows) }
      , by: { db.collection.name, deployment.environment }
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0. Prerequisite: `setup_test_data_volume_storage.sql` run.

#### AE-C2.6 — Table volume tracked (size)

```dql
timeseries {avg(snowflake.data.rows), avg(snowflake.data.size)},
        union: true,
        by: { db.namespace, db.collection.name, deployment.environment }
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.7 — Trust center metrics reported

```dql
timeseries max(snowflake.trust_center.findings), by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.8 — Metrics for dynamic tables reported

```dql
timeseries {
   avg(snowflake.table.dynamic.lag.mean)
 , avg(snowflake.table.dynamic.lag.target.value)
}, union:true
 , by: {deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0. (7-day timeframe recommended for dynamic table metrics.)

#### AE-C2.11 — Metering metrics across ≥3 service types

```dql
timeseries sum(snowflake.credits.used), by:{snowflake.service.type}
| summarize service_types = countDistinct(snowflake.service.type[])
```

**Pass:** service_types ≥ 3. Prerequisite: `setup_test_metering.sql` run.

#### AE-C2.13 — Org costs: storage metrics (ORGADMIN required)

**Skip if `HAS_ORGADMIN=false`.**

```dql
timeseries avg(snowflake.org.data.stored), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C2.14 — Org costs: billing capacity balance (ORGADMIN required)

**Skip if `HAS_ORGADMIN=false`.**

```dql
timeseries avg(snowflake.org.billing.capacity_balance)
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C3.1 — Queries with mismatched log/span coverage [SHOULD BE EMPTY]

```dql
fetch logs, scanLimitGBytes: -1
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "query_history"
| summarize {qh_count = count(), timestamp = takeAny(timestamp)}, by: {snowflake.query.id}
| append [
  fetch logs, scanLimitGBytes: -1
  | filter deployment.environment == "DEV-{CURR_TAG}"
  | filter dsoa.run.context == "active_queries"
  | sort timestamp asc
  | summarize {aq_count = count(), timestamp = takeLast(timestamp)}, by: {snowflake.query.id}
]
| append [
  fetch spans, scanLimitGBytes: -1
  | filter deployment.environment == "DEV-{CURR_TAG}"
  | filter dsoa.run.context == "query_history"
  | summarize {sp_count = count(), sp_events = max(arraySize(span.events)), sp_events_added = max(snowagent.debug.span.events.added), timestamp = takeAny(start_time)}, by: {snowflake.query.id}
]
| summarize {qh_count=max(qh_count), aq_count=max(aq_count), sp_count=max(sp_count), sp_events=max(sp_events), sp_events_added=max(sp_events_added), timestamp=takeAny(timestamp)}, by:{snowflake.query.id}
| fieldsAdd missing_data = isNull(aq_count) or (isNull(sp_count) xor isNull(qh_count)) or (qh_count != sp_count+sp_events and qh_count != sp_count+sp_events_added)
| filterOut isNull(aq_count)
| filter isNotNull(missing_data)
| summarize count = count()
```

**Pass:** count == 0. Allow 2+ hours after deploy before evaluating.

#### AE-C3.2 — Query time per table (logs)

```dql
fetch logs
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(db.user) and isNotNull(db.collection.name) and isNotNull(snowflake.time.execution)
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C3.3 — Logs for dynamic tables reported

```dql
fetch logs, from: now()-7d
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "dynamic_tables"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(snowflake.table.dynamic.lag.target.value)
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C3.4 — Event log entries reported (logs)

```dql
fetch logs
| filter db.system == "snowflake"
| filter contains(dsoa.run.context, "event_log")
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C3.5 — Trust center status.message correctly set [COMPARE]

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.context == "trust_center"
| filter in(deployment.environment, {"DEV-{PREV_TAG}", "DEV-{CURR_TAG}"})
| summarize count = count(), by: {status.message, deployment.environment}
| summarize rows = count()
```

**Pass:** rows > 0 (at least one status.message value is set).

#### AE-C3.6 — Resource monitor warnings correct [COMPARE]

```dql
fetch logs
| filter in(deployment.environment, {"DEV-{PREV_TAG}", "DEV-{CURR_TAG}"})
| filter dsoa.run.context == "resource_monitors"
| filter snowflake.warehouse.is_unmonitored
| filter loglevel == "WARN"
| summarize count = count(), by: {deployment.environment}
```

**Pass:** count > 0 for `DEV-{CURR_TAG}` (warnings fire when unmonitored warehouses exist).

#### AE-C3.7 — Metering logs include service_type dimension

```dql
fetch logs
| filter dsoa.run.plugin == "metering"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(snowflake.service.type)
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C4.1 — Query history spans reported

```dql
fetch spans
| filter db.system == "snowflake"
| filter in(deployment.environment, {"DEV-{PREV_TAG}", "DEV-{CURR_TAG}"})
| filter dsoa.run.plugin == "query_history"
| summarize count = count(), by: {deployment.environment}
```

**Pass:** count > 0 for `DEV-{CURR_TAG}`.

#### AE-C4.2 — Query time per table (spans)

```dql
fetch spans
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(db.user) and isNotNull(db.collection.name) and isNotNull(snowflake.time.execution)
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C4.3 — Coverage of spans for query_history logs [SHOULD BE EMPTY]

```dql
fetch logs, from: now()-7d
| filter db.system == "snowflake"
| filter dsoa.run.context == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize {logs_per_query = count()}, by: {snowflake.query.id}
| append [
  fetch spans, from: now()-7d
  | filter db.system == "snowflake"
  | filter dsoa.run.context == "query_history"
  | filter deployment.environment == "DEV-{CURR_TAG}"
  | fieldsAdd span_events_count = coalesce(arraySize(span.events), 0) + 1
]
| summarize {count_logs = sum(logs_per_query), count_events = sum(span_events_count)}, by: {snowflake.query.id}
| filter count_events == 0 or count_events != count_logs
| filter count_events < 2001
| summarize count = count()
```

**Pass:** count == 0.

#### AE-C4.5 — Event log entries reported (spans)

```dql
fetch spans
| filter db.system == "snowflake"
| filter dsoa.run.context == "event_log_spans"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C4.11 — task_history attempt is integer-typed

```dql
fetch spans
| filter dsoa.run.plugin == "tasks"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(snowflake.task.run.attempt)
| fields snowflake.task.run.attempt
| limit 5
| summarize count = count()
```

**Pass:** count > 0 AND all `snowflake.task.run.attempt` values are numeric (not quoted strings). If the field is returned as a string (e.g., `"1"` instead of `1`), record as FAIL with the raw value.

#### AE-C4.12 — serverless_tasks db.namespace is NULL not empty string [SHOULD BE EMPTY]

```dql
fetch logs
| filter dsoa.run.context == "serverless_tasks"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter db.namespace == ""
| summarize count = count()
```

**Pass:** count == 0.

---

### Batch 3 — Events, active queries, shares, plugin lifecycle

Run by eval-batch-2 (ant-3) in Cowork mode, or sequentially after Batch 2.

#### AE-C5.2 — BizEvents sent by plugins

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| summarize count = count(), by: {dsoa.task.name}
| filter count == 0
```

**Pass:** 0 rows returned (every plugin has at least one BizEvent).

#### AE-C5.3 — Self-monitoring BizEvents correlation

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter dsoa.run.context == "self_monitoring"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize {count = count()}, by: {dsoa.task.exec.id, dsoa.task.name}
| filter count != 2
| summarize unpaired = count()
```

**Pass:** unpaired == 0 (every run has exactly one STARTED and one FINISHED BizEvent).

#### AE-C5.6 — Data schemas plugin reports events

```dql
fetch events
| filter dsoa.run.context == "data_schemas"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0. Prerequisite: `setup_test_data_volume_storage.sql` run.

#### AE-C5.10 — Resource monitor credit alert events

```dql
fetch events
| filter dsoa.run.plugin == "resource_monitors"
| filter event.kind == "CUSTOM_INFO"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0 after running `setup_test_resource_monitor_alert.sql`.
**Skip if:** simulation script was not run.

#### AE-C6.1 — Long-running queries reported more than once

```dql
fetch logs
| filter dsoa.run.context == "active_queries"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(snowflake.query.id)
| summarize {count = count()}, by: {snowflake.query.id}
| filter count > 1
| summarize multi_reported = count()
```

**Pass:** multi_reported > 0 (at least one query_id appears in more than one agent cycle).

#### AE-C6.2 — RUNNING and SUCCESS statuses visible

```dql
fetch logs
| filter dsoa.run.context == "active_queries"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(snowflake.query.id)
| summarize statuses = collectDistinct(snowflake.query.execution_status)
```

**Pass:** result contains both `"RUNNING"` and `"SUCCESS"` in the statuses list.

#### AE-C6.3 — All statuses of active queries reported

```dql
fetch logs, from: now()-7d
| filter dsoa.run.context == "active_queries"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count(), by: {snowflake.query.execution_status}
| sort count desc
```

**Pass:** At least 2 distinct status values are returned (e.g. RUNNING, SUCCESS).

#### AE-C7.1 — Inbound and outbound shares reported (logs)

```dql
fetch logs
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter in(dsoa.run.context, {"inbound_shares", "outbound_shares"})
| summarize count = count(), by: {snowflake.share.kind}
```

**Pass:** rows returned for both `INBOUND` and `OUTBOUND` share kinds.
Prerequisite: `setup_test_shares.sql` run.

#### AE-C7.2 — Inbound and outbound shares reported (events)

```dql
fetch events
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.plugin == "shares"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C7.3 — Inbound shares with missing DB reported

```dql
fetch logs
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "inbound_shares"
| filter isNull(db.namespace)
| summarize count = count()
```

**Pass:** count > 0 after running `setup_test_shares.sql` (which creates a share
with a dropped/missing database).

#### AE-C7.4 — Query count per user tracked

```dql
fetch spans
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(db.user)
| summarize user_count = countDistinct(db.user)
```

**Pass:** user_count > 0.

#### AE-C8.1 — Disabled plugins produce no data [SHOULD BE EMPTY]

Run **only** after a B8/B10 disabled-plugins deployment. Substitute the disabled
plugin name for `{DISABLED_PLUGIN}` (e.g., `tasks`).

```dql
fetch logs
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.plugin == "{DISABLED_PLUGIN}"
| filter dsoa.run.context != "self_monitoring"
| filter timestamp > now()-15m
| summarize count = count()
```

**Pass:** count == 0.
**Skip if:** no disabled-plugins scenario was run.

#### AE-C8.2 — Disabled plugins not in self_monitoring deployment [SHOULD BE EMPTY]

Run **only** after a B10 deploy with `deploy_disabled_plugins: false`.

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| filter dsoa.run.plugin == "{DISABLED_PLUGIN}"
| filter timestamp > now()-30m
| summarize count = count()
```

**Pass:** count == 0.
**Skip if:** deploy_disabled_plugins scenario was not run.

#### AE-C8.3 — Disabled plugin task suspended (no FINISHED events)

Run after disabling a plugin with `--scope=config` redeploy.

```dql
fetch bizevents
| filter db.system == "snowflake"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.context == "self_monitoring"
| filter dsoa.task.exec.status == "FINISHED"
| filter dsoa.run.plugin == "{DISABLED_PLUGIN}"
| filter timestamp > now()-15m
| summarize count = count()
```

**Pass:** count == 0.
**Skip if:** B12 (disabled_by_default config redeploy) scenario was not run.

#### AE-C8.4 — event_usage plugin deprecated, no new telemetry [SHOULD BE EMPTY]

```dql
fetch logs
| filter dsoa.run.plugin == "event_usage"
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count == 0 (metering plugin replaces event_usage as of 0.9.5).

---

### Batch 4 — OpenPipeline, obfuscation, overload

Run by eval-batch-3 (ant-4) in Cowork mode, or sequentially after Batch 3.

**Prerequisites for this batch:**
- C9.x: OpenPipeline rules deployed (`deploy_dt_assets.sh --scope=openpipeline`),
  `setup_test_openpipeline_traffic.sql` run, ~5-15 min for metric extraction
- C10.x: `setup_test_query_obfuscation.sql` run, mode switches applied,
  one agent cycle between each switch
- C11.x: `setup_test_overload.sql` run, `max_entries` config value lowered

#### AE-C9.1 — Failed login attempts metric

```dql
timeseries count(snowflake.login.attempts.failed), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C9.2 — Successful login attempts metric

```dql
timeseries count(snowflake.login.attempts.successful), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C9.3 — Total login attempts metric

```dql
timeseries count(snowflake.login.attempts.total), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C9.4 — Failed task runs metric

```dql
timeseries count(snowflake.task.run.failed), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C9.5 — Cancelled task runs metric

```dql
timeseries count(snowflake.task.run.cancelled), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C9.6 — Successful task runs metric

```dql
timeseries count(snowflake.task.run.successful), by:{deployment.environment}
| filter deployment.environment == "DEV-{CURR_TAG}"
| summarize count = count()
```

**Pass:** count > 0.

#### AE-C10.1 — Obfuscation mode: off — literal visible

Requires `obfuscation_mode: off` config + agent cycle after `setup_test_query_obfuscation.sql`.

```dql
fetch spans
| filter dsoa.run.context == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter contains(db.query.text, "'DSOA_OBFUSCATION_TEST'")
| summarize count = count()
```

**Pass:** count > 0 (sentinel literal present in unobfuscated query text).

#### AE-C10.2 — Obfuscation mode: literals — sentinel absent [SHOULD BE EMPTY]

Requires `obfuscation_mode: literals` config + re-run of simulation + one agent cycle.
Use a **narrow timeframe** (`now()-30m`) to target only post-switch spans.

```dql
fetch spans, from: now()-30m
| filter dsoa.run.context == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter contains(db.query.text, "'DSOA_OBFUSCATION_TEST'")
| summarize count = count()
```

**Pass:** count == 0 (literal is replaced by `?` in literals mode).

#### AE-C10.3 — Obfuscation mode: full — no SQL keywords [SHOULD BE EMPTY]

Requires `obfuscation_mode: full` config + re-run + one agent cycle. Use
`now()-30m` timeframe to exclude pre-switch spans.

```dql
fetch spans, from: now()-30m
| filter dsoa.run.context == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter matchesPhrase(db.query.text, "SELECT")
| summarize count = count()
```

**Pass:** count == 0 (full obfuscation replaces entire query text with a hash).

#### AE-C11.1 — max_entries cap enforced

```dql
fetch bizevents
| filter dsoa.run.plugin == "query_history"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter isNotNull(dsoa.acquisition.skipped_count)
| summarize total_skipped = sum(dsoa.acquisition.skipped_count)
```

**Pass:** total_skipped > 0. Prerequisite: `setup_test_overload.sql` run and
`max_entries` configured lower than generated row count.

#### AE-C11.2 — Overload warning logged

```dql
fetch logs
| filter dsoa.run.context == "self_monitoring"
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter loglevel == "WARN"
| filter contains(content, "max_entries")
| summarize count = count()
```

**Pass:** count > 0.

---

### Auto-evaluation output

After running all batches, present the consolidated results table:

```text
## Auto-Evaluation Results — DEV-{CURR_TAG}

### Batch 1 — Core health

| Test    | Description                                      | Result    | Notes |
|---------|--------------------------------------------------|-----------|-------|
| AE-C4.9 | No non_persisted_attribute_keys                  | PASS/FAIL |       |
| AE-C5.4 | BizEvent timestamps are current                  | PASS/FAIL |       |
| AE-C4.4 | Completeness span.events                         | PASS/FAIL |       |
| AE-C4.7 | No missing span.parent_id for child queries      | PASS/FAIL |       |
| AE-C1.2 | No ERROR-level agent logs                        | PASS/FAIL |       |
| AE-C2.3 | Query history metrics reported                   | PASS/FAIL |       |
| AE-C5.5 | Process metrics reported                         | PASS/FAIL |       |
| AE-C5.7 | Self-monitoring BizEvents all delivered          | PASS/FAIL |       |
| AE-C5.8 | No unexpected ingest-quality warnings            | PASS/FAIL |       |
| AE-C5.9 | No unexpected acquisition problems               | PASS/FAIL |       |
| AE-C4.6 | span.parent_id present for child queries         | PASS/FAIL |       |
| AE-C2.1 | Budget metrics reported                          | PASS/FAIL |       |
| AE-C1.3 | No increase in dt.ingest.warnings (5% tolerance) | PASS/FAIL |       |

### Batch 2 — Additional metrics, logs, spans

| Test     | Description                                     | Result    | Notes |
|----------|-------------------------------------------------|-----------|-------|
| AE-C1.1  | No task execution failures                      | PASS/FAIL |       |
| AE-C2.2  | Metrics reported with deployment.environment    | PASS/FAIL |       |
| AE-C2.4  | Query time per table (metrics)                  | PASS/FAIL |       |
| AE-C2.5  | Table volume tracked (rows)                     | PASS/FAIL |       |
| AE-C2.6  | Table volume tracked (size)                     | PASS/FAIL |       |
| AE-C2.7  | Trust center metrics reported                   | PASS/FAIL |       |
| AE-C2.8  | Dynamic table metrics reported                  | PASS/FAIL |       |
| AE-C2.11 | Metering across >=3 service types               | PASS/FAIL |       |
| AE-C2.13 | Org costs: storage metrics                      | PASS/FAIL/SKIP |  |
| AE-C2.14 | Org costs: billing capacity balance             | PASS/FAIL/SKIP |  |
| AE-C3.1  | No mismatched log/span coverage                 | PASS/FAIL |       |
| AE-C3.2  | Query time per table (logs)                     | PASS/FAIL |       |
| AE-C3.3  | Logs for dynamic tables reported                | PASS/FAIL |       |
| AE-C3.4  | Event log entries (logs)                        | PASS/FAIL |       |
| AE-C3.5  | Trust center status.message set                 | PASS/FAIL |       |
| AE-C3.6  | Resource monitor warnings correct               | PASS/FAIL |       |
| AE-C3.7  | Metering logs include service_type              | PASS/FAIL |       |
| AE-C4.1  | Query history spans reported                    | PASS/FAIL |       |
| AE-C4.2  | Query time per table (spans)                    | PASS/FAIL |       |
| AE-C4.3  | Span coverage for query_history logs            | PASS/FAIL |       |
| AE-C4.5  | Event log entries (spans)                       | PASS/FAIL |       |
| AE-C4.11 | task_history attempt is integer-typed           | PASS/FAIL |       |
| AE-C4.12 | serverless_tasks db.namespace null not empty    | PASS/FAIL |       |

### Batch 3 — Events, active queries, shares, lifecycle

| Test     | Description                                     | Result    | Notes |
|----------|-------------------------------------------------|-----------|-------|
| AE-C5.2  | BizEvents sent by all plugins                   | PASS/FAIL |       |
| AE-C5.3  | Self-monitoring BizEvents paired                | PASS/FAIL |       |
| AE-C5.6  | Data schemas plugin events reported             | PASS/FAIL |       |
| AE-C5.10 | Resource monitor credit alert events            | PASS/FAIL/SKIP |  |
| AE-C6.1  | Long-running queries reported > once            | PASS/FAIL |       |
| AE-C6.2  | RUNNING and SUCCESS statuses visible            | PASS/FAIL |       |
| AE-C6.3  | All active query statuses reported              | PASS/FAIL |       |
| AE-C7.1  | Inbound/outbound shares (logs)                  | PASS/FAIL |       |
| AE-C7.2  | Inbound/outbound shares (events)                | PASS/FAIL |       |
| AE-C7.3  | Inbound shares with missing DB                  | PASS/FAIL |       |
| AE-C7.4  | Query count per user tracked                    | PASS/FAIL |       |
| AE-C8.1  | Disabled plugins produce no data                | PASS/FAIL/SKIP |  |
| AE-C8.2  | Disabled plugins not in deployment              | PASS/FAIL/SKIP |  |
| AE-C8.3  | Disabled plugin task suspended                  | PASS/FAIL/SKIP |  |
| AE-C8.4  | event_usage deprecated, no telemetry            | PASS/FAIL |       |

### Batch 4 — OpenPipeline, obfuscation, overload

| Test     | Description                                     | Result    | Notes |
|----------|-------------------------------------------------|-----------|-------|
| AE-C9.1  | Failed login attempts metric                    | PASS/FAIL |       |
| AE-C9.2  | Successful login attempts metric                | PASS/FAIL |       |
| AE-C9.3  | Total login attempts metric                     | PASS/FAIL |       |
| AE-C9.4  | Failed task runs metric                         | PASS/FAIL |       |
| AE-C9.5  | Cancelled task runs metric                      | PASS/FAIL |       |
| AE-C9.6  | Successful task runs metric                     | PASS/FAIL |       |
| AE-C10.1 | Obfuscation mode: off — literal visible         | PASS/FAIL |       |
| AE-C10.2 | Obfuscation mode: literals — sentinel absent    | PASS/FAIL |       |
| AE-C10.3 | Obfuscation mode: full — no SQL keywords        | PASS/FAIL |       |
| AE-C11.1 | max_entries cap enforced                        | PASS/FAIL |       |
| AE-C11.2 | Overload warning logged                         | PASS/FAIL |       |

Auto-evaluated: {N}/57 — {n} passed, {f} failed, {s} skipped
  Batch 1: {n1}/13  Batch 2: {n2}/23  Batch 3: {n3}/15  Batch 4: {n4}/11
  (Deferred: C2.15, C2.16, C4.13 — verify on next day / after data latency window)
```

Include the full consolidated table in the Phase 5 markdown report.

---

## Phase 4 — Test Walkthrough

Walk through `test/qa/RELEASE-CHECKLIST.md` section by section. For each item:

- State the item description clearly
- For Section A (offline): ask `[PASS]`, `[FAIL]`, or `[SKIP reason]`
- For Section B (deployment): provide the exact command, ask the human to run it,
  then confirm the result
- For Section C (live telemetry): name the **exact notebook tile** to check, note
  whether it is a `[COMPARE]` tile (both DEV-{PREV} and DEV-{CURR} expected), and
  ask for the result

Keep a running tally in memory. Only proceed to the next item after recording
the current item's result.

### Tile navigation hints

Tell the human to open the notebook at the URL from Phase 3. The tiles are
grouped by test theme matching the checklist sections. Within each group tiles
appear in checklist order.

For `[COMPARE]` tiles, both series must be visible. If only one series appears,
it likely means the other environment has not completed a run yet — ask the
human to wait and refresh.

### Handling failures

When a test fails:

1. Ask the human to describe what they see
2. Suggest the most likely investigation steps (e.g. check logs for that plugin,
   verify the Snowflake view exists, check task is not suspended)
3. Record the failure with a brief note
4. Continue to the next item — do not block the session on a single failure

---

## Phase 5 — QA Signoff

Generate the result summary table:

```text
Section                  | Pass | Fail | Skip | Total
-------------------------|------|------|------|------
A — Offline              |      |      |      |  12
B — Deployment           |      |      |      |  15
C1 — Data Volume         |      |      |      |   8
C2 — Metrics             |      |      |      |  16
C3 — Logs                |      |      |      |   8
C4 — Spans               |      |      |      |  13
C5 — Events              |      |      |      |  10
C6 — Active Queries      |      |      |      |   4
C7 — Shares              |      |      |      |   4
C8 — Plugin Lifecycle    |      |      |      |   4
C9 — OpenPipeline        |      |      |      |   6
C10 — Obfuscation        |      |      |      |   3
C11 — Signal Protection  |      |      |      |   2
Total                    |      |      |      | 105
```

List all failed and skipped items with the human's notes.

Generate the signoff line:

```text
DSOA {CURR_VERSION} QA — {DATE} — {PASS}/{TOTAL} items passed
Tester: {human name or "QA"}
Notebook: {NOTEBOOK_URL}
```

### Write the markdown report

Always write the full results to a file (do not just offer — write it):

```bash
mkdir -p test/qa/results
# file: test/qa/results/qa-{CURR_VERSION}-{YYYYMMDD}.md
```

The report file must have the following structure:

```markdown
# DSOA {CURR_VERSION} QA Report — {DATE}

**Tester:** {NAME}
**Notebook:** [{NOTEBOOK_URL}]({NOTEBOOK_URL})
**Environment:** DEV-{CURR_TAG} vs DEV-{PREV_TAG}
**Tenant:** {TENANT_ADDR}
**ORGADMIN:** {true / false}

## Signoff

> DSOA {CURR_VERSION} QA — {DATE} — {PASS}/{TOTAL} items passed ({DEFERRED} deferred)
> Deferred: C2.15, C2.16, C4.13 — re-verify after data latency window

## Auto-Evaluation (AI)

[Paste consolidated auto-eval table from Phase 3.5 here]

Auto-evaluated: {N}/57 — {n} passed, {f} failed, {s} skipped

## Section Results

| Section                  | Pass | Fail | Skip | Total |
|--------------------------|------|------|------|-------|
| A — Offline              |      |      |      |  12   |
| B — Deployment           |      |      |      |  15   |
| C1 — Data Volume         |      |      |      |   8   |
| C2 — Metrics             |      |      |      |  16   |
| C3 — Logs                |      |      |      |   8   |
| C4 — Spans               |      |      |      |  13   |
| C5 — Events              |      |      |      |  10   |
| C6 — Active Queries      |      |      |      |   4   |
| C7 — Shares              |      |      |      |   4   |
| C8 — Plugin Lifecycle    |      |      |      |   4   |
| C9 — OpenPipeline        |      |      |      |   6   |
| C10 — Obfuscation        |      |      |      |   3   |
| C11 — Signal Protection  |      |      |      |   2   |
| **Total**                |      |      |      | **105**|

## Failures and Skips

### Failed items

- **{ID}** — {title}: {human's note}

### Skipped items

- **{ID}** — {title}: {reason}

## Notes

{any additional observations from the QA session}
```

---

## Helper Reference

### Version-to-tag algorithm (bash)

```bash
version_to_tag() {
    local version="$1"
    local minor patch
    minor=$(echo "$version" | cut -d. -f2)
    patch=$(echo "$version" | cut -d. -f3)
    printf "%03d" $(( minor * 10 + patch ))
}
```

Examples: `0.9.4` → `094` | `0.9.3.1` → `093` | `0.9.10` → `100`

### DQL semantics — `dsoa.run.plugin` vs `dsoa.run.context`

These two attributes have **distinct meanings** and must never be used
interchangeably in DQL queries:

| Attribute         | Meaning                                                   | Example values                         |
|-------------------|-----------------------------------------------------------|----------------------------------------|
| `dsoa.run.plugin` | The **plugin** that emitted the telemetry                 | `"shares"`, `"query_history"`          |
| `dsoa.run.context`| The specific **context** (sub-task) within a plugin run   | `"inbound_shares"`, `"outbound_shares"`, `"shares"` |

**Rule:** Use `dsoa.run.plugin` when filtering for all telemetry produced by a
plugin regardless of which context within that plugin emitted it.
Use `dsoa.run.context` only when you need to target a specific named context.

Some plugins have a single context whose name matches the plugin name — in that
case both filters return the same data. However, you **must still use
`dsoa.run.plugin`** when the intent is to select by plugin, to keep semantics
correct and future-proof against the plugin gaining additional contexts.

**Example — correct (shares events from any context):**

```dql
fetch events
| filter dsoa.run.plugin == "shares"
```

**Example — correct (shares logs from specific inbound/outbound contexts):**

```dql
fetch logs
| filter in(dsoa.run.context, {"inbound_shares", "outbound_shares"})
```

**Example — wrong (uses context instead of plugin for a plugin-level query):**

```dql
fetch events
| filter dsoa.run.context == "shares"   // WRONG — should be dsoa.run.plugin
```

### B2 — Manual agent invocation

For B2 (manual execution test), call `DTAGENT` **once per plugin** using separate
`CALL APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'))` statements — one for each plugin.
**Never** call with all plugins in a single `ARRAY_CONSTRUCT` — the `snow sql`
CLI has a hard 2-minute timeout and a full 16-plugin run will always exceed it.

The commented call template in `src/dtagent.sql/agents/700_dtagent.sql` already
contains the correct separate-call form. Run each line individually:

```sql
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
call APP.DTAGENT(ARRAY_CONSTRUCT('active_queries'));
call APP.DTAGENT(ARRAY_CONSTRUCT('budgets'));
-- ... one per plugin ...
call APP.DTAGENT(ARRAY_CONSTRUCT('warehouse_usage'));
```

**Pre-requisite — `snow sql` timeout configuration (MANDATORY):**
Before running B2, ensure the connection profile in `~/.snowflake/config.toml`
has both timeout values set to at least 300 seconds (5 minutes) to handle cold
starts on data-heavy plugins:

```toml
[connections.snow_agent_dev-{CURR_TAG}]
# ... existing settings ...
login_timeout = 300
network_timeout = 300
```

`login_timeout` covers the initial connection handshake; `network_timeout` covers
query execution. Both are needed. Without these, the CLI silently cuts off at
~120 seconds and returns no output or error.

Run each plugin call via:

```bash
snow sql -c snow_agent_dev-{CURR_TAG} \
    --role DTAGENT_{TAG}_OWNER \
    --warehouse DTAGENT_{TAG}_WH \
    --database DTAGENT_{TAG}_DB \
    --schema APP \
    -q "call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'));"
```

After all calls, verify telemetry arrives by checking for recent FINISHED
biz events per plugin:

```dql
fetch bizevents, from: now()-30m
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.task.exec.status == "FINISHED"
| summarize count = count(), by: {dsoa.task.name}
| sort dsoa.task.name asc
```

All 16 plugins should appear with count >= 1. Any missing plugin is a FAIL.

**Note on `dsoa.task.name` format:** Some plugins (e.g. `snowpipes`) are invoked
with individual contexts using the `$plugin:$context` format, e.g.
`"snowpipes:snowpipes"` or `"snowpipes:snowpipes_copy_history,snowpipes_usage_history"`.
This is correct and expected — do not flag these as malformed.

### Notebook tile format notes

**Markdown tiles** — use the `markdown:` key (NOT `text:`). The `text:` key is
silently ignored by Dynatrace; the rendered content comes from `markdown:`.

```yaml
- id: my-markdown-tile
  type: markdown
  markdown: |
    ## Section heading

    Some **bold** description.
```

**DQL tiles** — always include `showInput: false` to hide the code by default.

| Path | Purpose |
|---|---|
| `src/dtagent/version.py` | Source of truth for current version |
| `conf/config-dev-{TAG}.yml` | Per-environment configuration |
| `test/qa/RELEASE-CHECKLIST.md` | Full checklist with all items |
| `test/qa/test-suite/test-suite.yml` | Notebook YAML template |
| `scripts/test/deploy_test_notebook.sh` | Notebook deploy script |
| `scripts/test/test_deploy_flags_manual.sh` | Manual test script for deploy.sh flag parsing (no Snowflake required) |
| `test/qa/results/` | QA result files (create as needed) |

### Deploy commands quick reference

```bash
# Deploy both environments (fresh) — human only on dev-* profiles (requires DTAGENT_TOKEN)
./scripts/deploy/deploy.sh --env=dev-{CURR_TAG} --scope=all --options=skip_confirm
./scripts/deploy/deploy.sh --env=dev-{PREV_TAG} --scope=all --options=skip_confirm

# test-qa: AI can and must use --scope=all
./scripts/deploy/deploy.sh --env=test-qa --scope=all --options=skip_confirm

# AI-safe re-deploy on dev-* profiles (no token needed) — plugins + agents + config only
./scripts/deploy/deploy.sh --env=dev-{CURR_TAG} --scope=plugins,agents,config --options=skip_confirm

# Config-only update (no SQL changes)
./scripts/deploy/deploy.sh --env=dev-{CURR_TAG} --scope=config --options=skip_confirm

# Deploy the test notebook
./scripts/test/deploy_test_notebook.sh \
    --curr-version={CURR_VERSION} \
    --prev-version={PREV_VERSION}

# Preview notebook deploy without applying
./scripts/test/deploy_test_notebook.sh --dry-run

# Run manual deploy flag tests (no Snowflake connection required)
bash scripts/test/test_deploy_flags_manual.sh
```

**CRITICAL — scope rules for AI-assisted deploys:**
- On **`test-qa`**: the AI has full DTAGENT access and must use `--scope=all` for
  fresh deployments — this is required and correct.
- On **`dev-*` profiles**: `--scope=all` requires `DTAGENT_TOKEN` env-var (sends
  deployment biz events). The AI does not have this token on dev profiles. Use
  `--scope=plugins,agents,config` instead for AI-run deploys on dev environments.
- Always `build.sh` first if build artifacts are missing — deploy will error with
  `Build file missing: build/...`.

### Deploy log monitoring

Never let deploy output stream directly to the tool — the log is very large and will
cause tool aborts. Always background the process and tail the log:

```bash
./scripts/deploy/deploy.sh --env=dev-{CURR_TAG} --scope=all --options=skip_confirm \
    > /tmp/deploy-{CURR_TAG}.log 2>&1 &
# then poll:
sleep 30 && ps -p $PID && tail -10 /tmp/deploy-{CURR_TAG}.log
```

**Key strings to grep for in deploy logs:**

| String | Meaning |
|---|---|
| `Filtering out disabled plugins: ...` | Which plugins were excluded |
| `UPDATE_FROM_CONFIGURATIONS \| OK` | Config applied successfully |
| `successfully created` / `successfully resumed` | Tasks are live |
| `^ERROR:` | Fatal deploy error |

**Note:** `snow sql` garbles wide-table output (`SHOW TASKS`, `TASK_HISTORY`).
Never use these to verify task state — use deploy log evidence instead.

### B-section deployment scenarios (B8–B10)

These tests use `conf/config-dev-{CURR_TAG}.yml` changes + redeploy on the current
environment. The AI updates the config file; the human runs the deploy (or the AI
runs `--scope=plugins,agents,config` if no token is needed).

**Always restore the config to a clean state after each B8–B10 scenario** before
the next one. A fresh `--scope=all` (by the human) is the safest restore path.

#### B8 — Selected plugins only

Config pattern:

```yaml
plugins:
  disabled_by_default: true
  deploy_disabled_plugins: false
  query_history:
    is_enabled: true
  data_volume:
    is_enabled: true
  shares:
    is_enabled: true
```

Deploy: `--scope=all` (human). Verify:
- Deploy log shows `Filtering out disabled plugins: <13 plugins>`
- Trigger enabled tasks manually: `EXECUTE TASK DTAGENT_{TAG}_DB.APP.TASK_DTAGENT_QUERY_HISTORY;` etc.
- DQL: zero telemetry from any non-enabled plugin over last 15 min.

#### B9 — Config-only update

Make a non-structural config change (e.g. `log_level: DEBUG` → `INFO`).
Deploy: `--scope=config` only (AI can run this). Verify:
- No `CREATE PROCEDURE` / `CREATE VIEW` / `CREATE TASK` in deploy log.
- `UPDATE_FROM_CONFIGURATIONS` → `OK`.
- New value confirmed in Snowflake: `SELECT PATH, VALUE FROM CONFIG.CONFIGURATIONS WHERE PATH = 'core.log_level';`
- Trigger tasks and confirm FINISHED biz events still appear.

#### B10 — Disabled plugin not callable

Remove a previously-enabled plugin from config (e.g. remove `shares: is_enabled: true`).
Deploy: `--scope=all` (human) or `--scope=plugins,agents,config` (AI).

**Correct verification method:** Call the agent directly for the disabled plugin:

```bash
snow sql -c snow_agent_dev-{CURR_TAG} \
    --role DTAGENT_{TAG}_OWNER \
    --warehouse DTAGENT_{TAG}_WH \
    --database DTAGENT_{TAG}_DB \
    --schema APP \
    -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('shares'));"
```

Expected result: `"not_implemented"` — the plugin code is excluded from the DTAGENT
procedure at compile time. **Do not check for absent SQL objects** — the deploy does
not DROP pre-existing views or tasks; enforcement is at the Python code level inside
the stored procedure.

Confirm no telemetry from the plugin in the 5 minutes after deploy:

```dql
fetch logs, from: now()-5m
| filter deployment.environment == "DEV-{CURR_TAG}"
| filter dsoa.run.plugin == "shares"
| filter dsoa.run.context != "self_monitoring"
| summarize count = count()
```

Pass: count == 0.

#### B11 — LOG_EVENT_LEVEL BCR adaptation (Snowflake BCR 2026_02)

This test verifies that the `LOG_EVENT_LEVEL` BCR adaptation runs correctly
on accounts that support the parameter, and falls back gracefully on those
that do not.

1. **Full redeploy** to `test-qa` to exercise both `002_init_db.sql` and
   `009_event_log_init.sql`:

   ```bash
   ./scripts/dev/build.sh && \
   ./scripts/deploy/deploy.sh test-qa \
       --scope=init,plugins,config \
       --options=skip_confirm
   ```

1. **Verify `LOG_EVENT_LEVEL` set at account level** — only applicable when
   DSOA provisions and owns the event table (i.e. `EVENT_TABLE` points to
   `DTAGENT_DB.STATUS.EVENT_LOG`). First confirm ownership:

   ```sql
   SHOW PARAMETERS LIKE 'EVENT_TABLE' IN ACCOUNT;
   ```

   If `value = DTAGENT_DB.STATUS.EVENT_LOG`, DSOA owns the event table —
   proceed with the account-level check below. If it points elsewhere (custom
   or Snowflake-managed table), skip this step and step 4; the account-level
   parameter is intentionally left to the operator in that scenario.

   ```sql
   SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL' IN ACCOUNT;
   ```

   **Expected (DSOA-owned event table):** one row with `name = LOG_EVENT_LEVEL`
   and `value = INFO`.
   If the parameter does not exist, the account predates BCR 2026_02 — the
   fallback path is active; skip steps 3 and 4 and record as SKIP (pre-BCR).

1. **Verify `LOG_EVENT_LEVEL` set at database level**:

   ```sql
   SHOW PARAMETERS LIKE 'LOG_EVENT_LEVEL' IN DATABASE DTAGENT_DB;
   ```

   **Expected:** `value = INFO`.

1. **Verify privilege was granted to DTAGENT_VIEWER**:

   ```sql
   SHOW GRANTS TO ROLE DTAGENT_VIEWER;
   ```

   **Expected:** a row with `privilege = MODIFY LOG EVENT LEVEL` and
   `granted_on = ACCOUNT`.

1. **Verify event_log plugin collects telemetry** — wait ~2 minutes after
   deploy, then check Dynatrace:

   ```dql
   fetch logs, from: now()-10m
   | filter deployment.environment == "test-qa"
   | filter dsoa.run.plugin == "event_log"
   | summarize count = count()
   ```

   **Expected:** count > 0. If count == 0, trigger the plugin manually:

   ```bash
   snow sql -c snow_agent_test-qa \
       --role DTAGENT_OWNER \
       --warehouse DTAGENT_WH \
       --database DTAGENT_DB \
       --schema APP \
       -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('event_log'));"
   ```

   Then re-run the DQL check.

**Pass criteria:**

- BCR-capable account: all four SQL checks pass + telemetry count > 0.
- Pre-BCR account: steps 2–4 skipped (parameter absent), telemetry count > 0.

#### B12 — `disabled_by_default: true` config-only redeploy (BDX-1944 / BDX-1905)

From a B1 baseline (all plugins deployed and running):

1. Add `plugins.disabled_by_default: true` to `conf/config-test-qa.yml`.

2. **Config-only redeploy** (AI can run this):

   ```bash
   ./scripts/deploy/deploy.sh test-qa --scope=config --options=skip_confirm
   ```

3. **Verify ALL plugin tasks are suspended** — wait ~60 seconds then:

   ```bash
   snow sql -c snow_agent_test-qa \
       --role DTAGENT_OWNER \
       --database DTAGENT_DB \
       --schema APP \
       -q "SHOW TASKS IN DATABASE DTAGENT_DB;"
   ```

   **Expected:** Every `TASK_DTAGENT_*` task shows `state = suspended`.
   Zero tasks should be in `started` state.

4. **DQL confirmation** — wait for next scheduled task run (up to 5 min), then:

   ```dql
   fetch bizevents, from: now()-10m
   | filter deployment.environment == "test-qa"
   | filter dsoa.run.context == "self_monitoring"
   | filter dsoa.task.exec.status == "STARTED"
   | summarize count = count()
   ```

   **Expected:** count == 0 (no new task executions after suspension).

5. Restore config (`plugins.disabled_by_default: false`) and run `--scope=config`
   redeploy to resume tasks before the next scenario.

**Pass criteria:** All tasks suspended after config-only redeploy; no new STARTED
BizEvents within 10 minutes of suspension.

---

#### B13 — Interactive deploy wizard (BDX-1969)

1. Move the existing config aside:

   ```bash
   mv conf/config-test-qa.yml conf/config-test-qa.yml.bak
   ```

2. Run the wizard with scripted stdin answers:

   ```bash
   echo -e "test-qa\nmy_account\nmy_user\nmy_warehouse\nmy_database\nmy_schema\nmy_tenant\nmy_token\n" \
     | ./scripts/deploy/deploy.sh test-qa --interactive
   ```

   Adjust the echo values to match valid Snowflake and Dynatrace settings for
   the test-qa account.

3. **Verify config was generated:**

   ```bash
   test -f conf/config-test-qa.yml && yamllint conf/config-test-qa.yml \
     && echo "PASS: config valid" || echo "FAIL: config missing or invalid"
   ```

4. **Verify deployment proceeds** — the wizard should call `deploy.sh` after
   generating the config. Check that the deploy log shows no fatal errors.

5. Restore original config:

   ```bash
   mv conf/config-test-qa.yml.bak conf/config-test-qa.yml
   ```

**Pass criteria:** Wizard generates a valid `yamllint`-passing config; deployment
proceeds without fatal errors.

---

#### B14 — Non-admin deployment path (BDX-1992)

Tests that `query_history` plugin still captures warehouse queries via the
non-admin fallback when `roles.admin: "-"` is set.

1. Set `roles.admin: "-"` in `conf/config-test-qa.yml` to disable admin role.

2. **Full redeploy:**

   ```bash
   ./scripts/deploy/deploy.sh test-qa --scope=all --options=skip_confirm
   ```

3. **Trigger `query_history` manually:**

   ```bash
   snow sql -c snow_agent_test-qa \
       --role DTAGENT_OWNER \
       --warehouse DTAGENT_WH \
       --database DTAGENT_DB \
       --schema APP \
       -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));"
   ```

4. **Verify telemetry:**

   ```dql
   fetch spans, from: now()-15m
   | filter deployment.environment == "test-qa"
   | filter dsoa.run.plugin == "query_history"
   | summarize count = count()
   ```

   **Expected:** count > 0 (non-admin path captures warehouse queries via
   `P_MONITOR_WAREHOUSES` fallback procedure).

5. Restore `roles.admin` to its original value and redeploy.

**Pass criteria:** query_history telemetry > 0 when admin role is disabled.

---

#### B15 — Install completeness check (BDX-714)

After a fresh B1 deployment:

1. Run `--scope=verify`:

   ```bash
   ./scripts/deploy/deploy.sh test-qa --scope=verify --options=skip_confirm
   ```

2. **Verify output:**
   - All expected Snowflake objects reported as present
   - Installed version matches `src/dtagent/version.py` VERSION
   - No "MISSING" or "MISMATCH" lines in output
   - Exit code 0

**Pass criteria:** `--scope=verify` exits 0 and reports all objects present with
matching version.

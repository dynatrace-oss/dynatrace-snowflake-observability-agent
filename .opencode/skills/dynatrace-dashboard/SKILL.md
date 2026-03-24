---
name: dynatrace-dashboard
description: Create and update Dynatrace dashboards for DSOA telemetry
license: MIT
compatibility: opencode
metadata:
  audience: developers
---

# Skill: Dynatrace Dashboard Creation and Deployment

Use this skill to create, update, convert, and deploy Dynatrace dashboards
for DSOA telemetry visualisation.

## File Locations

| Artefact               | Path                                                    |
|------------------------|---------------------------------------------------------|
| Dashboard YAML source  | `docs/dashboards/<dashboard-name>/<dashboard-name>.yml` |
| Dashboard readme       | `docs/dashboards/<dashboard-name>/readme.md`            |
| Screenshot placeholder | `docs/dashboards/<dashboard-name>/img/.gitkeep`         |
| Dashboards index       | `docs/dashboards/README.md`                             |
| Workflow YAML source   | `docs/workflows/<workflow-name>/<workflow-name>.yml`    |
| Workflow readme        | `docs/workflows/<workflow-name>/readme.md`              |

Dashboard names use a descriptive slug, not necessarily the plugin name,
since dashboards may span multiple plugins (e.g. `snowpipes-monitoring`,
`tasks-pipelines`, `budgets-finops`).

## Metric / Attribute Reference

Before writing any DQL query, consult the plugin's semantic dictionary:
```
src/dtagent/plugins/<plugin-name>.config/instruments-def.yml
```

This is the authoritative source for:
- Metric keys (e.g. `snowflake.pipe.files.pending`)
- Dimensions (e.g. `snowflake.pipe.name`, `db.namespace`)
- Log/event attributes
- Telemetry types (metrics, logs, events, bizevents, spans)

All DSOA telemetry carries these standard dimensions on every record:
- `db.system == "snowflake"`
- `deployment.environment` — Snowflake account identifier
- `dsoa.run.plugin` — plugin name (e.g. `"snowpipes"`)
- `dsoa.run.context` — context name (e.g. `"snowpipes_copy_history"`)

## DQL Rules (Lessons Learned)

These rules come from real debugging sessions — follow them strictly:

1. **Determine the actual telemetry type before writing any DQL.**
   DSOA plugins can emit logs, events, metrics, or bizevents — and the plugin
   source is the only authoritative answer. Before writing a tile query, check
   the plugin's `_log_entries()` call in `src/dtagent/plugins/<plugin>.py`:
   - No `report_timestamp_events=True` and no `event_payload_prepare` → **logs only** → use `fetch logs`
   - `report_timestamp_events=True` → timestamp events **in addition to** logs → use `fetch events` for event tiles
   - `report_all_as_events=True` → all rows as events → use `fetch events`
   - Metrics in `instruments-def.yml` with a metric key → use `timeseries`

   **Known emission types (verified):**
   - `tasks` plugin (`task_history`, `task_versions`, `serverless_tasks` contexts): **logs + metrics**
   - `dynamic_tables` plugin (`dynamic_tables`, `dynamic_table_refresh_history`, `dynamic_table_graph_history`): **logs + metrics**
   - `snowpipes` plugin: logs + events (timestamp events via `report_timestamp_events=True`)

2. **No `fetch metrics` for DSOA data.** DSOA does not use the standard
   Dynatrace metric ingestion pipeline. Use `timeseries` with a metric key
   from `instruments-def.yml`, or `fetch logs` for log-based aggregations.

3. **`timeseries` requires all filter dimensions in the `by:` clause.**
   If you filter on `deployment.environment` after `timeseries`, it must
   also appear in `by: { ..., deployment.environment }`.

4. **`percentile()` does not support iterative expressions from `timeseries`.**
   Instead of:
```dql
   timeseries v = avg(metric), by: { dim }
   | summarize { p95 = percentile(v[], 95) }
```
   Use `fetch logs` with `percentile()` directly, or use `summarize` with
   `avg()` / `max()` which do support array aggregation.

5. **Honeycomb tiles need scalar values, not timeseries arrays.**
   Use `fetch logs | summarize ... by: { dim }` — not `timeseries`.

6. **Variable filters after `timeseries` must use `array()` wrapper:**
```dql
   timeseries v = sum(metric), by: { snowflake.pipe.name, deployment.environment }
   | filter in(deployment.environment, array($Accounts))
   | filter in(snowflake.pipe.name, array($Pipe))
```

7. **`$Variable` in threshold expressions needs `toDouble()`:**
```dql
   | filter value > toDouble($Threshold_Latency_Warning)
```

8. **Pipe/task/table status is a string dimension, not a numeric metric.**
   Query it from logs via `fetch logs | summarize`, not from a metric series.

9. **`dtctl auth login` can be run by the AI agent** — it opens a browser tab
   for OAuth. Run it whenever `dtctl apply` returns a token/auth error.

## YAML Dashboard Format
```yaml
# DASHBOARD: <Human-readable title>
# DESCRIPTION: <One-line description>
# OWNER: DSOA Team
# PLUGINS: <comma-separated plugin names>
# TAGS: snowflake, dsoa, <domain>

version: 15

variables:
  - key: Accounts
    type: query
    input:
      query: |
        fetch logs
        | filter db.system == "snowflake"
        | filter dsoa.run.plugin == "<plugin>"
        | fields deployment.environment
        | dedup deployment.environment
        | sort deployment.environment asc
    defaultValue: "*"
  # ... additional variables

tiles:
  "0":
    title: ""
    type: markdown
    content: |
      ## Section Title
      Description of this section.

  "1":
    title: Tile Title
    type: data
    query: |
      fetch logs
      | filter db.system == "snowflake"
      | ...
    visualization: singleValue   # singleValue | lineChart | barChart | honeycomb | table
    visualizationSettings:
      singleValue:
        label: "Label"
        # colorThresholds: [{value: 0, color: "red"}, {value: 1, color: "green"}]
    querySettings:
      timeframe: now-2h
    davis:
      enabled: false

layouts:
  "0": {x: 0, y: 0, w: 24, h: 2}
  "1": {x: 0, y: 2, w: 6, h: 4}
  # ... grid uses 24 columns

settings:
  autoRefresh:
    enabled: true
    interval: 300

annotations: {}
```

## YAML → JSON Conversion

**Always convert before uploading.** The project provides a conversion script:
```bash
./scripts/tools/yaml-to-json.sh docs/dashboards/<name>/<name>.yml > /tmp/<name>.json
```

Validate the JSON before uploading:
```bash
jq . /tmp/<name>.json > /dev/null && echo "JSON valid" || echo "JSON INVALID"
```

For workflows, the same script applies:
```bash
./scripts/tools/yaml-to-json.sh docs/workflows/<name>/<name>.yml > /tmp/<name>.json
```

## Deploying with dtctl

Use `dtctl apply` to create or update dashboards and workflows.
Always use `-A` for structured agent-friendly output.

### Create new dashboard (no ID in file):
```bash
dtctl apply -A -f /tmp/<name>.json
```

The response will include the assigned dashboard ID. **Record this ID** and add
it to the YAML file as a top-level `id:` field so future runs update rather than
create a duplicate.

### Update existing dashboard (ID already in file):
```bash
dtctl apply -A -f /tmp/<name>.json
```

`dtctl apply` is idempotent: if the ID exists it updates, otherwise it creates.

### Preview changes before applying:
```bash
dtctl apply -A --dry-run -f /tmp/<name>.json
```

### Show what changed:
```bash
dtctl apply -A --show-diff -f /tmp/<name>.json
```

### Get current dashboard for round-trip edit:
```bash
dtctl get dashboard <id> -o yaml > /tmp/<name>-current.yaml
```

### Workflows follow the same pattern:
```bash
dtctl apply -A -f /tmp/<name>-workflow.json
```

## Full Deployment Sequence

> **CRITICAL:** The pre-flight check and Phase A are mandatory blocking gates.
> Do NOT proceed to Phase B until live data is confirmed flowing.
> A dashboard deployed against an empty dataset cannot be validated and is not done.

```
=== PRE-FLIGHT: Verify DSOA is Installed on test-qa ===

0.  Before ANY other step, confirm DSOA is installed in the target environment.
    The connection profile's default role may not have visibility into DTAGENT
    databases, so always check using the owner role explicitly:

      snow sql -c snow_agent_test-qa -q "USE ROLE DTAGENT_QA_OWNER; SHOW DATABASES LIKE 'DTAGENT%'"

    Expected: at least one row (e.g. DTAGENT_QA_DB).

    If the result is empty ("No data"), DSOA has never been installed there.
    STOP immediately and tell the user:

      "DSOA is not installed on test-qa. A human must run the base installation
       first using the privileged scopes (init, admin, all). These scopes create
       roles, databases, and warehouses and must NEVER be run by an AI agent.
       Please run:
         ./scripts/deploy/deploy.sh test-qa --scope=all --options=skip_confirm
       Then come back and I will continue."

    !! IMPORTANT: NEVER run --scope=all, init, admin, or apikey yourself.
    These scopes create or modify roles, databases, warehouses, API integrations,
    and other account-level objects. They are HUMAN-ONLY operations.
    The AI agent is only permitted to run --scope=plugins,config (and agents
    when python code changes). Always stop and ask the human to run privileged
    scopes, then wait for confirmation before proceeding.

    Do NOT attempt to deploy plugins,config or write synthetic SQL until the
    base install is confirmed. The role DTAGENT_QA_OWNER and database
    DTAGENT_QA_DB must exist before any scoped deployment can succeed.

=== PHASE A: Synthetic Data Setup (snowflake-synthetic skill) ===

1.  Read instruments-def.yml for all relevant plugins — confirm exact field names
    and which dsoa.run.context values each tile will query.

2.  Write test/tools/setup_test_<plugin>.sql covering every dashboard tile's
    data requirements. Apply it:
      snow sql --connection snow_agent_test-qa -f test/tools/setup_test_<plugin>.sql

3.  Verify synthetic objects exist and grants are in place:
      snow sql --connection snow_agent_test-qa -q "SHOW <OBJECTS> IN SCHEMA DSOA_TEST_DB.<PLUGIN>;"
      snow sql --connection snow_agent_test-qa -q "SHOW GRANTS TO ROLE DTAGENT_QA_VIEWER;" | grep DSOA_TEST_DB

4.  Enable required plugins in conf/config-test-qa.yml (is_enabled: true, scoped
    to DSOA_TEST_DB). Rebuild and redeploy DSOA:
      ./scripts/dev/build.sh
      ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

5.  Wait for at least one DSOA collection cycle, then confirm data is flowing
    via a spot-check DQL query through the MCP server or dtctl query. Do NOT
    proceed until records are returned. Fast plugins: ~5 min. Deep plugins: ~1-2 h.

=== PHASE B: Dashboard Authoring and Deployment ===

6.  Write dashboard YAML in docs/dashboards/<name>/<name>.yml
7.  Convert:  ./scripts/tools/yaml-to-json.sh ... > /tmp/<name>.json
8.  Validate: jq . /tmp/<name>.json
9.  Deploy:   dtctl apply -A -f /tmp/<name>.json
10. Record the returned ID — add it to the YAML as `id: <uuid>`
11. Re-convert and re-deploy with ID so subsequent runs update in place
12. Verify every tile renders real data in the Dynatrace UI

=== PHASE C: Documentation ===

13. Write docs/dashboards/<name>/readme.md  (see dashboard-docs skill)
14. Update docs/dashboards/README.md index
15. Request screenshots (see dashboard-docs skill)
```

## Dynatrace MCP Server

The `dt-oss-aym-mcp` MCP server can be used as a reference to:
- Inspect existing dashboards and workflows
- Run DQL queries to validate metric availability before writing tiles
- Check what data is actually present for a given `deployment.environment`

Prefer `dtctl` for create/update operations (it is faster and more scriptable).
Use the MCP server for read/query/exploration.

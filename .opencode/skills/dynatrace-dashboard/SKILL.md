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

3. **Prefer `filter: {}` over post-pipe `| filter` for `timeseries` dimension filtering.**
   Inline filters inside `filter: {}` are applied before data is split by `by:`, so you
   avoid creating unnecessary series for dimensions you then immediately discard. Only
   dimensions used for *display grouping* should appear in `by:`.
   Post-pipe `| filter` is still required for dimensions that are in `by:` but not
   filterable inline (e.g. computed fields), but avoid it for raw dimension variables.

   For variable-driven dimension filters inside `filter: {}`, use `in()` with
   `array($Var)` — this works inside the `filter:` block as of DQL 1.38:

```dql
   timeseries v = sum(metric), by: { snowflake.task.name, deployment.environment }
   , filter: {
       db.system == "snowflake" and
       in(deployment.environment, array($Accounts)) and
       in(db.namespace, array($Database))
     }
```

   **Null-or-match pattern for optional dimensions:** Some records legitimately have
   `NULL` for a dimension (e.g. Snowflake-internal serverless tasks have no
   `db.namespace`). If you filter strictly with `in()`, those records are silently
   dropped and cannot be seen even with the wildcard default. Use:

```dql
   (isNull(db.namespace) or in(db.namespace, array($Database))) and
   (isNull(snowflake.schema.name) or in(snowflake.schema.name, array($Schema)))
```

   This preserves unattributed records when the variable is set to wildcard (`*`),
   while still allowing the user to filter to a specific database/schema.

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

10. **All dashboard tiles must apply the same global variable filters consistently.**
    If a dashboard has `$Accounts`, `$Database`, `$Schema` (or similar) variables,
    every data tile must filter by all of them — not just the ones that are "obviously
    relevant". Inconsistent filtering makes the dashboard feel broken (user selects a
    database and some tiles ignore it). If a telemetry context does not populate a
    dimension (e.g. `db.namespace` is empty for some records), still apply the filter —
    real user data will be populated and the wildcard default (`*`) will pass all records
    through anyway. For `timeseries` tiles, add the dimension to `by:` and then apply
    `| filter in(dim, array($Var))` after the `timeseries` step (rule 3 above).
    Document any known empty-field cases in the tile description or readme rather than
    silently dropping the filter.

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
    multiple: true
    # DO NOT set defaultValue: "*" — Dynatrace automatically adds "*" (select all)
    # as the first option for multi-select variables. Explicitly setting it creates
    # a duplicate and causes the literal string "*" to appear as a selected value,
    # which is NOT translated as "all" in DQL filters.
    # DO NOT add array("*", <var>) in the query for the same reason — DT handles it.
    input: |
      fetch logs
      | filter db.system == "snowflake"
      | filter dsoa.run.plugin == "<plugin>"
      | summarize collectDistinct(deployment.environment)
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

> **CRITICAL — MANDATORY GATES:** Steps 0 and A are hard blocking gates.
> You MUST complete them before writing a single line of YAML.
> Skipping them produces a dashboard that cannot be validated and is not done.
> These gates have been violated before — do not repeat the mistake.

```
=== GATE 0: Ask the user whether DSOA is deployed ===

!! THIS IS THE VERY FIRST THING TO DO — before reading any files, before writing
   any YAML, before doing anything else.

Ask the user this question (use the question tool):
  "Is DSOA already deployed and running on the target environment (e.g. test-qa)?
   If yes, is the <plugin> plugin already enabled?"

Possible outcomes:
  A) "Yes, deployed and plugin enabled" → skip to GATE A step 2
  B) "Yes, deployed but plugin not enabled" → proceed to GATE A step 4
  C) "No, not deployed" → STOP. Tell the user:
       "DSOA base installation must be done by a human first (privileged scopes).
        Please run:
          ./scripts/deploy/deploy.sh <env> --scope=all --options=skip_confirm
        Then come back and I will continue."
     Do NOT proceed until the user confirms deployment is done.

!! IMPORTANT: NEVER run --scope=all, init, admin, or apikey yourself.
   These scopes are HUMAN-ONLY. The AI agent may only run --scope=plugins,config
   (and agents when Python code changes).

=== GATE A: Synthetic Data Setup ===

!! THIS GATE IS MANDATORY. Do NOT write dashboard YAML until it is complete.
   A dashboard built against an empty dataset cannot be validated. It is not done.

1.  Read instruments-def.yml for all required plugins.
    Identify every metric, dimension, and attribute used by dashboard tiles.
    Identify which dsoa.run.context values correspond to each data area.

2.  Write test/tools/setup_test_<plugin>.sql (using the snowflake-synthetic skill).
    The script must cover EVERY tile's data requirements — every attribute,
    every metric, every edge case referenced in the dashboard YAML.
    Apply it:
      snow sql --connection snow_agent_<env> -f test/tools/setup_test_<plugin>.sql

3.  Verify synthetic objects exist and grants are correct:
      snow sql --connection snow_agent_<env> -q "SHOW <OBJECTS> IN SCHEMA DSOA_TEST_DB.<PLUGIN>;"
      snow sql --connection snow_agent_<env> -q "SHOW GRANTS TO ROLE DTAGENT_QA_VIEWER;" | grep DSOA_TEST_DB

4.  If plugin is not yet enabled: update conf/config-<env>.yml (is_enabled: true).
    Build and redeploy:
      ./scripts/dev/build.sh
      ./scripts/deploy/deploy.sh <env> --scope=plugins,config --options=skip_confirm

5.  Trigger a manual DSOA run to get telemetry immediately (bypasses the task
    scheduler — no need to wait for the next scheduled cycle):

    IMPORTANT: DSOA connection profiles intentionally leave role/database/warehouse
    blank (they may not exist yet at deploy time). You MUST pass them explicitly:

      snow sql --connection snow_agent_<env> \
        --role     DTAGENT_<TAG>_VIEWER \
        --database DTAGENT_<TAG>_DB \
        --warehouse DTAGENT_<TAG>_WH \
        -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('<plugin_name>'))"

    Where <TAG> matches the environment tag (e.g. QA for test-qa, DEV for dev-094).
    You can pass multiple plugins: ARRAY_CONSTRUCT('plugin_a', 'plugin_b')
    or omit the argument entirely to run ALL enabled plugins.

    IMPORTANT — plugin-specific latency caveats:
    - Most plugins: telemetry arrives in Dynatrace within ~1-2 min after the
      CALL returns.
    - query_history: ACCOUNT_USAGE.QUERY_HISTORY has a ~45 min ingestion lag
      in Snowflake. Even after CALL DTAGENT returns successfully, the log/span
      records for queries run by the simulation script will NOT be visible in
      Dynatrace until that lag clears. Plan ~45-60 min of wait time before
      verifying Section 4 (operator stats) tiles.
      Metrics and biz_events derived from ACCOUNT_USAGE share the same lag.
    - active_queries: reads INFORMATION_SCHEMA (real-time) — no lag.

    After the CALL returns, run a spot-check DQL to confirm records are flowing:
      fetch logs
      | filter db.system == "snowflake"
      | filter dsoa.run.plugin == "<plugin>"
      | filter deployment.environment == "<ENV>"
      | limit 10
    Do NOT proceed until records are returned.

=== PHASE B: Dashboard Authoring and Deployment ===

6.  Write dashboard YAML in docs/dashboards/<name>/<name>.yml
7.  Convert:  ./scripts/tools/yaml-to-json.sh ... > /tmp/<name>.json
8.  Validate: jq . /tmp/<name>.json
9.  Deploy:   dtctl apply -A -f /tmp/<name>.json
10. Record the returned ID — embed it in the YAML as `id: <uuid>`
11. Re-convert, inject id/name/type with python3, re-deploy to update in place:
      python3 -c "
      import json
      with open('/tmp/<name>.json') as f:
          d = json.load(f)
      d['id']   = '<uuid>'
      d['name'] = '<Human-readable title>'
      d['type'] = 'dashboard'
      with open('/tmp/<name>-apply.json', 'w') as f:
          json.dump(d, f)
      "
      dtctl apply -A -f /tmp/<name>-apply.json
12. Verify every tile renders real data in the Dynatrace UI.

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

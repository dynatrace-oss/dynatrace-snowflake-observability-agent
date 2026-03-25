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

11. **Always add `unitsOverrides` for every byte (data-size) metric field.**
    Dynatrace does not auto-detect byte units from metric keys — if you omit a
    `unitsOverrides` entry, values are rendered as raw numbers (e.g. `947121664`)
    instead of human-readable storage (e.g. `903.0 MiB`). The correct `unitCategory`
    for storage metrics is `"data"` (not `"data-information"`). Apply this to every
    output field that carries bytes — including intermediate computed fields like `v`
    that come from a `timeseries` step and are displayed in a bar chart or table:

    ```yaml
    unitsOverrides:
      - identifier: total_bytes   # the DQL field name, not the metric key
        unitCategory: data
        baseUnit: byte
        displayUnit: null
        decimals: 2
        suffix: ""
        delimiter: false
        added: 1                  # unique integer, use 1/2/3/... per tile
    ```

    For `timeseries` tiles that expose both a summarised field **and** the raw
    series array (`v`), add an override for each:

    ```yaml
    unitsOverrides:
      - identifier: size          # summarised / computed field
        unitCategory: data
        baseUnit: byte
        displayUnit: null
        decimals: 2
        suffix: ""
        delimiter: false
        added: 1
      - identifier: v             # raw timeseries array shown in chart hover
        unitCategory: data
        baseUnit: byte
        displayUnit: null
        decimals: null
        suffix: ""
        delimiter: false
        added: 2
    ```

    **Tiles that MUST have byte `unitsOverrides` in a data-volume dashboard:**
    - Any `singleValue` tile summing `snowflake.data.size`
    - Any `lineChart` / `barChart` showing `snowflake.data.size` or its aliases
    - Any `table` tile with a column derived from a byte metric

12. **`davis.componentState` must NOT appear on data tiles — only on markdown tiles.**
    The `davis` block shape differs by tile type:

    ```yaml
    # ✅ CORRECT — markdown tile
    type: markdown
    davis:
      componentState:
        inputData: null

    # ✅ CORRECT — data tile
    type: data
    davis:
      enabled: false
      davisVisualization:
        isAvailable: true

    # ❌ WRONG — data tile with componentState causes "unable to load" crash
    type: data
    davis:
      enabled: false
      davisVisualization:
        isAvailable: true
      componentState:        # ← DELETE THIS from all data tiles
        inputData: null
    ```

    A dashboard with `componentState` on any data tile shows "Something went wrong /
    We were unable to load this dashboard" — even if the JSON structure and queries
    are otherwise valid. Always verify after writing tiles: data tiles have exactly
    `enabled` + `davisVisualization`; markdown tiles have exactly `componentState`.

13. **`honeycomb` `dataMappings` is an object, not an array. Colouring goes in `coloring.colorRules`.**

    ```yaml
    # ✅ CORRECT
    visualizationSettings:
      honeycomb:
        shape: square
        legend:
          position: right
        dataMappings:
          value: state_code          # object with single key "value"
        displayedFields:
          - snowflake.task.name
          - state
        labels:
          showLabels: true
      coloring:
        colorRules:
          - color: "var(--dt-colors-charts-apdex-excellent-default, #2a7453)"
            colorMode: single-color
            comparator: "="
            field: state_code
            type: long               # "long" for numeric, "string" for text
            value: 1

    # ❌ WRONG — array dataMappings, thresholds at wrong level
    visualizationSettings:
      honeycomb:
        dataMappings:
          - valueField: state_code   # ← wrong: array with valueField/labelField/colorField
            labelField: name
            colorField: status
      thresholds:                    # ← wrong level: thresholds here crashes the dashboard
        - field: status
          rules: [...]
    ```

14. **`categoricalBarChart` axis fields are strings, not arrays.**

    ```yaml
    # ✅ CORRECT
    visualizationSettings:
      chartSettings:
        truncationMode: middle
        legend:
          hidden: true
        categoryOverrides: {}
        categoricalBarChartSettings:
          categoryAxis: snowflake.pipe.name    # string
          categoryAxisLabel: Pipe
          valueAxis: count                     # string
          valueAxisLabel: Count
      thresholds: []

    # ❌ WRONG — arrays crash the dashboard
    categoricalBarChartSettings:
      categoryAxis:
        - snowflake.pipe.name                  # ← must be a plain string
      valueAxis:
        - count
    ```

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

### CRITICAL: Correct JSON envelope format for dashboards

`dtctl apply` expects the **same envelope structure that `dtctl get` returns** —
not a flat JSON file. The correct shape is:

```json
{
  "id":   "<uuid>",
  "name": "<Dashboard Name>",
  "type": "dashboard",
  "content": { ...full dashboard JSON from YAML conversion... }
}
```

To produce this correctly from the YAML source:

```bash
./scripts/tools/yaml-to-json.sh docs/dashboards/<name>/<name>.yml > /tmp/inner.json

python3 -c "
import json
inner = json.load(open('/tmp/inner.json'))
# CRITICAL: pop id/name OUT of content — they belong only at envelope level.
# Leaving them inside content causes 'We were unable to load this dashboard.'
dashboard_id   = inner.pop('id')
dashboard_name = inner.pop('name')
envelope = {
    'id':      dashboard_id,
    'name':    dashboard_name,
    'type':    'dashboard',
    'content': inner
}
json.dump(envelope, open('/tmp/<name>-apply.json', 'w'), indent=2)
"

dtctl apply -A -f /tmp/<name>-apply.json
```

Verify after apply that `tiles count` is correct (not 0):

```bash
dtctl get dashboard <id> -o json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('tiles:', len(d.get('content',{}).get('tiles',{})))
"
```

If tiles count is 0 after apply, the envelope was wrong (flat file was passed
instead of the wrapped envelope). Rebuild the envelope and reapply.

**Critical rules:**
- `id` and `name` must be **popped** from `inner` before wrapping — they must appear at
  envelope level **only**. Leaving them inside `content` causes the dashboard to fail to
  load: "We were unable to load this dashboard."
- **Do NOT** pass the flat converted JSON directly to `dtctl apply` — that causes
  `dtctl` to wrap it a second time, producing an empty dashboard that fails to load.

### Create new dashboard (no ID in file):

For a brand-new dashboard, omit `id` from the envelope. `dtctl apply` assigns one:

```bash
python3 -c "
import json
inner = json.load(open('/tmp/inner.json'))
# pop id if present (it may not exist for new dashboards)
inner.pop('id', None)
dashboard_name = inner.pop('name')
envelope = {'name': dashboard_name, 'type': 'dashboard', 'content': inner}
json.dump(envelope, open('/tmp/<name>-apply.json', 'w'), indent=2)
"
dtctl apply -A -f /tmp/<name>-apply.json
```

The response will include the assigned dashboard ID. **Record this ID** and add
it to the YAML file as a top-level `id:` field so future runs update rather than
create a duplicate.

### Update existing dashboard (ID already in file):

Build the envelope as shown above (with `id` included) and apply:

```bash
dtctl apply -A -f /tmp/<name>-apply.json
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
7.  Convert:  ./scripts/tools/yaml-to-json.sh ... > /tmp/inner.json
8.  Validate: jq . /tmp/inner.json
9.  Build envelope and deploy (see "Deploying with dtctl" section above for the
    mandatory envelope-wrapping step — do NOT pass the flat JSON directly):
      python3 -c "import json; inner=json.load(open('/tmp/inner.json')); \
        json.dump({'name':inner['name'],'type':'dashboard','content':inner}, \
        open('/tmp/<name>-apply.json','w'))"
      dtctl apply -A -f /tmp/<name>-apply.json
10. Record the returned ID — add it to the YAML as `id: <uuid>`. Re-convert,
    rebuild envelope (this time with 'id' included), and re-deploy:
      dtctl apply -A -f /tmp/<name>-apply.json
11. Verify tiles: dtctl get dashboard <id> -o json | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print('tiles:',len(d.get('content',{}).get('tiles',{})))"
    Expected: tiles == 14 (or however many your dashboard has). If 0, envelope was wrong.
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

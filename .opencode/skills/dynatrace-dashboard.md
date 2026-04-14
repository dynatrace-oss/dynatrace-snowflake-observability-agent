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

```text
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

1. **No `fetch metrics` in Grail DQL.** Metric series are queried with
   `timeseries avg(metric.name), by: { dim }` — there is no `fetch metrics` command.
   For structured log/event data use `fetch logs`, `fetch events`, or `fetch bizevents`.
   Check `instruments-def.yml` for the correct telemetry type per signal.

2. **`timeseries` requires all filter dimensions in the `by:` clause.**
   If you filter on `deployment.environment` after `timeseries`, it must
   also appear in `by: { ..., deployment.environment }`.

3. **`percentile()` does not support iterative expressions from `timeseries`.**
   Instead of:

```dql
   timeseries v = avg(metric), by: { dim }
   | summarize { p95 = percentile(v[], 95) }
```

   Use `fetch logs` with `percentile()` directly, or use `summarize` with
   `avg()` / `max()` which do support array aggregation.

1. **Honeycomb tiles need scalar values, not timeseries arrays.**
   Use `fetch logs | summarize ... by: { dim }` or
   `fetch events | summarize ... by: { dim }` — not `timeseries`.

2. **Variable filters after `timeseries` must use `array()` wrapper:**

```dql
   timeseries v = sum(metric), by: { snowflake.pipe.name, deployment.environment }
   | filter in(deployment.environment, array($Accounts))
   | filter in(snowflake.pipe.name, array($Pipe))
```

1. **`$Variable` in threshold expressions needs `toDouble()`:**

```dql
   | filter value > toDouble($Threshold_Latency_Warning)
```

1. **Pipe status is a string dimension, not a numeric metric.**
   Query it from logs/events, not from a metric series.

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
    defaultValue: "<your-environment>"  # e.g. "PROD", "DEV" — must match a value the query returns
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

**Critical:** `dtctl apply` expects a specific envelope structure. The YAML-to-JSON
conversion produces the inner dashboard content; you must wrap it before applying.
`id` and `name` must appear **only at the envelope level** — never inside `content`.
Leaving them inside `content` causes the dashboard to fail to load ("We were unable
to load this dashboard") or returns `tiles: 0`.

### Step-by-step: deploy a dashboard

```bash
# 1. Convert YAML to JSON (produces the inner content)
./scripts/tools/yaml-to-json.sh docs/dashboards/<name>/<name>.yml > /tmp/inner.json

# 2. Wrap in the dtctl envelope
#    Pop id/name OUT of content — they belong only at envelope level.
python3 -c "
import json
inner = json.load(open('/tmp/inner.json'))
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

# 3. Validate
jq . /tmp/<name>-apply.json > /dev/null && echo "JSON valid"

# 4. Apply
dtctl apply -A -f /tmp/<name>-apply.json

# 5. Verify tiles were stored (should match tile count in YAML, not 0)
dtctl get dashboard <id> -o json | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('tiles:',len(d.get('content',{}).get('tiles',{})))"
```

The response includes the assigned dashboard ID. **Record it** and add it to the
YAML as a top-level `id:` field so subsequent runs update rather than create duplicates.

### On first create (no ID yet)

Omit `id` from the YAML. After the first deploy, `dtctl apply` returns the new ID —
add it to the YAML, re-convert, and re-deploy once to make future runs idempotent.

### Preview / diff before applying

```bash
dtctl apply -A --dry-run   -f /tmp/<name>-apply.json
dtctl apply -A --show-diff -f /tmp/<name>-apply.json
```

### Get current dashboard for round-trip edit

```bash
dtctl get dashboard <id> -o yaml > /tmp/<name>-current.yaml
```

### Workflows follow the same pattern

```bash
./scripts/tools/yaml-to-json.sh docs/workflows/<name>/<name>.yml > /tmp/inner.json
# wrap with type: "workflow" instead of "dashboard", then:
dtctl apply -A -f /tmp/<name>-workflow-apply.json
```

## Full Deployment Sequence

```text
1.  Read instruments-def.yml for all relevant plugins
2.  Write dashboard YAML in docs/dashboards/<name>/<name>.yml
3.  Convert:  ./scripts/tools/yaml-to-json.sh ... > /tmp/inner.json
4.  Wrap:     python3 envelope script above  → /tmp/<name>-apply.json
5.  Validate: jq . /tmp/<name>-apply.json
6.  Deploy:   dtctl apply -A -f /tmp/<name>-apply.json
7.  Record the returned ID — add it to the YAML as `id: <uuid>`
8.  Re-convert, re-wrap, re-deploy with ID so subsequent runs update in place
9.  Verify:   dtctl get dashboard <id> ... | check tile count > 0
10. Verify visually in Dynatrace UI
11. Write docs/dashboards/<name>/readme.md  (see dashboard-docs skill)
12. Update docs/dashboards/README.md index
13. Request screenshots (see dashboard-docs skill)
```

## Dynatrace MCP Server

The `dt-oss-aym-mcp` MCP server can be used as a reference to:

- Inspect existing dashboards and workflows
- Run DQL queries to validate metric availability before writing tiles
- Check what data is actually present for a given `deployment.environment`

Prefer `dtctl` for create/update operations (it is faster and more scriptable).
Use the MCP server for read/query/exploration.

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
   - `shares` plugin (`inbound_shares`, `outbound_shares` contexts): **logs only** — use `fetch logs`; the `shares` context uses `report_timestamp_events=True` so those summary events go to `fetch events`, but per-share/per-grant detail rows are logs
   - `users` plugin (`users`, `users_all_roles`, `users_all_privileges`, `users_direct_roles`, `users_removed_direct_roles` contexts): **logs only in practice** — although `instruments-def.yml` has `event_timestamps`, the EVENT_TIMESTAMPS contain stale dates (e.g. `last_altered` from 2021), causing Dynatrace to silently drop events. Always use `fetch logs`. See rules 15-17.
   - `resource_monitors` plugin: **logs + events + metrics** (`timeseries` for credits metrics)
   - `query_history` plugin: **logs + metrics** (`fetch logs` for detail rows, `timeseries` for execution time metrics)
   - `active_queries` plugin: **logs only** — reads INFORMATION_SCHEMA in real-time
   - Default assumption for any new plugin context: **logs only**, unless `instruments-def.yml` or `_log_entries()` call explicitly shows `report_timestamp_events=True` or `report_all_as_events=True`

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

15. **Use `toBoolean()` for boolean attribute comparisons — it handles both native booleans and strings.**
    DSOA attributes like `snowflake.user.is_disabled`, `snowflake.user.has_mfa`,
    `snowflake.user.has_rsa`, `snowflake.user.has_pat` may arrive as native booleans
    or as strings depending on the plugin and OpenPipeline processing. Using `toBoolean()`
    is the universal pattern that works for both types.

    ```dql
    # ✅ CORRECT — toBoolean() works for both native booleans and string "true"/"false"
    | fieldsAdd status = if(toBoolean(snowflake.user.is_disabled), "Disabled", else: "Active")
    | filter toBoolean(snowflake.user.has_mfa)
    | filter NOT toBoolean(snowflake.user.has_rsa)

    # ❌ WRONG — == "true" fails silently for native boolean attributes
    | fieldsAdd status = if(snowflake.user.is_disabled == "true", "Disabled", else: "Active")

    # ⚠️ FRAGILE — == true fails for string-typed boolean attributes
    | filter snowflake.user.has_mfa == true
    ```

16. **Users plugin: all contexts share `dsoa.run.context == "users"` — distinguish by attribute presence.**
    The users plugin passes a single `context_name="users"` for ALL its views
    (`V_USERS_INSTRUMENTED`, `V_USERS_ALL_ROLES_INSTRUMENTED`, `V_USERS_ALL_PRIVILEGES_INSTRUMENTED`,
    `V_USERS_DIRECT_ROLES_INSTRUMENTED`, `V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED`).
    The context names `users_all_roles`, `users_all_privileges`, `users_removed_direct_roles`
    from `instruments-def.yml` do **not** appear as `dsoa.run.context` values in Dynatrace.

    To filter for specific user data subsets, use attribute presence:

    ```dql
    # All roles data
    | filter dsoa.run.context == "users" and isNotNull(snowflake.user.roles.all)

    # All privileges data
    | filter dsoa.run.context == "users" and isNotNull(snowflake.user.privilege)

    # Removed direct roles
    | filter dsoa.run.context == "users" and isNotNull(snowflake.user.roles.direct.removed)

    # Base user info (login status, MFA, RSA, type)
    | filter dsoa.run.context == "users" and isNotNull(snowflake.user.is_disabled)
    ```

17. **Events with stale timestamps are silently dropped by Dynatrace — prefer `fetch logs`.**
    Dynatrace's OpenPipeline Events API silently rejects events whose timestamps fall
    outside the ingestion window (typically ±24h). Plugins that use `event_timestamps`
    referencing historical dates (e.g. `last_altered`, `created_on`) will show non-zero
    send counts in the agent logs, but the events will **not** appear in `fetch events`.
    The same data is always available via `fetch logs` (which uses the current timestamp).

    **Diagnostic pattern:** If a tile using `fetch events` returns 0 rows but the agent
    reports sending events successfully, switch to `fetch logs` — the data is there.

    **Known affected plugins:** `users` (all contexts — EVENT_TIMESTAMPS contain
    `last_altered` dates from months/years ago).

18. **Never use legacy `coalesce(dsoa.run.context, snowagent.run.context, service.namespace)` fallbacks.**
    Early DSOA versions used `snowagent.run.context` and `service.namespace` as attribute
    names before standardising on `dsoa.run.context`. The coalesce pattern was a migration
    shim. All current agents emit `dsoa.run.context` exclusively. New dashboards and
    dashboard updates must use `dsoa.run.context` directly — no coalesce, no `or` fallback.

19. **Dashboard variables must not depend on a single plugin context.**
    Variables like `$Environment` and `$Account` populate dropdown filters used by every
    tile on the dashboard. If the variable query is restricted to one context
    (e.g. `dsoa.run.context == "login_history"`), and that context has no data in the
    selected timeframe, the variable returns empty. An empty variable causes
    `in(deployment.environment, array($Environment))` to evaluate to `NULL` / `false`,
    blanking **all** tiles — even those whose contexts do have data.

    Always use a broad filter that matches any DSOA data:

    ```dql
    # ✅ CORRECT — works as long as ANY Snowflake data exists in the timeframe
    fetch logs
    | filter db.system == "snowflake"
    | filter isNotNull(deployment.environment)
    | fields deployment.environment
    | dedup deployment.environment
    | sort deployment.environment asc

    # ❌ WRONG — fails when login_history has no data, blanking entire dashboard
    fetch logs
    | filter dsoa.run.context == "login_history"
    | fields deployment.environment
    | dedup deployment.environment
    ```

    The same principle applies to `$Account` and any other global filter variable.

20. **Always use `unitsOverrides` for time fields — drop `(ms)` postfixes from field names.**
    When a DQL field represents a time duration in milliseconds, do **not** append `(ms)` to
    the field alias. Instead, use a clean name (e.g. `Compilation`, `Execution`, `Fastest`,
    `Slowest`, `Avg`) and add a `unitsOverrides` entry for each field:

    ```yaml
    unitsOverrides:
      - identifier: Compilation
        unitCategory: time
        baseUnit: millisecond
        displayUnit: null
        decimals: null
        suffix: ""
        delimiter: false
        added: 1
    ```

    Dynatrace renders the appropriate unit automatically in tables, charts, and tooltips.
    Keeping `(ms)` in the field name leads to redundant display like `30 s (ms)`.

21. **Multi-select variables: use `multiple: true`, no `defaultValue`, and `in()` in queries.**
    For query-type variables that should allow selecting multiple values:

    - Set `multiple: true` on the variable definition.
    - Do **not** set `defaultValue: "*"` — Dynatrace automatically adds a "select all" option.
    - Use `dedup` + `sort` instead of `collectDistinct` + `array("*", ...)`.
    - In tile queries, use `in(field, array($Variable))` instead of
      `$Var == "*" or $Var == field`.

    ```yaml
    # ✅ CORRECT — multi-select variable definition
    - key: Account
      type: query
      visible: true
      editable: true
      multiple: true
      input: |-
        fetch logs
          | filter db.system == "snowflake"
          | fieldsAdd snow_account = deployment.environment
          | filter isNotNull(snow_account)
          | fields snow_account
          | dedup snow_account
          | sort snow_account

    # ✅ CORRECT — tile query using in()
    | filter in(deployment.environment, array($Account))

    # ❌ WRONG — old single-select pattern
    | filter $Account == "*" or deployment.environment == $Account
    ```

    When a downstream variable depends on an upstream multi-select variable, use `in()` in
    its query as well:

    ```yaml
    # Warehouse depends on Account
    - key: Warehouse
      type: query
      multiple: true
      input: |-
        fetch logs
          | filter db.system == "snowflake"
          | filter in(deployment.environment, array($Account))
          | fields snowflake.warehouse.name
          | dedup snowflake.warehouse.name
          | sort snowflake.warehouse.name
    ```

22. **Drop legacy coalesce backwards-compatibility fallbacks for standard attributes.**
    Stop using `coalesce(deployment.environment, service.name)` — use `deployment.environment`
    directly. The `service.name` fallback was needed during early DSOA versions before
    `deployment.environment` was standardised. The same applies to:
    - `coalesce(db.name, db.namespace)` — keep only where both genuinely appear
    - `coalesce(db.collection.name, db.sql.table)` — keep only where both genuinely appear
    - `coalesce(db.statement, db.query.text)` — keep only where both genuinely appear

    For `deployment.environment` specifically, always use it directly — never wrap in coalesce.

## YAML Dashboard Format
```yaml
# DASHBOARD: <Human-readable title>
# DESCRIPTION: <One-line description>
# OWNER: DSOA Team
# PLUGINS: <comma-separated plugin names>
# TAGS: snowflake, dsoa, <domain>

id: <uuid>                  # assigned after first deploy; omit on initial creation
name: <Human-readable title> # REQUIRED — must match dashboard display name
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

## Deploying with deploy_dt_assets.sh (Recommended)

**Always use `scripts/deploy/deploy_dt_assets.sh` to deploy dashboards and workflows.**
This script handles YAML → JSON conversion, envelope building, `dtctl apply`, URL printing,
and automatic ID write-back — all in one step.

```bash
# Deploy all dashboards and workflows
./scripts/deploy/deploy_dt_assets.sh

# Deploy only dashboards
./scripts/deploy/deploy_dt_assets.sh --scope=dashboards

# Deploy only workflows
./scripts/deploy/deploy_dt_assets.sh --scope=workflows

# Preview without applying
./scripts/deploy/deploy_dt_assets.sh --dry-run

# Add environment label to log output
./scripts/deploy/deploy_dt_assets.sh --env=test-qa
```

On success the script prints a clickable `[URL]` line for each deployed asset:
```
[OK]    Updated: Data Volume & Storage
[URL]   https://aym57094.sprint.apps.dynatracelabs.com/ui/apps/dynatrace.dashboards/dashboard/fdd7c1db-ffc0-4c75-adea-f60cadc120ad
```

**ID write-back:** For new dashboards (no `id:` in YAML), the script automatically
inserts the assigned ID into the YAML file after deployment. This ensures future
runs update the same dashboard rather than creating a duplicate.

**YAML requirements for the script to work correctly:**
- `# DASHBOARD: <Human-readable name>` comment at the top → used as display name
- `id: <uuid>` top-level field → present after first deploy (written back automatically)
- `name: <Human-readable name>` top-level field → required for `dtctl` round-trips
  (also written back by `dtctl get` exports). If absent, the script uses the comment.

Via `deploy.sh` (opt-in, never part of default `all`):
```bash
./scripts/deploy/deploy.sh <env> --scope=dt_assets
```

## Deploying with dtctl Directly (Manual / Fallback)

Use this approach only when `deploy_dt_assets.sh` is unavailable or you need
fine-grained control (e.g. deploying a single dashboard by hand).

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

### CRITICAL envelope rules

- `id` and `name` must be **popped** from the inner content before wrapping — they must
  appear at envelope level **only**. Leaving them inside `content` causes the dashboard
  to fail to load: "We were unable to load this dashboard."
- **Do NOT** pass the flat converted JSON directly to `dtctl apply` — that causes
  `dtctl` to double-wrap the content, producing `tiles: 0`.

To produce the envelope correctly:

```bash
./scripts/tools/yaml-to-json.sh docs/dashboards/<name>/<name>.yml > /tmp/inner.json

python3 -c "
import json
inner = json.load(open('/tmp/inner.json'))
# CRITICAL: pop id/name OUT of content — they belong only at envelope level.
dashboard_id   = inner.pop('id', None)
dashboard_name = inner.pop('name')
envelope = {'name': dashboard_name, 'type': 'dashboard', 'content': inner}
if dashboard_id:
    envelope['id'] = dashboard_id
json.dump(envelope, open('/tmp/<name>-apply.json', 'w'), indent=2)
"

dtctl apply -f /tmp/<name>-apply.json
```

Verify after apply that `tiles count` is correct (not 0):

```bash
dtctl get dashboard <id> -o json | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('tiles:', len(d.get('content',{}).get('tiles',{})))
"
```

If tiles count is 0 after apply, the envelope was wrong. Rebuild and reapply.

### For new dashboards (no ID yet):

Omit `id` from the envelope. `dtctl apply` assigns one. Record it and add it to
the YAML as `id: <uuid>` so future runs update rather than create a duplicate.
(`deploy_dt_assets.sh` does this automatically.)

### Preview / diff / round-trip:
```bash
dtctl apply --dry-run -f /tmp/<name>-apply.json
dtctl apply --show-diff -f /tmp/<name>-apply.json
dtctl get dashboard <id> -o yaml > /tmp/<name>-current.yaml
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
12. Verify tiles: dtctl get dashboard <id> -o json | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print('tiles:',len(d.get('content',{}).get('tiles',{})))"
    Expected: tiles == 14 (or however many your dashboard has). If 0, envelope was wrong.
13. Verify every tile renders real data in the Dynatrace UI

=== PHASE C: Documentation ===

14. Write docs/dashboards/<name>/readme.md  (see dashboard-docs skill)
15. Update docs/dashboards/README.md index
16. Request screenshots (see dashboard-docs skill)
```

## Dynatrace MCP Server

The `dt-oss-aym-mcp` MCP server can be used as a reference to:
- Inspect existing dashboards and workflows
- Run DQL queries to validate metric availability before writing tiles
- Check what data is actually present for a given `deployment.environment`

Prefer `dtctl` for create/update operations (it is faster and more scriptable).
Use the MCP server for read/query/exploration.

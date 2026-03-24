# Skill: Dynatrace Workflow Creation and Deployment

Use this skill to create and deploy Dynatrace automation workflows
(anomaly detection, alerting, scheduled DQL actions) for DSOA.

## File Location

```text
docs/workflows/<workflow-name>/<workflow-name>.yml
docs/workflows/<workflow-name>/readme.md
docs/workflows/<workflow-name>/img/.gitkeep
docs/workflows/README.md   (index — update after every new workflow)
```

## Workflow YAML Format

Export an existing workflow as reference before writing a new one:

```bash
dtctl get workflows -A           # list all workflows with IDs
dtctl get workflow <id> -o yaml  # export one as a structural template
```

Typical workflow YAML structure:

```yaml
# WORKFLOW: <Human-readable title>
# DESCRIPTION: <One-line description>
# OWNER: DSOA Team
# PLUGINS: <comma-separated plugin names>
# TAGS: snowflake, dsoa, <domain>

id: <uuid>        # omit on first create; add after dtctl returns the ID
title: "DSOA — <Descriptive Name>"
description: |
  <What this workflow does and why>

trigger:
  # Option A — scheduled (cron)
  schedule:
    rule: "0 * * * *"
    timezone: UTC
  # Option B — event-driven
  # event:
  #   eventType: "davis.problem.opened"
  #   filter: "event.category == 'AVAILABILITY'"

tasks:
  step_query:
    name: Query anomaly data
    action: dynatrace.automations:run-javascript
    input:
      script: |
        import { queryExecutionClient } from '@dynatrace-sdk/client-query';

        export default async function () {
          const result = await queryExecutionClient.queryExecute({
            body: {
              query: `
                fetch logs
                | filter db.system == "snowflake"
                | filter dsoa.run.plugin == "<plugin>"
                | summarize count = count(), by: { snowflake.<dim> }
                | filter count > 0
              `,
              requestTimeoutMilliseconds: 30000
            }
          });
          return { anomalyCount: result.result?.records?.length ?? 0, records: result.result?.records };
        }

  step_notify:
    name: Send alert notification
    action: dynatrace.slack.connector:send-message
    conditions:
      - taskId: step_query
        condition: "{{ result('step_query').anomalyCount > 0 }}"
    input:
      channel: "#dsoa-alerts"
      message: |
        :warning: DSOA anomaly detected
        Count: {{ result('step_query').anomalyCount }}
        Details: {{ result('step_query').records | dump }}
```

## DQL Inside Workflow Scripts

Apply the same DQL rules as for dashboards (see `dynatrace-dashboard.md`):

- Use `fetch logs`, `fetch events`, or `fetch bizevents` — not `fetch metrics`
- Consult `src/dtagent/plugins/<plugin>.config/instruments-def.yml` for correct
  metric keys, dimensions, and telemetry types
- All DSOA telemetry carries `db.system == "snowflake"` and `deployment.environment`

## YAML to JSON Conversion

Workflows use the same conversion pipeline as dashboards:

```bash
./scripts/tools/yaml-to-json.sh docs/workflows/<name>/<name>.yml > /tmp/<name>.json
jq . /tmp/<name>.json > /dev/null && echo "JSON valid" || echo "JSON INVALID"
```

## Deploying with dtctl

Always use `-A` for structured agent-friendly output.

### Create new workflow (no ID in file)

```bash
dtctl apply -A -f /tmp/<name>.json
```

Record the returned ID and add it to the YAML as `id: <uuid>` so future
runs update rather than create a duplicate.

### Update existing workflow (ID already in file)

```bash
dtctl apply -A -f /tmp/<name>.json
```

### Preview changes without applying

```bash
dtctl apply -A --dry-run -f /tmp/<name>.json
```

### Show diff when updating

```bash
dtctl apply -A --show-diff -f /tmp/<name>.json
```

### Get current workflow for round-trip editing

```bash
dtctl get workflow <id> -o yaml > /tmp/<name>-current.yaml
```

## Full Deployment Sequence

```text
1.  Read instruments-def.yml for all relevant plugins
2.  Export a similar existing workflow as structural reference:
      dtctl get workflow <id> -o yaml
3.  Write workflow YAML in docs/workflows/<name>/<name>.yml
4.  Convert:   ./scripts/tools/yaml-to-json.sh ... > /tmp/<name>.json
5.  Validate:  jq . /tmp/<name>.json
6.  Deploy:    dtctl apply -A -f /tmp/<name>.json
7.  Record returned ID — add it to the YAML as `id: <uuid>`
8.  Re-convert and re-deploy with ID so subsequent runs update in place
9.  Verify workflow triggers and executes correctly in Dynatrace UI
10. Write docs/workflows/<name>/readme.md  (see dashboard-docs skill)
11. Update docs/workflows/README.md index
12. Request screenshots (see dashboard-docs skill)
```

## Dynatrace MCP Server

The `dt-oss-aym-mcp` MCP server can be used as a reference to:

- List and inspect existing workflows before writing a new one
- Run DQL queries to validate that the anomaly detection logic returns
  the expected records before embedding it in a workflow script
- Check event schemas for trigger configuration

Prefer `dtctl` for create/update operations.
Use the MCP server for read/query/exploration.

## Rebuilding DSOA (if workflow depends on new plugin code)

If the workflow queries telemetry from a plugin that was just modified:

```bash
# Rebuild
./scripts/dev/build.sh

# Redeploy to dev-094
./scripts/deploy/deploy.sh test-094 --scope=plugins,config,agents --options=skip_confirm
```

Wait for at least one collection cycle before testing the workflow trigger.

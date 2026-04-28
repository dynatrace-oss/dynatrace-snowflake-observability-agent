# Example Workflows

This directory contains example Dynatrace workflows designed to automate alerting and remediation actions based on telemetry data collected by the Dynatrace Snowflake Observability Agent (DSOA). These workflows complement the [example dashboards](../dashboards/README.md) and cover the five themes of [Data Platform Observability](../DPO.md): Security, Operations, Costs, Performance, and Quality.

- [Deploying Workflows](#deploying-workflows)
  - [Using the Deployment Script (Recommended)](#using-the-deployment-script-recommended)
  - [Using dtctl Directly](#using-dtctl-directly)
  - [Manual Import via Dynatrace UI](#manual-import-via-dynatrace-ui)
- [Available Workflows](#available-workflows)
- [Workflow Structure](#workflow-structure)
- [Prerequisites](#prerequisites)
  - [Installing dtctl](#installing-dtctl)
- [Related Documentation](#related-documentation)

## Deploying Workflows

### Using the Deployment Script (Recommended)

The easiest way to deploy all DSOA workflows to your Dynatrace environment is via the
`deploy_dt_assets.sh` script. It requires [dtctl](https://github.com/dynatrace-oss/dtctl)
to be installed and authenticated.

**Deploy all workflows:**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=workflows
```

**Dry-run (preview without applying):**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=workflows --dry-run
```

**Deploy both dashboards and workflows at once:**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=all
```

**Via the main deploy script (explicit `dt_assets` scope):**

```bash
./scripts/deploy/deploy.sh <env> --scope=dt_assets
```

> **Note:** `dt_assets` is never part of the default `all` scope in `deploy.sh` because dtctl
> is an optional dependency. You must request it explicitly.

### Using dtctl Directly

If you prefer to deploy a single workflow manually:

```bash
# 1. Convert YAML to JSON
./scripts/tools/yaml-to-json.sh docs/workflows/<name>/<name>.yml > /tmp/inner.json

# 2. Wrap in the dtctl envelope (pop id/name out of content if present)
python3 -c "
import json
inner = json.load(open('/tmp/inner.json'))
workflow_id   = inner.pop('id', None)
workflow_name = inner.pop('name', 'My Workflow')
envelope = {'name': workflow_name, 'type': 'workflow', 'content': inner}
if workflow_id:
    envelope['id'] = workflow_id
json.dump(envelope, open('/tmp/workflow-apply.json', 'w'), indent=2)
"

# 3. Apply
dtctl apply -f /tmp/workflow-apply.json
```

### Manual Import via Dynatrace UI

1. Convert the YAML to JSON using `./scripts/tools/yaml-to-json.sh`
2. In your Dynatrace environment, navigate to **Workflows**
3. Click **Import** and upload the JSON file

## Available Workflows

| Workflow                                                                      | DPO Theme             | Description                                                                                    | Required Plugin(s)  |
|-------------------------------------------------------------------------------|-----------------------|------------------------------------------------------------------------------------------------|---------------------|
| [Credits Exhaustion Prediction](./credits-exhaustion-prediction/readme.md)    | Costs                 | Detects abnormal credit consumption velocity per resource monitor and alerts before exhaustion | `resource_monitors` |
| [Org Contract Balance Warning](./org-contract-balance-warning/readme.md)      | Costs                 | Monitors remaining organization contract balances and alerts when any drops below threshold    | `org_costs`         |
| [Data Volume Anomaly Detection](./data-volume-anomaly/readme.md)              | Quality               | Detects unexpected drops in table row counts indicating failed pipelines or accidental deletes | `data_volume`       |
| [Dynamic Table Refresh Drift Detection](./dynamic-table-drift/readme.md)      | Quality / Performance | Detects when dynamic table scheduling lag consistently exceeds target lag                      | `dynamic_tables`    |
| [Query Slowdown Detection](./query-slowdown-detection/readme.md)              | Performance           | Detects abnormal increases in query execution time per warehouse and database                  | `query_history`     |
| [Table Performance Degradation Detection](./table-perf-degradation/readme.md) | Performance           | Detects tables with rising partition scan ratios indicating need for re-clustering             | `query_history`     |
| [Long-Running Queries Detection](./long-running-queries/readme.md)            | Performance           | Detects individual queries with abnormal max execution time per warehouse and user             | `query_history`     |

## Workflow Structure

Each workflow folder contains:

- **`*.yml`** — Workflow definition in YAML format (compatible with `dtctl apply`)
- **`readme.md`** — Documentation including trigger conditions, actions, and customization notes
- **`img/`** — Screenshots and visual documentation

Workflow YAML files follow the same structure exported by `dtctl get workflow -o yaml`:

```yaml
# WORKFLOW: <Human-Readable Name>
title: <workflow title>
trigger:
  type: ...
tasks:
  <task-name>:
    action: ...
    ...
```

The `# WORKFLOW:` comment is used by the deployment script to extract the human-readable name.

## Prerequisites

- DSOA must be deployed and collecting telemetry from your Snowflake account(s)
- Required plugins for each workflow must be enabled in your DSOA configuration
- [dtctl](https://github.com/dynatrace-oss/dtctl) installed and authenticated with a platform token that has `automation:workflows:write` scope

### Installing dtctl

```bash
brew install dynatrace-oss/tap/dtctl
dtctl auth login
```

## Related Documentation

- [Example Dashboards](../dashboards/README.md) — Complementary dashboard catalog
- [Data Platform Observability (DPO)](../DPO.md) — Understanding the five themes of data observability
- [Available Plugins](../PLUGINS.md) — Complete list of DSOA plugins and their capabilities
- [Installation Guide](../INSTALL.md) — Deploying dashboards and workflows with dtctl
- [Architecture](../ARCHITECTURE.md) — How DSOA collects and sends telemetry data

# OpenPipeline Rules

This directory contains example Dynatrace OpenPipeline metric-extraction rules designed to derive
counter metrics directly from Snowflake telemetry logs collected by the Dynatrace Snowflake
Observability Agent (DSOA). These rules complement the [example dashboards](../dashboards/README.md)
and [example workflows](../workflows/README.md), covering the Security and Operations themes of
[Data Platform Observability](../DPO.md).

- [Deploying OpenPipeline Rules](#deploying-openpipeline-rules)
  - [Using the Deployment Script (Recommended)](#using-the-deployment-script-recommended)
  - [Using dtctl Directly](#using-dtctl-directly)
- [Available Pipelines](#available-pipelines)
- [Pipeline File Structure](#pipeline-file-structure)
- [Prerequisites](#prerequisites)
  - [Installing dtctl](#installing-dtctl)
- [Related Documentation](#related-documentation)

## Deploying OpenPipeline Rules

### Using the Deployment Script (Recommended)

The easiest way to deploy all DSOA OpenPipeline rules to your Dynatrace environment is via the
`deploy_dt_assets.sh` script. It requires [dtctl](https://github.com/dynatrace-oss/dtctl)
to be installed and authenticated.

**Deploy all OpenPipeline rules:**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=openpipeline
```

**Dry-run (preview without applying):**

```bash
./scripts/deploy/deploy_dt_assets.sh --scope=openpipeline --dry-run
```

**Deploy dashboards, workflows, and OpenPipeline rules at once:**

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

If you prefer to deploy a single pipeline settings object manually:

```bash
# Apply the Settings 2.0 pipeline YAML directly — no conversion needed
dtctl apply -f docs/openpipeline/<name>/<name>.yml
```

## Available Pipelines

The `snowagent-logs-pipeline/` directory contains the full DSOA logs pipeline settings object.
The table below lists the metric-extraction processors it ships:

| Metric Key                      | DPO Theme  | Description                                                                                          | Required Plugin(s) |
|---------------------------------|------------|------------------------------------------------------------------------------------------------------|--------------------|
| `snowflake.task.run.failed`     | Operations | Counts FAILED task runs from `task_history` logs, dimensioned by database, schema, and task name.    | `tasks`            |
| `snowflake.task.run.cancelled`  | Operations | Counts CANCELLED task runs from `task_history` logs, dimensioned by database, schema, and task name. | `tasks`            |
| `snowflake.task.run.successful` | Operations | Counts SUCCEEDED task runs from `task_history` logs, dimensioned by database, schema, and task name. | `tasks`            |

## Pipeline File Structure

Each pipeline folder contains a single `*.yml` file — a Dynatrace Settings 2.0 object applied
directly via `dtctl apply`. The file follows the Settings 2.0 envelope with an inline `value`
block that holds the full OpenPipeline pipeline definition:

```yaml
# OPENPIPELINE: <Human-Readable Name>
# DESCRIPTION: <what the pipeline does>
# OWNER: DSOA Team
# SCHEMA: builtin:openpipeline.logs.pipelines
# TAGS: <comma-separated tags>

objectid: <settings-object-id>
schemaid: builtin:openpipeline.logs.pipelines
schemaversion: <version>
scope: environment
value:
  displayName: <Human-Readable Name>
  metricExtraction:
    processors:
      - counterMetric:
          dimensions:
            - extractionType: field
              sourceFieldName: <dim1>
          metricKey: <metric.key>
        description: <description>
        enabled: true
        id: <processor-id>
        matcher: "<DQL filter expression>"
        type: counterMetric
```

The `# OPENPIPELINE:` comment is used by the deployment script to extract the human-readable name.

## Prerequisites

- DSOA must be deployed and collecting telemetry from your Snowflake account(s)
- Required plugins for each rule must be enabled in your DSOA configuration
- [dtctl](https://github.com/dynatrace-oss/dtctl) installed and authenticated with a platform token
  that has `openpipeline:configurations:write` scope

### Installing dtctl

```bash
brew install dynatrace-oss/tap/dtctl
dtctl auth login
```

## Related Documentation

- [Example Dashboards](../dashboards/README.md) — Complementary dashboard catalog
- [Example Workflows](../workflows/README.md) — Complementary workflow catalog
- [Data Platform Observability (DPO)](../DPO.md) — Understanding the five themes of data observability
- [Available Plugins](../PLUGINS.md) — Complete list of DSOA plugins and their capabilities
- [Installation Guide](../INSTALL.md) — Deploying DSOA assets with dtctl
- [Architecture](../ARCHITECTURE.md) — How DSOA collects and sends telemetry data

# OpenPipeline Rules

This directory contains example Dynatrace OpenPipeline metric-extraction rules designed to derive
counter metrics directly from Snowflake telemetry logs collected by the Dynatrace Snowflake
Observability Agent (DSOA). These rules complement the [example dashboards](../dashboards/README.md)
and [example workflows](../workflows/README.md), covering the Security and Operations themes of
[Data Platform Observability](../DPO.md).

- [Deploying OpenPipeline Rules](#deploying-openpipeline-rules)
  - [Using the Deployment Script (Recommended)](#using-the-deployment-script-recommended)
  - [Using dtctl Directly](#using-dtctl-directly)
- [Available Rules](#available-rules)
- [Rule Structure](#rule-structure)
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

If you prefer to deploy a single rule manually:

```bash
# 1. Convert YAML to JSON
./scripts/tools/yaml-to-json.sh docs/openpipeline/<name>/<name>.yml > /tmp/rule.json

# 2. Apply
dtctl apply -f /tmp/rule.json
```

## Available Rules

| Rule | Metric Key | DPO Theme | Description | Required Plugin(s) |
|------|-----------|-----------|-------------|-------------------|
| [Snowflake login attempts failed](./snowflake-login-attempts-failed/) | `snowflake.login.attempts.failed` | Security | Counts failed Snowflake login attempts from `login_history` logs, dimensioned by user, client type, and error code | `login_history` |
| [Snowflake task run failed](./snowflake-task-run-failed/) | `snowflake.task.run.failed` | Operations | Counts FAILED task runs from `task_history` logs, dimensioned by database, schema, and task name | `tasks` |
| [Snowflake task run cancelled](./snowflake-task-run-cancelled/) | `snowflake.task.run.cancelled` | Operations | Counts CANCELLED task runs from `task_history` logs, dimensioned by database, schema, and task name | `tasks` |
| [Snowflake task run successful](./snowflake-task-run-successful/) | `snowflake.task.run.successful` | Operations | Counts SUCCEEDED task runs from `task_history` logs, dimensioned by database, schema, and task name | `tasks` |

## Rule Structure

Each rule folder contains:

- **`*.yml`** — OpenPipeline rule definition in YAML format (compatible with `dtctl apply`)

Rule YAML files follow a compact structure:

```yaml
# OPENPIPELINE: <Human-Readable Name>
# DESCRIPTION: <what the rule does>
# OWNER: DSOA Team
# PLUGINS: <required plugin(s)>
# TAGS: <comma-separated tags>

id: <slug>
displayName: <Human-Readable Name>
pipeline: default_logs
processors:
  - type: metricExtraction
    matcher: "<DQL filter expression>"
    metricKey: <metric.key>
    dimensions:
      - <dim1>
      - <dim2>
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

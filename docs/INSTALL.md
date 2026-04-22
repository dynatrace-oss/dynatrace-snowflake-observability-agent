# How to Install DSOA

This guide gets you from zero to a running agent in the shortest path.
For advanced scenarios (custom object names, privilege separation, multitenancy, CI/CD), see [INSTALL-ADVANCED.md](INSTALL-ADVANCED.md).

> **Note:** These instructions assume you are installing from the distribution package
> (`dynatrace_snowflake_observability_agent-*.zip`). Developers building from source: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (5 steps)](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Updating an Existing Installation](#updating-an-existing-installation)
- [Deploying Dashboards and Workflows](#deploying-dashboards-and-workflows)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Windows

Install [WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install) and run everything inside WSL.

### Required tools

| Tool | Install |
|---|---|
| **bash** | Included on macOS/Linux |
| **Snowflake CLI** (`snow`) | See below |
| **jq** | `brew install jq` / `apt install jq` |
| **yq** | `brew install yq` / `apt install yq` |
| **gawk** | `brew install gawk` / `apt install gawk` |

**Quick install (runs `setup.sh` which installs all tools):**

```bash
./setup.sh
```

**Install Snowflake CLI manually:**

```bash
# macOS
brew tap snowflakedb/snowflake-cli && brew install snowflake-cli

# Linux / WSL
pipx install snowflake-cli-labs
```

---

## Quick Start

### Step 1 — Create your config file

Choose a short `$ENV` name (e.g. `production`, `dev`, `tenant-a`). This is just a file label.

```bash
# Using the interactive wizard (recommended for first install):
./scripts/deploy/deploy.sh --env=production --interactive

# Or: copy the template and edit manually:
cp conf/config-template.yml conf/config-production.yml
```

**Minimum required fields in your config:**

```yaml
core:
  dynatrace_tenant_address: "YOUR_TENANT.live.dynatrace.com"
  deployment_environment: "PRODUCTION"     # Used for Dynatrace telemetry dimensions
  snowflake:
    account_name: "myorg-myaccount"        # Find with: SELECT CURRENT_ORGANIZATION_NAME()  || '-' || CURRENT_ACCOUNT_NAME()
```

### Step 2 — Set your Dynatrace API token

The token needs these scopes: `logs.ingest`, `metrics.ingest`, `bizevents.ingest`,
`openpipeline.events`, `openTelemetryTrace.ingest`.

```bash
export HISTCONTROL=ignorespace
 export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"   # leading space keeps it out of shell history
```

### Step 3 — Set up the Snowflake CLI connection

```bash
./setup.sh production
# Creates connection: snow_agent_production  (derived from deployment_environment)
```

> **Key concept:** The connection name is derived from `deployment_environment` inside your config,
> not from the `$ENV` filename. If `deployment_environment: "PRODUCTION_US_EAST"`, the connection
> name will be `snow_agent_production_us_east` (lowercase).

### Step 4 — Deploy

```bash
./scripts/deploy/deploy.sh --env=production
```

This runs a full deployment (`--scope=all`) and asks for confirmation before executing SQL.
To skip the prompt:

```bash
./scripts/deploy/deploy.sh --env=production --options=skip_confirm
```

### Step 5 — Verify

Wait ~30 minutes for the first Snowflake task run. Then check Dynatrace for incoming telemetry.
Budget-related metrics take up to 24 hours (they fire once per day).

> **No data?** See [Troubleshooting: No Data in Dynatrace](debug/no-data-in-dt/readme.md).

---

## Configuration Reference

### Core options

| Key | Required | Default | Description |
|---|---|---|---|
| `dynatrace_tenant_address` | Yes | — | e.g. `abc123.live.dynatrace.com` |
| `deployment_environment` | Yes | — | Unique identifier sent with all telemetry |
| `log_level` | No | `WARN` | `DEBUG` / `INFO` / `WARN` / `ERROR` |
| `tag` | No | `""` | Multitenancy suffix for Snowflake object names |
| `procedure_timeout` | No | `3600` | Stored procedure timeout in seconds |
| `snowflake.account_name` | Recommended | auto-detected | `myorg-myaccount` format (avoids ~100ms startup query) |
| `snowflake.host_name` | No | derived | Leave as `"-"` to auto-derive from `account_name` |

For custom object names (database, warehouse, roles), subscription-only signals, plugin scheduling,
and multitenancy — see [INSTALL-ADVANCED.md](INSTALL-ADVANCED.md).

### Finding your Snowflake account identifier

```sql
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_name;
```

Use the result as `snowflake.account_name` in your config.

---

## Updating an Existing Installation

### Config or plugin changes only (no SQL schema changes)

```bash
./scripts/deploy/deploy.sh --env=production --scope=plugins,config,agents --options=skip_confirm
```

### Version upgrade

```bash
# 1. Build new version (if building from source)
./scripts/dev/build.sh

# 2. Apply upgrade scripts first
./scripts/deploy/deploy.sh --env=production --scope=upgrade --from-version=0.9.2 --options=skip_confirm

# 3. Then redeploy
./scripts/deploy/deploy.sh --env=production --scope=plugins,agents,config --options=skip_confirm
```

### Scope reference

| Scope | When to use | Requires |
|---|---|---|
| `all` | Fresh install or major update | `ACCOUNTADMIN` |
| `init` | First-time only: creates DB, WH, roles | `ACCOUNTADMIN` |
| `admin` | Creates `DTAGENT_ADMIN` role (optional) | `DTAGENT_ADMIN` or `ACCOUNTADMIN` |
| `setup` | Core schema/procedure changes | `DTAGENT_OWNER` |
| `plugins` | Plugin code changes | `DTAGENT_OWNER` |
| `config` | Config values only — no SQL | `DTAGENT_OWNER` |
| `agents` | Task scheduler changes | `DTAGENT_OWNER` |
| `apikey` | Update Dynatrace token only | `DTAGENT_OWNER` |
| `upgrade` | Schema migrations between versions | `DTAGENT_OWNER` |
| `teardown` | Full uninstall | `ACCOUNTADMIN` |
| `dt_assets` | Deploy Dynatrace dashboards + workflows | `dtctl` auth |

**Always include `config`** alongside other scopes — omitting it leaves tasks suspended.

### `deploy.sh` usage

```text
deploy.sh --env=<ENV> [--scope=<SCOPE>] [--options=<OPTIONS>] [--from-version=<VER>] [--output-file=<FILE>]

Options: manual, service_user, skip_confirm, no_dep, dry_run

Run: deploy.sh --help   for full reference
```

---

## Deploying Dashboards and Workflows

After the agent is running, deploy pre-built Dynatrace dashboards and workflows.

### Prerequisites

Install and authenticate `dtctl`:

```bash
brew install dynatrace-oss/tap/dtctl
dtctl auth login
# or: export DTCTL_TOKEN="dt0s01.YOUR_PLATFORM_TOKEN"
```

Required platform token scopes: `document:documents:write`, `automation:workflows:write`.

### Deploy

```bash
# All dashboards and workflows:
./scripts/deploy/deploy_dt_assets.sh

# Dashboards only:
./scripts/deploy/deploy_dt_assets.sh --scope=dashboards

# Dry-run (preview only):
./scripts/deploy/deploy_dt_assets.sh --dry-run
```

Or as part of a `deploy.sh` run:

```bash
./scripts/deploy/deploy.sh --env=production --scope=dt_assets
```

See [docs/dashboards/README.md](dashboards/README.md) and [docs/workflows/README.md](workflows/README.md)
for available assets.

---

## Troubleshooting

### `ERROR: --env=<ENV> is required`

You did not pass `--env`. Example: `deploy.sh --env=production`. Run `deploy.sh --help` for usage.

### `Connection 'snow_agent_xxx' not found`

The Snowflake CLI connection name must match `snow_agent_<deployment_environment_lowercase>`.
Your connection is derived from `deployment_environment` **inside** the config file, not from
the `$ENV` filename.

```bash
# Check what connection name should be:
yq '.core.deployment_environment' conf/config-$ENV.yml | tr '[:upper:]' '[:lower:]' | sed 's/^/snow_agent_/'

# Create the correct connection:
./setup.sh $ENV
```

### `There is no configuration file [conf/config-xxx.yml]`

The `$ENV` value you passed doesn't match any config file. Config files live in `conf/` and follow
the `config-<ENV>.yml` naming convention.

```bash
ls conf/config-*.yml    # List existing configs
deploy.sh --env=production --defaults   # Generate a skeleton config
```

### Tasks running but no data in Dynatrace

See [Troubleshooting: No Data in Dynatrace](debug/no-data-in-dt/readme.md).

### Without a Dynatrace Platform Subscription (DPS)

BizEvents and OpenPipeline events require DPS. Disable them to avoid errors:

```yaml
otel:
  events:
    is_disabled: true
  biz_events:
    is_disabled: true
```

Logs, metrics, and spans work on all Dynatrace tenants.

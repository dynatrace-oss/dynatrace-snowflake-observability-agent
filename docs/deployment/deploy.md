# Local Deployment Guide

Deploy DSOA directly from your workstation using `deploy.sh`.

For Docker-based deployment, see [docker.md](docker.md).
For GitHub Actions CI/CD, see [github-actions.md](github-actions.md).

## Prerequisites

| Tool | Install |
| --- | --- |
| **bash** | Included on macOS/Linux |
| **Snowflake CLI** (`snow`) | See below |
| **jq** | `brew install jq` / `apt install jq` |
| **yq** | `brew install yq` / `apt install yq` |
| **gawk** | `brew install gawk` / `apt install gawk` |

**Windows:** Install [WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install) and run everything inside WSL.

### Install Snowflake CLI

```bash
# macOS
brew tap snowflakedb/snowflake-cli && brew install snowflake-cli

# Linux / WSL
pipx install snowflake-cli-labs
```

Or run `./setup.sh` — it installs all missing tools automatically.

## Setup

```bash
# Install tools and create Snowflake connection profile
./setup.sh production
```

This creates a `snow_agent_production` connection profile (name derived from `deployment_environment` in your config).

## Configuration

Choose a short `$ENV` name (e.g. `production`, `dev`, `tenant-a`).

```bash
# Interactive wizard (recommended for first install)
./scripts/deploy/deploy.sh --env=production --interactive

# Or copy the template and edit manually
cp conf/config-template.yml conf/config-production.yml
```

Minimum required fields:

```yaml
core:
  dynatrace_tenant_address: "YOUR_TENANT.live.dynatrace.com"
  deployment_environment: "PRODUCTION"
  snowflake:
    account_name: "myorg-myaccount"
```

Find your Snowflake account identifier:

```sql
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_name;
```

## Deployment

```bash
# Set Dynatrace API token
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"

# Full deploy (first install)
./scripts/deploy/deploy.sh --env=production

# Skip confirmation prompt
./scripts/deploy/deploy.sh --env=production --options=skip_confirm

# Partial deploy (plugins + config only)
./scripts/deploy/deploy.sh --env=production --scope=plugins,config,agents --options=skip_confirm
```

## Scope Reference

| Scope | When to use | Requires |
| --- | --- | --- |
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

## Updating an Existing Installation

### Config or plugin changes only

```bash
./scripts/deploy/deploy.sh --env=production --scope=plugins,config,agents --options=skip_confirm
```

### Version upgrade

```bash
# 1. Apply upgrade scripts first
./scripts/deploy/deploy.sh --env=production --scope=upgrade --from-version=0.9.2 --options=skip_confirm

# 2. Then redeploy
./scripts/deploy/deploy.sh --env=production --scope=plugins,agents,config --options=skip_confirm
```

## Troubleshooting

### `Connection 'snow_agent_xxx' not found`

The connection name is derived from `deployment_environment` inside the config, not from the `$ENV` filename.

```bash
# Check expected connection name
yq '.core.deployment_environment' conf/config-production.yml | tr '[:upper:]' '[:lower:]' | sed 's/^/snow_agent_/'

# Recreate the connection
./setup.sh production
```

### `ERROR: Build artifacts are missing`

Run `./scripts/dev/build.sh` first, then retry.

### No data in Dynatrace

See [Troubleshooting: No Data in Dynatrace](../debug/no-data-in-dt/readme.md).

# How to Install DSOA

Three ways to deploy DSOA — choose the one that fits your environment:

| Method                     | Best for                                                   |
|----------------------------|------------------------------------------------------------|
| **Docker** (recommended)   | Any OS — no toolchain, just Docker                         |
| **deploy.sh** (local)      | macOS/Linux with Snowflake CLI installed                   |
| **GitHub Actions** (CI/CD) | Regulated environments, audit trail, automated deployments |

> **Note:** These instructions use the published Docker image
> (`ghcr.io/dynatrace-oss/dsoa-deploy:latest`). Developers building from source: see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Docker (Recommended)

No toolchain required — just Docker. Works on any OS.

### First install — interactive wizard

```bash
docker run -it \
  -v "$(pwd)/conf:/app/conf" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production --interactive
```

The wizard prompts for your Dynatrace tenant, Snowflake account, and API token,
creates `conf/config-production.yml`, then deploys the agent.

> [!NOTE]
> The `-v "$(pwd)/conf:/app/conf"` mount is required — the container cannot access
> your local files without it. The wizard saves the generated config there so you
> can reuse it for future deployments.

### Subsequent deployments (config already exists)

```bash
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"

docker run --rm \
  -v "$(pwd)/conf:/app/conf" \
  -e DTAGENT_TOKEN \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production --options=skip_confirm
```

### Available image tags

| Tag                                        | Use                       |
|--------------------------------------------|---------------------------|
| `ghcr.io/dynatrace-oss/dsoa-deploy:latest` | Latest stable release     |
| `ghcr.io/dynatrace-oss/dsoa-deploy:v0.9.5` | Pin to a specific version |

### Step 2 — Wait for first run

Wait ~30 minutes for the first Snowflake task run. Budget-related metrics take up to 24 hours.

### Step 3 — Verify in Dynatrace

Check Dynatrace for incoming telemetry. No data? See [Troubleshooting: No Data in Dynatrace](debug/no-data-in-dt/readme.md).

For full Docker documentation (non-interactive CI usage, env vars):
see [docs/deployment/docker.md](deployment/docker.md).

---

## Local deploy.sh

```bash
# 1. Install tools and create Snowflake connection
./setup.sh production

# 2. Create config (interactive wizard)
./scripts/deploy/deploy.sh --env=production --interactive

# 3. Set token and deploy
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"
./scripts/deploy/deploy.sh --env=production
```

Full guide: [docs/deployment/deploy.md](deployment/deploy.md)

---

## GitHub Actions

Generate a ready-to-use workflow with:

```bash
docker run -it \
  -v "$(pwd)/conf:/app/conf" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production --interactive --ci-export=github
```

This creates `.github/workflows/dsoa-deploy.yml` and `GITHUB_SECRETS_SETUP.md`
in your deployment repository.

Alternatively, copy the reference template from
[`docs/deployment/github-actions-template.yml`](deployment/github-actions-template.yml)
and replace `<YOUR_ENV>` with your environment name.

Full guide: [docs/deployment/github-actions.md](deployment/github-actions.md)

---

## Verifying Your Installation

After deploying, confirm the installation is healthy:

```sh
./scripts/deploy/deploy.sh --env=production --scope=verify
```

Runs five Snowflake checks (database, stored procedures, tasks, config, version) and two optional
Dynatrace checks (recent telemetry, version match). Outputs a JSON report on stdout and a
human-readable summary on stderr. Exit code 0 = healthy (PASS or WARN); exit code 1 = failure.

To also verify that telemetry has reached Dynatrace, export a token with the `storage:events:read`
scope in addition to the standard ingest scopes:

```sh
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"
./scripts/deploy/deploy.sh --env=production --scope=verify
```

For CI/CD pipelines — deploy then verify in one pipeline step:

```sh
./scripts/deploy/deploy.sh --env=production --scope=all && \
./scripts/deploy/deploy.sh --env=production --scope=verify
```

> [!NOTE]
> `verify` is a standalone scope and cannot be combined with other scopes.
> The Dynatrace checks query for bizevents from the last 2 hours, so they may show
> no data immediately after a fresh deployment — run them again after the first scheduled task
> execution (~15 minutes).

---

## Dynatrace API Token Scopes

The `DTAGENT_TOKEN` needs these scopes:

- `logs.ingest`
- `metrics.ingest`
- `bizevents.ingest`
- `openpipeline.events`
- `openTelemetryTrace.ingest`

---

## Deploying Dashboards and Workflows

After the agent is running, deploy pre-built Dynatrace dashboards and workflows.

### Dynatrace Deployment Prerequisites

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

Pass `--env`. Example: `deploy.sh --env=production`. Run `deploy.sh --help` for usage.

### `Connection 'snow_agent_xxx' not found`

The connection name is derived from `deployment_environment` inside the config, not from the `$ENV` filename.
Run `./setup.sh $ENV` to create the correct connection.

For more troubleshooting, see [docs/debug/](debug/) and [INSTALL_ADVANCED.md](INSTALL_ADVANCED.md).

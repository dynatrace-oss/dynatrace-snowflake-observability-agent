# How to Install DSOA

Three ways to deploy DSOA — choose the one that fits your environment:

| Method | Best for |
| --- | --- |
| **Docker** (simplest) | Any OS, no toolchain required |
| **deploy.sh** (local) | macOS/Linux with Snowflake CLI installed |
| **GitHub Actions** (CI/CD) | Regulated environments, audit trail, automated deployments |

> **Note:** These instructions assume you are installing from the distribution package
> (`dynatrace_snowflake_observability_agent-*.zip`). Developers building from source: see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Docker Quick Start

The fastest path to a running agent.

### Step 1 — Pull and run the interactive wizard

```bash
docker run -it \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="dt0c01.YOUR_TOKEN" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production --interactive
```

The wizard creates `conf/config-production.yml` and deploys the agent.

### Step 2 — Wait for first run

Wait ~30 minutes for the first Snowflake task run. Budget-related metrics take up to 24 hours.

### Step 3 — Verify in Dynatrace

Check Dynatrace for incoming telemetry. No data? See [Troubleshooting: No Data in Dynatrace](debug/no-data-in-dt/readme.md).

For full Docker documentation (non-interactive CI usage, env vars, building locally):
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
./scripts/deploy/deploy.sh --env=production --interactive --ci-export=github
```

This creates `.github/workflows/dsoa-deploy.yml` and `GITHUB_SECRETS_SETUP.md`.

Full guide: [docs/deployment/github-actions.md](deployment/github-actions.md)

---

## Dynatrace API Token Scopes

The `DTAGENT_TOKEN` needs these scopes:

- `logs.ingest`
- `metrics.ingest`
- `bizevents.ingest`
- `openpipeline.events`
- `openTelemetryTrace.ingest`

---

## Troubleshooting

### `ERROR: --env=<ENV> is required`

Pass `--env`. Example: `deploy.sh --env=production`. Run `deploy.sh --help` for usage.

### `Connection 'snow_agent_xxx' not found`

The connection name is derived from `deployment_environment` inside the config, not from the `$ENV` filename.
Run `./setup.sh $ENV` to create the correct connection.

For more troubleshooting, see [docs/debug/](debug/) and [INSTALL-ADVANCED.md](INSTALL-ADVANCED.md).

# GitHub Actions Deployment Guide

Deploy DSOA from a GitHub Actions workflow — ideal for regulated environments,
CI/CD-first teams, and deployments requiring an audit trail.

For local deployment, see [deploy.md](deploy.md).
For Docker deployment, see [docker.md](docker.md).

## When to Use GitHub Actions

- Regulated environments requiring deployment audit trails
- Teams that manage infrastructure as code in Git
- Automated deployments triggered by config changes
- Environments where direct Snowflake access from developer machines is restricted

## Prerequisites

- A GitHub repository for your DSOA deployment config
- GitHub secrets configured (see [Required Secrets](#required-secrets))
- A Snowflake service user with key-pair authentication

## Quick Start

### Option 1 — Generate workflow with the wizard

```bash
./scripts/deploy/deploy.sh --env=production --interactive --ci-export=github
```

This runs the interactive wizard, saves your config, and generates:

- `.github/workflows/dsoa-deploy.yml` — ready-to-use workflow
- `GITHUB_SECRETS_SETUP.md` — step-by-step secrets configuration guide

### Option 2 — Copy the reference template

Copy [`docs/deployment/github-actions-template.yml`](github-actions-template.yml) to
`.github/workflows/dsoa-deploy.yml` in your deployment repository, then replace
`<YOUR_ENV>` with your environment name and configure secrets manually.

## Required Secrets

Configure in: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Description |
| --- | --- |
| `DTAGENT_TOKEN` | Dynatrace API token with `logs.ingest`, `metrics.ingest`, `bizevents.ingest`, `openpipeline.events`, `openTelemetryTrace.ingest` |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier (`myorg-myaccount` format) |
| `SNOWFLAKE_USER` | Snowflake service user for deployments |
| `SNOWFLAKE_PRIVATE_KEY_RAW` | RSA private key PEM (no passphrase) |

## Key Pair Authentication Setup

### 1. Generate key pair

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -nocrypt -inform PEM -outform PEM -out dsoa_deploy_key.pem
openssl rsa -in dsoa_deploy_key.pem -pubout -out dsoa_deploy_key.pub
```

### 2. Register public key in Snowflake

```sql
ALTER USER svc_dsoa_deploy SET RSA_PUBLIC_KEY='<contents of dsoa_deploy_key.pub without header/footer>';
```

### 3. Add private key as GitHub secret

Copy the **entire contents** of `dsoa_deploy_key.pem` (including the `-----BEGIN PRIVATE KEY-----`
and `-----END PRIVATE KEY-----` lines) as the value of `SNOWFLAKE_PRIVATE_KEY_RAW`.

## Triggering Deployments

### Via GitHub Actions UI

1. Go to your repository → **Actions** → **Deploy DSOA to Snowflake**
1. Click **Run workflow**
1. Select scope (use `all` for first install)
1. Click **Run workflow**

### Via GitHub CLI

```bash
gh workflow run dsoa-deploy.yml -f scope=plugins,config,agents
```

### Via REST API

```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/YOUR_ORG/YOUR_REPO/actions/workflows/dsoa-deploy.yml/dispatches" \
  -d '{"ref":"main","inputs":{"scope":"plugins,config,agents"}}'
```

## Approval Gates (GitHub Environments)

For production deployments requiring manual approval:

1. Create a GitHub Environment named `production`
1. Add required reviewers
1. Reference the environment in the workflow job:

```yaml
jobs:
  deploy:
    environment: production
    runs-on: ubuntu-latest
```

## Advanced: WIF/OIDC Authentication

For enterprise environments using Workload Identity Federation instead of long-lived keys,
configure OIDC trust between GitHub Actions and Snowflake. This is an advanced topic —
consult your Snowflake administrator and the
[Snowflake OIDC documentation](https://docs.snowflake.com/en/user-guide/oauth-external).

## Config File Management

The workflow mounts `conf/` from the repository. Commit your `conf/config-<ENV>.yml`
to the deployment repository (ensure it contains no secrets — tokens are passed via env vars).

For fully automated config generation (no committed config file), use `--defaults` with
`DSOA_DT_TENANT`, `DSOA_SF_ACCOUNT`, and `DSOA_DEPLOYMENT_ENV` secrets.

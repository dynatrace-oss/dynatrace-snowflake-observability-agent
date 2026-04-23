# Docker Deployment Guide

Deploy DSOA using Docker — no local toolchain required beyond Docker itself.

For local `deploy.sh` deployment, see [deploy.md](deploy.md).
For GitHub Actions CI/CD, see [github-actions.md](github-actions.md).

## When to Use Docker

- Windows without WSL
- Reproducible deployments across machines
- CI/CD pipelines where installing `snow` CLI is inconvenient
- Isolated environments where you cannot install system packages

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- A `conf/config-<ENV>.yml` file (or env vars for `--defaults` mode)
- `DTAGENT_TOKEN` environment variable

## Quick Start

### Interactive (first install)

```bash
docker run -it \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production --interactive
```

This launches the interactive wizard to create your config, then deploys.

### Non-interactive (CI/CD)

```bash
docker run --rm \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  -e SNOWFLAKE_ACCOUNT="myorg-myaccount" \
  -e SNOWFLAKE_USER="svc_dsoa_deploy" \
  -e SNOWFLAKE_PRIVATE_KEY_RAW="$SNOWFLAKE_PRIVATE_KEY_RAW" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production \
  --defaults \
  --options=skip_confirm
```

When `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` are set, `deploy.sh` automatically uses
`--temporary-connection` (key-pair auth) instead of a named connection profile.

## Mounting the Config Volume

The container has its own isolated filesystem — it **cannot access your local files** unless
you mount them explicitly. Always mount your local `conf/` directory into `/app/conf`:

```bash
-v /absolute/path/to/conf:/app/conf
# or (relative, Docker Compose / newer Docker):
-v ./conf:/app/conf
# or (current directory):
-v "$(pwd)/conf:/app/conf"
```

### Using an existing config file

If you already have a `conf/config-<ENV>.yml`, mount the directory and reference it by env name:

```bash
docker run -it --rm \
  -v "$(pwd)/conf:/app/conf" \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=<ENV>
```

The container will find `conf/config-<ENV>.yml` from the mounted volume.

**Without the `-v` mount the container starts fresh with no config and the wizard
will prompt you to create one from scratch, ignoring any local files.**

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `DTAGENT_TOKEN` | Yes | Dynatrace API token |
| `SNOWFLAKE_ACCOUNT` | For CI | Snowflake account identifier (enables `--temporary-connection`) |
| `SNOWFLAKE_USER` | For CI | Snowflake service user |
| `SNOWFLAKE_PRIVATE_KEY_RAW` | For CI | RSA private key PEM contents |
| `DSOA_DT_TENANT` | With `--defaults` | Dynatrace tenant address for config generation |
| `DSOA_SF_ACCOUNT` | With `--defaults` | Snowflake account for config generation |
| `DSOA_DEPLOYMENT_ENV` | With `--defaults` | Deployment environment name |

## Generating Config from Env Vars (`--defaults`)

When no config file exists, `--defaults` generates one from env vars:

```bash
docker run --rm \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  -e SNOWFLAKE_ACCOUNT="myorg-myaccount" \
  -e SNOWFLAKE_USER="svc_dsoa_deploy" \
  -e SNOWFLAKE_PRIVATE_KEY_RAW="$SNOWFLAKE_PRIVATE_KEY_RAW" \
  -e DSOA_DT_TENANT="abc123.live.dynatrace.com" \
  -e DSOA_SF_ACCOUNT="myorg-myaccount" \
  -e DSOA_DEPLOYMENT_ENV="PRODUCTION" \
  ghcr.io/dynatrace-oss/dsoa-deploy:latest \
  --env=production \
  --defaults \
  --options=skip_confirm
```

## Building the Image Locally

The Docker image requires build artifacts. Run `build.sh` first:

```bash
# 1. Build DSOA artifacts
make build

# 2. Build Docker image
make docker-build

# 3. Smoke-test
make docker-test
```

Or manually:

```bash
docker build -t dsoa-deploy:local .
docker run --rm dsoa-deploy:local --help
```

**Note:** `build/` must exist before `docker build`. The Makefile `docker-build` target
prints a warning if `build/` is missing.

## Specific Version

Pin to a specific release version for reproducible deployments:

```bash
ghcr.io/dynatrace-oss/dsoa-deploy:0.9.5
```

Available tags: `latest`, `v<version>` (e.g. `v0.9.5`).

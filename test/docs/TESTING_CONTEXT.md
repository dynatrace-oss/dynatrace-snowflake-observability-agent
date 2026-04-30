# Testing Context: Docker & Workflow Validation

## What Changed

Recent fixes to `deploy.sh --defaults`:

- **Exit code:** Now exits **0** after config generation (previously may have failed)
- **Build check:** Skipped when `--defaults` is used without existing config
- **Env vars:** Reads `DSOA_DT_TENANT`, `DSOA_SF_ACCOUNT`, `DSOA_DEPLOYMENT_ENV` to generate minimal config
- **Bats tests:** Updated to provide required env vars for all test scenarios

## Why This Matters

The Docker image and GitHub workflows rely on `--defaults` for **non-interactive config generation** in CI/CD environments:

1. **Docker image** (`Dockerfile`):
   - Entrypoint is `deploy.sh`
   - Workflows pass `--defaults` + env vars instead of interactive wizard
   - Config must be generated without user input

2. **GitHub workflow** (`.github/workflows/dsoa-deploy-template.yml`):
   - Runs `docker run ... --defaults --options=skip_confirm`
   - Passes secrets as env vars: `DTAGENT_TOKEN`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_RAW`
   - Expects config to be generated automatically

## Testing Scope

### Part 1: Docker Image Testing

**What to test:**

- Image builds successfully
- `--help` works (smoke test)
- `--defaults` generates config from env vars
- `--defaults` fails gracefully without required env vars
- `--defaults` respects existing config (doesn't overwrite)
- Full deployment works with Snowflake + Dynatrace credentials

**Why:**

- Ensures the image is deployable
- Validates the core fix (exit 0 after config generation)
- Confirms env var handling is correct
- Tests the full CI/CD path

### Part 2: GitHub Workflow Testing

**What to test:**

- CI workflow passes all lint and test jobs
- Deployment workflow can be triggered manually
- Workflow syntax is valid
- Secrets are properly injected

**Why:**

- Ensures the workflow is syntactically correct
- Validates that the Docker image is used correctly
- Confirms the workflow can be safely tested on feature branches
- Prevents accidental deployments to `main`/`devel`

### Part 3: Integration Testing

**What to test:**

- Bats tests for `--defaults` mode pass
- Bats tests for new deploy flags pass
- Full test suite passes

**Why:**

- Validates the underlying shell script behavior
- Ensures the fix doesn't break existing functionality
- Confirms all edge cases are handled

## Key Test Scenarios

### Scenario 1: Config Generation (Core Fix)

```bash
export DSOA_DT_TENANT="abc123.live.dynatrace.com"
export DSOA_SF_ACCOUNT="myorg-myaccount"

docker run --rm \
  -v ./conf:/app/conf \
  -e DSOA_DT_TENANT="$DSOA_DT_TENANT" \
  -e DSOA_SF_ACCOUNT="$DSOA_SF_ACCOUNT" \
  dsoa-deploy:local \
  --env=test \
  --defaults
```

**Expected:**

- Exit code: **0**
- Output: `Config generated at: /app/conf/config-test.yml`
- File created with correct values

**Why:** This is the core fix — `--defaults` must exit 0 after generating config.

### Scenario 2: Missing Required Env Var

```bash
unset DSOA_DT_TENANT

docker run --rm \
  -v ./conf:/app/conf \
  -e DSOA_SF_ACCOUNT="myorg-myaccount" \
  dsoa-deploy:local \
  --env=test \
  --defaults
```

**Expected:**

- Exit code: **non-zero**
- Output: `ERROR: --defaults requires DSOA_DT_TENANT env var`

**Why:** Validates error handling and prevents silent failures.

### Scenario 3: Existing Config (No Overwrite)

```bash
# Pre-create config with different values
cat > ./conf/config-test.yml << 'EOF'
core:
  dynatrace_tenant_address: existing.live.dynatrace.com
  snowflake:
    account_name: existing-account
EOF

# Run with different env vars
export DSOA_DT_TENANT="new.live.dynatrace.com"

docker run --rm \
  -v ./conf:/app/conf \
  -e DSOA_DT_TENANT="$DSOA_DT_TENANT" \
  dsoa-deploy:local \
  --env=test \
  --defaults
```

**Expected:**

- Exit code: **0**
- Output: `Config file already exists: conf/config-test.yml — using as-is`
- File content: **unchanged** (still has `existing.live.dynatrace.com`)

**Why:** Prevents accidental overwrite of production configs.

### Scenario 4: Full Deployment

```bash
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN"
export SNOWFLAKE_ACCOUNT="myorg-myaccount"
export SNOWFLAKE_USER="svc_dsoa_deploy"
export SNOWFLAKE_PRIVATE_KEY_RAW="$(cat /path/to/key.pem)"

docker run --rm \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  -e SNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
  -e SNOWFLAKE_USER="$SNOWFLAKE_USER" \
  -e SNOWFLAKE_PRIVATE_KEY_RAW="$SNOWFLAKE_PRIVATE_KEY_RAW" \
  -e DSOA_DT_TENANT="abc123.live.dynatrace.com" \
  -e DSOA_SF_ACCOUNT="myorg-myaccount" \
  dsoa-deploy:local \
  --env=production \
  --scope=init \
  --defaults \
  --options=skip_confirm
```

**Expected:**

- Exit code: **0**
- Config generated
- Deployment proceeds without user interaction
- SQL executed on Snowflake

**Why:** Validates the full CI/CD path from config generation to deployment.

## Files Modified / Created

### Source Code

- `scripts/deploy/deploy.sh` — `--defaults` mode implementation
- `Dockerfile` — Docker image definition
- `.github/workflows/dsoa-deploy-template.yml` — GitHub Actions workflow

### Tests

- `test/bash/test_defaults_mode.bats` — Comprehensive `--defaults` tests
- `test/bash/test_deploy_new_flags.bats` — New flag tests

### Documentation (New)

- `test/docs/MANUAL_TESTING.md` — Step-by-step testing guide
- `test/docs/QUICK_REFERENCE.md` — Quick reference card
- `test/docs/TESTING_CONTEXT.md` — This file

## How to Use These Guides

1. **Quick start:** Read `QUICK_REFERENCE.md` (5 min)
2. **Detailed steps:** Follow `MANUAL_TESTING.md` (30-60 min depending on scope)
3. **Understanding:** Refer to `TESTING_CONTEXT.md` (this file) for rationale

## Validation Checklist

Before merging or deploying:

- [ ] Docker image builds without errors
- [ ] `--defaults` generates config and exits 0
- [ ] `--defaults` fails gracefully without required env vars
- [ ] Existing config is not overwritten
- [ ] Full deployment works with real Snowflake + Dynatrace
- [ ] CI workflow passes all jobs
- [ ] Deployment workflow can be triggered on feature branch
- [ ] All bats tests pass
- [ ] No secrets are exposed in logs

## References

- [Dockerfile](../../Dockerfile)
- [deploy.sh](../../scripts/deploy/deploy.sh)
- [GitHub Workflow](../../.github/workflows/dsoa-deploy-template.yml)
- [Bats Tests](../../test/bash/test_defaults_mode.bats)
- [Docker Deployment Guide](../../docs/deployment/docker.md)
- [Local Deployment Guide](../../docs/deployment/deploy.md)

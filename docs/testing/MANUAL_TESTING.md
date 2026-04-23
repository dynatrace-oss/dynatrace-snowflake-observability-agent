# Manual Testing Guide

Step-by-step instructions for testing the Docker image and GitHub workflows locally.

## Part 1: Docker Image Testing

### Prerequisites

- Docker installed and running
- Build artifacts generated: `./scripts/dev/build.sh`
- Valid Dynatrace API token (for full deployment testing)

### 1.1 Build the Docker Image Locally

```bash
# Build DSOA artifacts first
./scripts/dev/build.sh

# Build the Docker image
make docker-build

# Or manually:
docker build -t dsoa-deploy:local .
```

**Verify the build succeeded:**

```bash
docker images | grep dsoa-deploy
# Should show: dsoa-deploy    local    <IMAGE_ID>    <SIZE>
```

### 1.2 Test `--help` (Smoke Test)

```bash
docker run --rm dsoa-deploy:local --help
```

**Expected output:** Full help text showing all deploy.sh options.

### 1.3 Test `--defaults` Mode (Config Generation)

This tests the core fix: `--defaults` now exits 0 after config generation without requiring build artifacts or Snowflake connection.

#### 3a. Generate config with required env vars

```bash
# Set required env vars
export DSOA_DT_TENANT="abc123.live.dynatrace.com"
export DSOA_SF_ACCOUNT="myorg-myaccount"
export DSOA_DEPLOYMENT_ENV="TEST"

# Create a temporary directory for config
mkdir -p /tmp/dsoa-test-conf

# Run with --defaults (no build artifacts needed, no Snowflake connection needed)
docker run --rm \
  -v /tmp/dsoa-test-conf:/app/conf \
  -e DSOA_DT_TENANT="$DSOA_DT_TENANT" \
  -e DSOA_SF_ACCOUNT="$DSOA_SF_ACCOUNT" \
  -e DSOA_DEPLOYMENT_ENV="$DSOA_DEPLOYMENT_ENV" \
  dsoa-deploy:local \
  --env=test \
  --defaults
```

**Expected behavior:**
- Exit code: **0** (success)
- Output: `Config generated at: /app/conf/config-test.yml`
- File created: `/tmp/dsoa-test-conf/config-test.yml`

**Verify the generated config:**

```bash
cat /tmp/dsoa-test-conf/config-test.yml
```

**Expected content:**

```yaml
core:
  dynatrace_tenant_address: abc123.live.dynatrace.com
  deployment_environment: TEST
  snowflake:
    account_name: myorg-myaccount
  log_level: WARN
  procedure_timeout: 3600
plugins:
  deploy_disabled_plugins: true
```

#### 3b. Test missing required env var

```bash
# Unset DSOA_DT_TENANT to test error handling
unset DSOA_DT_TENANT

docker run --rm \
  -v /tmp/dsoa-test-conf:/app/conf \
  -e DSOA_SF_ACCOUNT="myorg-myaccount" \
  dsoa-deploy:local \
  --env=test2 \
  --defaults
```

**Expected behavior:**
- Exit code: **non-zero** (failure)
- Output contains: `ERROR: --defaults requires DSOA_DT_TENANT env var`

#### 3c. Test with existing config (should not regenerate)

```bash
# Create a pre-existing config
cat > /tmp/dsoa-test-conf/config-test3.yml << 'EOF'
core:
  dynatrace_tenant_address: existing.live.dynatrace.com
  deployment_environment: EXISTING
  snowflake:
    account_name: existing-account
  log_level: WARN
  procedure_timeout: 3600
plugins:
  deploy_disabled_plugins: true
EOF

# Run with --defaults and different env vars
docker run --rm \
  -v /tmp/dsoa-test-conf:/app/conf \
  -e DSOA_DT_TENANT="new.live.dynatrace.com" \
  -e DSOA_SF_ACCOUNT="new-account" \
  dsoa-deploy:local \
  --env=test3 \
  --defaults
```

**Expected behavior:**
- Exit code: **0** (success)
- Output: `Config file already exists: conf/config-test3.yml — using as-is`
- File content: **unchanged** (still has `existing.live.dynatrace.com`)

### 1.4 Test Full Deployment (with Snowflake + Dynatrace)

**Prerequisites:**
- Valid Snowflake account and credentials
- Valid Dynatrace API token
- Existing config file or env vars for `--defaults`

```bash
# Set all required env vars
export DTAGENT_TOKEN="dt0c01.YOUR_TOKEN_HERE"
export SNOWFLAKE_ACCOUNT="myorg-myaccount"
export SNOWFLAKE_USER="svc_dsoa_deploy"
export SNOWFLAKE_PRIVATE_KEY_RAW="$(cat /path/to/private/key.pem)"

# Option A: With existing config
docker run --rm \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  -e SNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
  -e SNOWFLAKE_USER="$SNOWFLAKE_USER" \
  -e SNOWFLAKE_PRIVATE_KEY_RAW="$SNOWFLAKE_PRIVATE_KEY_RAW" \
  dsoa-deploy:local \
  --env=production \
  --scope=init \
  --options=manual,skip_confirm

# Option B: With --defaults (generates config, then deploys)
docker run --rm \
  -v ./conf:/app/conf \
  -e DTAGENT_TOKEN="$DTAGENT_TOKEN" \
  -e SNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
  -e SNOWFLAKE_USER="$SNOWFLAKE_USER" \
  -e SNOWFLAKE_PRIVATE_KEY_RAW="$SNOWFLAKE_PRIVATE_KEY_RAW" \
  -e DSOA_DT_TENANT="abc123.live.dynatrace.com" \
  -e DSOA_SF_ACCOUNT="myorg-myaccount" \
  -e DSOA_DEPLOYMENT_ENV="PRODUCTION" \
  dsoa-deploy:local \
  --env=production \
  --scope=init \
  --defaults \
  --options=skip_confirm
```

**Expected behavior:**
- Exit code: **0** (success)
- Output shows deployment progress
- Config file created (if using `--defaults`)
- SQL script generated and executed

### 1.5 Inspect Generated Artifacts

```bash
# View generated config
cat ./conf/config-production.yml

# View generated SQL script (if using --options=manual)
cat dsoa-deploy-script-PRODUCTION-*.sql | head -50
```

### 1.6 Clean Up

```bash
# Remove test config
rm -rf /tmp/dsoa-test-conf

# Remove test image
docker rmi dsoa-deploy:local
```

---

## Part 2: GitHub Workflow Testing

### Prerequisites

- `act` installed: https://github.com/nektos/act
- GitHub CLI (`gh`) installed (optional, for PR creation)
- Local git repository with remote configured

### 2.1 Test Locally with `act`

#### 2.1a Install `act`

```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | bash

# Verify
act --version
```

#### 2.1b Run the CI workflow locally

```bash
# List available workflows
act --list

# Run the lint job
act -j lint

# Run the test-bash job
act -j test-bash

# Run all jobs (full CI)
act
```

**Expected output:**
- All linting checks pass (black, flake8, pylint, sqlfluff, yamllint, markdownlint, shellcheck)
- All bash tests pass
- No errors or warnings

#### 2.1c Run the deployment workflow locally

The deployment workflow (`dsoa-deploy-template.yml`) requires secrets. Simulate them locally:

```bash
# Create a .secrets file for act
cat > .secrets << 'EOF'
DTAGENT_TOKEN=dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890
SNOWFLAKE_ACCOUNT=myorg-myaccount
SNOWFLAKE_USER=svc_dsoa_deploy
SNOWFLAKE_PRIVATE_KEY_RAW=-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7...
-----END PRIVATE KEY-----
EOF

# Run the deployment workflow with secrets
act workflow_dispatch \
  --secret-file .secrets \
  --input scope=init \
  --input from_version=""
```

**Expected behavior:**
- Docker image builds successfully
- Config is generated (if using `--defaults`)
- Deployment proceeds without errors

**Clean up:**

```bash
rm .secrets
```

### 2.2 Test on a Feature Branch (Safe)

Create a feature branch and push it to test the workflow on GitHub without merging to `main` or `devel`:

```bash
# Create a feature branch
git checkout -b test/docker-workflow-validation

# Make a small change (e.g., update a comment)
echo "# Test workflow" >> README.md

# Commit and push
git add README.md
git commit -m "test: validate workflow on feature branch"
git push -u origin test/docker-workflow-validation
```

**On GitHub:**
1. Go to **Actions** tab
2. Select the **Quality Checks** workflow
3. Verify all jobs pass (lint, test-bash, test-documentation)

**Optional: Trigger deployment workflow manually**

1. Go to **Actions** → **Deploy DSOA to Snowflake**
2. Click **Run workflow**
3. Select your feature branch
4. Set `scope=init` and leave `from_version` empty
5. Click **Run workflow**

**Expected behavior:**
- Workflow runs on the feature branch
- All steps complete successfully
- No changes to `main` or `devel`

**Clean up:**

```bash
# Delete the feature branch locally
git branch -d test/docker-workflow-validation

# Delete the remote branch
git push origin --delete test/docker-workflow-validation
```

### 2.3 Validate Workflow Syntax

Check the workflow YAML for syntax errors without running it:

```bash
# Install yamllint if not already installed
pip install yamllint

# Validate workflow files
yamllint .github/workflows/dsoa-deploy-template.yml
yamllint .github/workflows/ci.yml
```

**Expected output:** No errors or warnings.

### 2.4 Inspect Workflow Logs

After running a workflow on GitHub:

1. Go to **Actions** tab
2. Click the workflow run
3. Expand each job to see logs
4. Look for:
   - **Build step:** Docker image built successfully
   - **Deploy step:** Config generated, deployment executed
   - **Errors:** Any failures in setup or deployment

---

## Part 3: Integration Testing

### 3.1 Test `--defaults` with Bats

The bats test suite includes comprehensive tests for `--defaults` mode:

```bash
# Run all defaults tests
.venv/bin/pytest test/bash/test_defaults_mode.bats -v

# Or with bats directly
bats test/bash/test_defaults_mode.bats
```

**Expected output:** All tests pass.

### 3.2 Test Deploy Script Flags

```bash
# Run tests for new deploy flags
bats test/bash/test_deploy_new_flags.bats
```

**Expected output:** All tests pass.

### 3.3 Full Test Suite

```bash
# Run all bash tests
./test/bash/run_tests.sh

# Or with pytest
.venv/bin/pytest test/bash/ -v
```

**Expected output:** All tests pass, no failures.

---

## Part 4: Troubleshooting

### Docker image build fails

**Problem:** `ERROR: Build artifacts are missing`

**Solution:**
```bash
./scripts/dev/build.sh
make docker-build
```

### `--defaults` exits with non-zero code

**Problem:** Config generation fails

**Check:**
```bash
# Verify DSOA_DT_TENANT is set
echo $DSOA_DT_TENANT

# Verify it's a valid Dynatrace tenant address
# Format: abc123.live.dynatrace.com or abc123.sprint.dynatrace.com
```

### Docker container exits immediately

**Problem:** Container runs but exits without output

**Debug:**
```bash
# Run with verbose output
docker run --rm dsoa-deploy:local --help 2>&1 | head -50

# Check image contents
docker run --rm dsoa-deploy:local ls -la /app/
docker run --rm dsoa-deploy:local ls -la /app/build/
```

### Workflow fails on GitHub

**Check:**
1. **Secrets are set:** Go to **Settings** → **Secrets and variables** → **Actions**
2. **Workflow syntax:** Run `yamllint .github/workflows/*.yml`
3. **Logs:** Click the failed workflow run and expand each step

### Config file not created

**Problem:** `--defaults` runs but no config file appears

**Check:**
```bash
# Verify volume mount
docker run --rm \
  -v /tmp/test-conf:/app/conf \
  dsoa-deploy:local \
  --env=test \
  --defaults

# Check if file was created
ls -la /tmp/test-conf/
```

---

## Part 5: Validation Checklist

Use this checklist to validate the Docker image and workflows:

- [ ] Docker image builds without errors
- [ ] `docker run dsoa-deploy:local --help` shows full help text
- [ ] `--defaults` with `DSOA_DT_TENANT` generates config and exits 0
- [ ] `--defaults` without `DSOA_DT_TENANT` fails with error message
- [ ] `--defaults` with existing config uses it without regenerating
- [ ] Config file contains correct values from env vars
- [ ] Full deployment with Snowflake credentials succeeds
- [ ] CI workflow passes all lint and test jobs
- [ ] Deployment workflow can be triggered manually on feature branch
- [ ] All bats tests pass (`test/bash/test_defaults_mode.bats`)
- [ ] No secrets are exposed in logs or artifacts

---

## References

- [Docker Deployment Guide](../deployment/docker.md)
- [Local Deployment Guide](../deployment/deploy.md)
- [GitHub Actions Guide](../deployment/github-actions.md)
- [deploy.sh source](../../scripts/deploy/deploy.sh)
- [Dockerfile](../../Dockerfile)
- [Bats tests](../../test/bash/test_defaults_mode.bats)

# Quick Reference: Docker & Workflow Testing

## Docker Image Testing (5 min)

```bash
# Build
./scripts/dev/build.sh && make docker-build

# Smoke test
docker run --rm dsoa-deploy:local --help

# Test --defaults (config generation)
export DSOA_DT_TENANT="abc123.live.dynatrace.com"
export DSOA_SF_ACCOUNT="myorg-myaccount"
mkdir -p /tmp/dsoa-test-conf

docker run --rm \
  -v /tmp/dsoa-test-conf:/app/conf \
  -e DSOA_DT_TENANT="$DSOA_DT_TENANT" \
  -e DSOA_SF_ACCOUNT="$DSOA_SF_ACCOUNT" \
  dsoa-deploy:local \
  --env=test \
  --defaults

# Verify config was created
cat /tmp/dsoa-test-conf/config-test.yml
```

**Expected:** Exit 0, config file created with correct values.

---

## GitHub Workflow Testing (10 min)

### Option A: Local with `act`

```bash
# Install act (one-time)
brew install act

# Run CI locally
act -j lint
act -j test-bash

# Run all jobs
act
```

**Expected:** All jobs pass.

### Option B: On Feature Branch (Safe)

```bash
# Create feature branch
git checkout -b test/docker-validation

# Push to GitHub
git push -u origin test/docker-validation

# On GitHub: Actions tab → Quality Checks → verify all pass
# Optional: trigger Deploy workflow manually
```

**Expected:** All checks pass on feature branch, no impact on `main`/`devel`.

---

## Key Behaviors to Verify

| Scenario | Command | Expected |
|---|---|---|
| **Config generation** | `--defaults` with `DSOA_DT_TENANT` | Exit 0, config file created |
| **Missing env var** | `--defaults` without `DSOA_DT_TENANT` | Exit non-zero, error message |
| **Existing config** | `--defaults` with pre-existing config | Exit 0, config unchanged |
| **Help text** | `docker run dsoa-deploy:local --help` | Full help output |
| **CI lint** | `act -j lint` | All linters pass |
| **CI tests** | `act -j test-bash` | All bash tests pass |

---

## Troubleshooting

| Problem | Check |
|---|---|
| Build fails | `./scripts/dev/build.sh` first |
| `--defaults` fails | `echo $DSOA_DT_TENANT` (must be set) |
| Docker exits immediately | `docker run dsoa-deploy:local ls -la /app/build/` |
| Workflow fails on GitHub | Check **Settings** → **Secrets** are set |

---

## Full Checklist

- [ ] Docker image builds
- [ ] `--help` works
- [ ] `--defaults` generates config (exit 0)
- [ ] `--defaults` fails without `DSOA_DT_TENANT`
- [ ] Config file has correct values
- [ ] CI lint passes
- [ ] CI tests pass
- [ ] Feature branch workflow passes
- [ ] Bats tests pass: `bats test/bash/test_defaults_mode.bats`

---

See [MANUAL_TESTING.md](MANUAL_TESTING.md) for detailed step-by-step instructions.

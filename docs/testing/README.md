# Testing Documentation

Comprehensive guides for testing DSOA Docker images and GitHub workflows.

## Quick Navigation

### 🚀 Start Here
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — 5-minute cheat sheet with essential commands

### 📖 Detailed Guides
- **[MANUAL_TESTING.md](MANUAL_TESTING.md)** — Step-by-step instructions for all testing scenarios
- **[TESTING_CONTEXT.md](TESTING_CONTEXT.md)** — Why we test, what changed, and what to validate

## What's Covered

### Docker Image Testing
- Building the image locally
- Testing `--defaults` mode (config generation)
- Testing with missing env vars
- Testing with existing config
- Full deployment with Snowflake + Dynatrace

### GitHub Workflow Testing
- Running CI locally with `act`
- Testing on feature branches safely
- Validating workflow syntax
- Inspecting workflow logs

### Integration Testing
- Running bats test suite
- Validating deploy script flags
- Full test suite execution

## Key Scenarios

| Scenario | Time | Guide |
|---|---|---|
| Quick smoke test | 5 min | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |
| Docker image validation | 15 min | [MANUAL_TESTING.md](MANUAL_TESTING.md#part-1-docker-image-testing) |
| Workflow testing locally | 10 min | [MANUAL_TESTING.md](MANUAL_TESTING.md#part-2-github-workflow-testing) |
| Full integration test | 30 min | [MANUAL_TESTING.md](MANUAL_TESTING.md#part-3-integration-testing) |
| Understanding the changes | 10 min | [TESTING_CONTEXT.md](TESTING_CONTEXT.md) |

## Recent Changes

The `--defaults` mode in `deploy.sh` was fixed to:
- Exit with code **0** after config generation (previously may have failed)
- Skip build artifact check when generating config only
- Read env vars: `DSOA_DT_TENANT`, `DSOA_SF_ACCOUNT`, `DSOA_DEPLOYMENT_ENV`
- Respect existing config files (no overwrite)

This enables **non-interactive CI/CD deployments** via Docker and GitHub Actions.

## Validation Checklist

Before merging or deploying, verify:

- [ ] Docker image builds
- [ ] `--defaults` generates config (exit 0)
- [ ] `--defaults` fails without required env vars
- [ ] Existing config is not overwritten
- [ ] Full deployment works
- [ ] CI workflow passes
- [ ] Deployment workflow works on feature branch
- [ ] All bats tests pass

## Files Tested

- `scripts/deploy/deploy.sh` — Deployment script with `--defaults` mode
- `Dockerfile` — Docker image definition
- `.github/workflows/dsoa-deploy-template.yml` — GitHub Actions workflow
- `test/bash/test_defaults_mode.bats` — Comprehensive tests

## Getting Started

1. **First time?** Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. **Need details?** Follow [MANUAL_TESTING.md](MANUAL_TESTING.md)
3. **Want context?** See [TESTING_CONTEXT.md](TESTING_CONTEXT.md)

## Related Documentation

- [Docker Deployment Guide](../deployment/docker.md)
- [Local Deployment Guide](../deployment/deploy.md)
- [GitHub Actions Guide](../deployment/github-actions.md)
- [Contributing Guide](../CONTRIBUTING.md)

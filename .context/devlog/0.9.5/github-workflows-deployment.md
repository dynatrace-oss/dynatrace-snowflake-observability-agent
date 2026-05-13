# [0.9.5] — GitHub Workflows as Deployment Option

## Docker + GitHub Actions Deployment — Full Implementation

**Scope**: Adds Docker-based and GitHub Actions CI/CD deployment paths to DSOA. Removes legacy `service_user` option. Adds `--defaults` non-interactive config generation and `--ci-export=github` wizard flag.

**Phase A — `service_user` removal and env-var auto-detection**:

- Removed `service_user` from `deploy.sh --options` help text and all execution paths.
- New behavior: when `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` env vars are both set, `deploy.sh` automatically uses `snow sql --temporary-connection --account "$SNOWFLAKE_ACCOUNT" --user "$SNOWFLAKE_USER"`. This replaces the old `service_user` path cleanly without requiring an explicit option flag.
- `setup.sh` detects the same env vars and skips `snow connection add` — prints a message that `--temporary-connection` will be used automatically.
- The `#%DEV:` block for `service_user` DTAGENT_TOKEN check was removed. The `#%DEV:` block for the named-connection `snow sql` call is preserved (it wraps the fallback path).
- BATS tests updated: removed `service_user` assertions, added tests for both env-var and named-connection paths.

**Phase B — Dockerfile and Makefile**:

- `Dockerfile` at repo root: `python:3.11-slim` base, installs `bash curl jq gawk yq snowflake-cli-labs`. Copies `build/`, `scripts/deploy/`, `conf/config-template.yml`, `src/assets/`. Entrypoint: `./scripts/deploy/deploy.sh`.
- `.dockerignore`: excludes `.git/`, `.venv/`, `test/`, `docs/`, `.github/`, `conf/config-*.yml` (except template), `.logs/`, `__pycache__/`, `*.pyc`. Does NOT exclude `build/` — required for Docker context.
- `Makefile` targets: `docker-build` (warns if `build/` missing), `docker-test` (smoke-tests `--help`).

**Phase C — `--defaults` refactor**:

- Previous `--defaults` implementation: generated a static skeleton config and exited. New behavior:
  - If config doesn't exist: generates from `DSOA_DT_TENANT`, `DSOA_DEPLOYMENT_ENV` (falls back to `$ENV` uppercased), `DSOA_SF_ACCOUNT` env vars using `yq -n`. Fails with error if `DSOA_DT_TENANT` is missing.
  - If config exists: uses it as-is, prints message.
  - Always implies `skip_confirm` (appended to OPTIONS array).
  - Does NOT exit — continues to deployment.
- Build artifact check updated: `--defaults` without existing config skips the build check (config-only operation). `--defaults` with existing config requires build artifacts (proceeds to deploy).

**Phase D — `--ci-export=github`**:

- New `CI_EXPORT` global var in `interactive_wizard.sh`. New `--ci-export=<platform>` argument.
- New `export_github_ci()` function: reads version from `build/config-default.yml`, substitutes `__ENV__`, `__VERSION__`, `__SF_USER__` in templates, writes `.github/workflows/dsoa-deploy.yml` and `GITHUB_SECRETS_SETUP.md`.
- Templates in `src/assets/ci-templates/github/`: `dsoa-deploy.yml.template` (GitHub Actions workflow with `workflow_dispatch`, Docker-based deploy step), `GITHUB_SECRETS_SETUP.md.template` (key-pair auth setup guide).
- Called after `config_persistence` in `main()`. Unknown platform → error + exit 1.

**Phase E — Release workflow and package**:

- `.github/workflows/release.yml`: new `build-and-push-docker` job (needs `build-and-release`, runs on tag push). Builds DSOA artifacts, logs into GHCR, pushes `ghcr.io/dynatrace-oss/dsoa-deploy:<tag>` and `:latest`.
- `.github/workflows/dsoa-deploy-template.yml`: reference template for customers. `on: workflow_dispatch` only — never auto-triggered in DSOA repo. Shipped in release ZIP.
- `scripts/dev/package.sh`: includes `docs/deployment/*.md` → `package/docs/deployment/` and `.github/workflows/dsoa-deploy-template.yml` → `package/dsoa-deploy-template.yml`.

**Phase F — Documentation**:

- New `docs/deployment/` directory: `deploy.md` (local), `docker.md` (Docker), `github-actions.md` (GitHub Actions).
- `docs/INSTALL.md` slimmed to ~100 lines: Docker as primary quick-start, brief sections for deploy.sh and GitHub Actions, links to deployment guides.
- `docs/INSTALL_ADVANCED.md`: added cross-links to deployment guides at top.

**Test coverage**:

- `test/bash/test_deployment_scripts.bats`: 3 new tests (temp-connection path, named-connection path, help text no `service_user`).
- `test/bash/test_defaults_mode.bats`: 6 new tests covering all `--defaults` scenarios.
- `test/bash/test_ci_export.bats`: 7 new tests covering `export_github_ci()` function and unknown platform error.

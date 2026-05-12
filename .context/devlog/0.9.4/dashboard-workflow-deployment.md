# Dashboard and Workflow Deployment Script

- **Motivation**: Dynatrace dashboards and workflows were previously imported manually through the UI. This was error-prone,
  not reproducible, and blocked CI/CD automation of the full observability stack.
- **Solution**: New `scripts/deploy/deploy_dt_assets.sh` script uses `dtctl apply` to deploy YAML-sourced dashboards and
  workflows directly to a Dynatrace tenant.
- **YAML → dtctl envelope**: Dashboard YAMLs contain raw content (tiles, variables, layouts) without top-level `id`/`name`.
  The script wraps them in a `{name, type, content}` envelope via `jq`. If an `id` is present in the JSON (post-round-trip),
  it is popped out of `content` and placed at the envelope level — matching `dtctl`'s expected structure.
- **Asset name extraction**: Human-readable names are read from `# DASHBOARD:` / `# WORKFLOW:` comments in the YAML files
  (existing convention from `package.sh`). Falls back to directory name if comment is absent.
- **Idempotency**: First deploy creates with auto-generated ID; subsequent deploys update in place once the ID is
  stored back in the YAML.
- **`dt_assets` scope in `deploy.sh`**: Added opt-in scope at the end of `deploy.sh` (after `send_bizevent FINISHED`).
  Deliberately excluded from the default `all` scope — `dtctl` is optional and not a standard deployment dependency.
  The scope passes `--dry-run` through via `$DRY_RUN_FLAG`.
- **Error handling**: Per-asset failures are logged but do not abort the run; remaining assets continue. Exit code reflects
  overall success/failure.
- **Tests**: 16 bats tests in `test/bash/test_deploy_dt_assets.bats` covering argument validation, dtctl availability,
  scope filtering, dry-run passthrough, YAML→JSON conversion, missing directories, summary output, and
  name extraction from comments.
- **New directory**: `docs/workflows/` created with `README.md` as placeholder for upcoming workflow YAMLs.
- **Docs updated**: `docs/INSTALL.md` — new `## Deploying Dashboards and Workflows` section; `docs/dashboards/README.md` —
  added deployment script as the recommended import method.

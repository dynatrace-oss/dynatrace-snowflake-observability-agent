# [Unreleased] — Interactive Deployment Wizard

**Scope**: Story to eliminate manual config creation friction for first-time DSOA users. Deliverables: shared bash library, 4-phase interactive wizard, `deploy.sh` flag enhancements, full BATS test suite.

## Architecture

- **`scripts/deploy/lib.sh`** (487 lines): Shared bash library sourced by wizard and deploy.sh. Includes:
  - **Logging helpers**: `log_info`, `log_ok`, `log_warn`, `log_error` (consolidates duplicated code from `deploy_dt_assets.sh` + `deploy_test_notebook.sh` for future refactoring).
  - **Prompt helpers**: `prompt_input()` (collects input with optional default + validation fn), `prompt_yesno()` (y/n), `prompt_select_one()` (bash `select` menu), `prompt_select_multi()` (y/n per item).
  - **Validators**: `validate_dt_tenant()` (accepts `*.live.dynatrace.com`, `*.sprint.dynatracelabs.com`, `*.dev.dynatracelabs.com`; auto-corrects `.apps.dynatrace.com` → `.live.dynatrace.com`), `validate_sf_account()` (format + optional HTTPS probe to `<account>.snowflakecomputing.com`), `validate_nonempty()`, `validate_alphanumeric()`.
  - **Probes**: `probe_dt_tenant()` + `probe_sf_account()` (HTTPS reachability checks; warn-don't-block on failure per story).
  - **Config helpers**: `read_config_key()` / `write_config_key()` (wraps `yq`).
  - All functions include Google-style docstrings for maintainability.

- **`scripts/deploy/interactive_wizard.sh`** (988 lines): Standalone wizard script. Five phases:
  1. **Phase 1 — Core Config**: Prompts for DT tenant, API token (silent `read -rs`), SF account, deployment env name, optional multitenancy tag. Auto-corrects `.apps.` to `.live.`. Pre-populates from existing config if in edit mode (`--existing-config=`).
  2. **Phase 2 — Deployment Scope**: `prompt_select_one()` menu with 9 options (full/init/init+admin/post-init/config-only/apikey/upgrade/teardown/dt_assets). If upgrade selected, prompts for `--from-version`.
  3. **Phase 3 — Plugin Selection**: Q1: All/None/Selected (shown as numbered list, user selects via bash `select` y/n per plugin). Q2: Deploy disabled plugin code? Sets `plugins.deploy_disabled_plugins`. Q3: Customize plugin settings? Walks through per-plugin knobs (schedule, thresholds) for each enabled plugin.
  4. **Phase 4 — Advanced Settings**: Optional (behind `prompt_yesno` gate). Log level, procedure timeout, resource monitor quota.
  5. **Phase 5 — Telemetry Settings**: Optional. OTel enable/disable per signal type, max consecutive API fails.
  - **Config persistence**: Generates YAML via heredoc + append. Offers: ① save new `conf/config-$ENV.yml`, ② overwrite existing config, ③ print to stdout, ④ discard. `--output=<file>` skips menu and writes directly. `--dry-run` prints to stdout without writing any file.
  - **Flags**: `--env=`, `--existing-config=`, `--dry-run`, `--output=`. Works with piped stdin for testing.

- **Modified `scripts/deploy/deploy.sh`**:
  - **New args**: `--env=<ENV>` (flag-based, replaces positional), `--interactive` (launch wizard), `--defaults` (generate minimal config non-interactively from `config-template.yml`).
  - **Backward compat**: Positional `$ENV` still works; emits deprecation warning suggesting `--env=`.
  - **Auto-trigger wizard**: When `conf/config-$ENV.yml` missing and `--defaults` not set, automatically invokes wizard.
  - **Validation**: Wizard's probes check DT tenant and SF account reachability; optional API token validation via metadata endpoint (all warnings, no hard blocks).

## Testing

- **`test/bash/test_lib.bats`** (156 lines, 19 tests): Unit tests for lib.sh validators, prompt helpers, config key accessors. Source lib.sh directly, test functions in isolation.
- **`test/bash/test_interactive_wizard.bats`**: Integration tests. Pipe stdin answers into wizard; validate generated YAML. Covers all phases, config persistence options, `--output=` and `--dry-run` flags.
- **`test/bash/test_deploy_new_flags.bats`**: Test deploy.sh flag behavior (`--env=`, `--interactive`, `--defaults`, positional deprecation). Includes integration test for `deploy.sh --interactive` with piped stdin (EOF) to verify wizard invocation path.

## Design decisions

1. **No external TUI frameworks** (no fzf/gum/whiptail/dialog) — bash `select` is sufficient for plugin checklist.
2. **HTTPS probes warn, don't block** — per story spec; users can proceed even if network unreachable.
3. **Auto-correct `.apps.` to `.live.`** — common user mistake; silently fixed improves UX.
4. **Bash `select` for multi-select** — simplest pure-bash solution; each item is y/n via separate `select` invocation (follows user's design choice).
5. **Config persistence via heredoc + append** — generates YAML with a heredoc for the core block, then appends optional sections. Overwrites the target file on save; does not merge/preserve comments from existing configs.
6. **Piped stdin testing** — wizard accepts EOF gracefully; tests pipe answers + validate output, no interactive mocking needed.

## Files changed

- `scripts/deploy/lib.sh` (new, 487 lines)
- `scripts/deploy/interactive_wizard.sh` (new, 568 lines)
- `scripts/deploy/deploy.sh` (modified, +119 lines)
- `test/bash/test_lib.bats` (new, 156 lines)
- `test/bash/test_interactive_wizard.bats` (new, 101 lines)
- `test/bash/test_deploy_new_flags.bats` (new, 160 lines)
- `docs/CHANGELOG.md` (updated, user-facing summary)

## Acceptance criteria met

- ✓ `./deploy.sh --env=test-qa --interactive` launches wizard
- ✓ `./deploy.sh --env=test-qa --defaults` generates config non-interactively
- ✓ `./deploy.sh test-qa --scope=...` (positional) works with deprecation warning
- ✓ Wizard generates valid YAML passing `prepare_config.sh` validation
- ✓ All BATS tests pass (32/32)
- ✓ `make lint` passes (pylint 10.00/10, shellcheck, markdownlint)
- ✓ No new runtime dependencies (bash builtins + jq/yq/curl/snow CLI only)
- ✓ Full backward compatibility (existing deploy.sh flows unchanged)

## Future work

- Extract log helpers from `deploy_dt_assets.sh` and `deploy_test_notebook.sh` to source lib.sh (scope creep, separate PR).
- GitHub Actions workflow generation as optional wizard output.
- SQL `USE` statement deduplication in `prepare_deploy_script.sh` (post-MVP optimization, noted in story).

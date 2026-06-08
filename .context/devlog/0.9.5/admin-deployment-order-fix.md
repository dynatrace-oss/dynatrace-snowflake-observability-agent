# Admin Deployment Order Fix (BIZOBS-115)

## Root Cause

The DSOA build pipeline assembled SQL scopes using numeric filename prefixes sorted alphabetically:
`00_init → 10_admin → 20_setup → 30_plugins → 40_config → 70_agents`. Because `10_admin.sql` ran
before `30_plugins/`, any Pattern B procedure (admin override + non-admin stub) was deployed in
the wrong order: the admin version was written first, then the plugin's non-admin stub clobbered it.

## PR #142 Trade-off

PR #142 worked around the ordering bug by inlining the admin override inside the non-admin file
using `--%OPTION:dtagent_admin:` blocks (`shares.sql/051_p_grant_imported_privileges.sql`). This
solved the overwrite problem but broke scope isolation: running `--scope=admin` independently
(the DBA path in managed deployments) would not deploy the admin procedure, because it lived in
the plugin scope rather than in `admin/`. This violated the deployment workflow contract.

## Fix

Renamed admin build output from `build/10_admin.sql` to `build/80_admin.sql`. Since
`prepare_deploy_script.sh` orders files using `sort`, `80_admin.sql` now sorts after
`70_agents.sql` and all `30_plugins/` files — guaranteeing admin runs last. No ordering
logic was changed beyond the filename prefix.

Reverted the PR #142 inline bundling: moved `P_GRANT_IMPORTED_PRIVILEGES` admin implementation
back to `shares.sql/admin/051_p_grant_imported_privileges.sql` (wrapped in `--%OPTION:dtagent_admin:`
as all admin/ files are). The non-admin stub in `shares.sql/051_p_grant_imported_privileges.sql`
now references only the stub itself, with no inline option blocks.

## Files Changed

1. `scripts/dev/build.sh` — admin output renamed `10_admin.sql` → `80_admin.sql`
1. `scripts/deploy/prepare_deploy_script.sh` — `admin` scope and `all` scope listing updated
1. `src/dtagent/plugins/shares.sql/051_p_grant_imported_privileges.sql` — stub only, no OPTION block
1. `src/dtagent/plugins/shares.sql/admin/051_p_grant_imported_privileges.sql` — restored admin version
1. `test/bash/test_execute_as_owner.bats` — exclusion path updated to `admin/` subdirectory
1. `test/core/test_admin_role_usage.py` — `TestAdminProcPattern` docstring and reference updated
1. `docs/PLUGIN_DEVELOPMENT.md` — Pattern B docs updated to describe two-file approach

## Deployment Contract

| Scope | Files included | Admin overrides? |
| --- | --- | --- |
| `init` | `00_init.sql` | No |
| `setup` | `20_setup.sql` | No |
| `plugins` | `30_plugins/*.sql` | No (stubs only) |
| `config` | `40_config.sql` | No |
| `agents` | `70_agents.sql` | No |
| `admin` | `80_admin.sql` | Yes (runs independently, DBA path) |
| `all` | all of the above, admin last | Yes |

## Pattern B Semantics (Updated)

Two-file approach — no inline option blocks in non-admin files:

1. `{plugin}.sql/{name}.sql` — non-admin stub (`execute as caller`, returns warning), always deployed
1. `{plugin}.sql/admin/{name}.sql` — admin override (`execute as owner`), wrapped in `--%OPTION:dtagent_admin:`

Ordering guarantees correctness: `30_plugins/` runs before `80_admin.sql`, so `create or replace`
in the admin file always overwrites the stub when admin scope is enabled.

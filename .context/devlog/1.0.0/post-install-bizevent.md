# Post-install verification bizevent

## Problem

A successful `deploy.sh` run only proves that the SQL statements executed against Snowflake
without error. It does not prove that Snowflake itself can reach the configured Dynatrace tenant
at runtime — a bad token, a missing/incorrect network rule, or a wrong tenant URL would still let
the deploy "succeed" while every subsequent plugin run silently fails to send telemetry. The
existing `scripts/deploy/send_bizevent.sh` STARTED/FINISHED bizevents don't catch this either,
since they're sent via `curl` directly from the deploying machine, not from inside Snowflake.

## Solution

A new build stage, `build/90_finalize.sql` (built from `src/dtagent.sql/finalize/`), calls
`APP.SEND_TELEMETRY()` from within Snowflake to send a `dsoa.installation` bizevent. It is
appended as the literal last statement of the generated deploy script for `scope=all`,
`scope=upgrade`, `scope=apikey` (standalone or as part of any scope combo including `apikey`) —
after the apikey/config-refresh block and any disabled-plugin task suspend/cleanup statements,
since those are appended even later than the main `SQL_FILES` concatenation in
`prepare_deploy_script.sh`. The `apikey` trigger was added after the initial `all`/`upgrade`-only
version shipped: verifying the token from inside Snowflake is most useful right when it's
(re)deployed, so the condition checks `INCLUDE_APIKEY` (already true for `all`, standalone
`apikey`, and any combo containing `apikey`) instead of a literal `SCOPE == "all"` check. It is
gated behind the existing `plugins.self_monitoring.send_bizevents_on_deploy` config flag (same
flag `send_bizevent.sh` already uses), so it can be disabled without introducing a new config key.

Payload is intentionally minimal: `event.type`, `message`, and `dsoa.deployment.parameter` (the
deploy scope). `deployment.environment.tag` and `app.version`/`app.short_version` are **not**
set manually — `BizEvents._pack_event_data` (`src/dtagent/otel/events/bizevents.py`) already
injects them from resource attributes for every event sent through `SEND_TELEMETRY`.

## Why not just append it to `70_agents.sql` or `80_admin.sql`?

Files are concatenated via `find | sort`, relying on the two-digit numeric prefix convention.
`80_admin.sql` already runs after `70_agents.sql` for `scope=all`, but neither is actually last:
`prepare_deploy_script.sh` appends an apikey/config-refresh block (`update_secret.sh` +
`CONFIG.UPDATE_FROM_CONFIGURATIONS()`) whenever `scope=all`, and separately injects
`alter task ... suspend` statements for any disabled plugins — both happen after the main
`SQL_FILES` concatenation. A first pass that added `90_finalize.sql` to `map_scope_to_files()`'s
`all`/`upgrade` cases landed before both of those blocks and was caught by the new bats test
(`test/bash/test_prepare_deploy_script.bats`) asserting the bizevent call is the last non-blank
line of the generated script. The fix appends `build/90_finalize.sql` explicitly, after the
apikey block and the plugin suspend/cleanup injection, but before the TAG/identifier substitution
pass — so multitenancy renaming (`DTAGENT_DB` → `DTAGENT_<TAG>_DB`) still applies to it.

## Failure isolation

`connector.py`'s `TelemetrySender.main()` has a latent bug: on `RuntimeError` (too many
consecutive send failures) it falls through to `return results` without `results` ever being
assigned, raising `UnboundLocalError` instead of returning cleanly. Rather than fix shared
`connector.py` code used by every `SEND_TELEMETRY`/plugin caller (out of scope for this change),
`900_p_send_install_bizevent.sql` wraps the call in its own `execute immediate` anonymous block
with `exception when other then`, so any failure — including that bug — is caught and reported
without failing the deploy script. The underlying `connector.py` bug should be tracked and fixed
separately.

## Files touched

- `src/dtagent.sql/finalize/900_p_send_install_bizevent.sql` (new)
- `scripts/dev/build.sh` — assembles `finalize/` into `build/90_finalize.sql`
- `scripts/deploy/prepare_deploy_script.sh` — fetches `SEND_INSTALL_BIZEVENT` flag, appends
  `build/90_finalize.sql` after the apikey/config-refresh and plugin-suspend/cleanup blocks
  (gated on `INCLUDE_APIKEY || HAS_UPGRADE_SCOPE`), substitutes `__DSOA_DEPLOY_SCOPE__`
- `test/bash/test_prepare_deploy_script.bats` — 7 tests covering ordering, scope substitution,
  gating, and the standalone/combo `apikey` scope cases

# Resource Monitor Ownership Warning & Resilience

## Problem

When a user modifies the `DTAGENT_RS` resource monitor quota via the Snowflake Web UI using a role
other than `DTAGENT_OWNER` (most commonly `ACCOUNTADMIN`, which is the UI default), Snowflake
reassigns OWNERSHIP and MODIFY grants on that resource monitor to the role that made the change.

This causes `P_UPDATE_RESOURCE_MONITOR` to fail during `scope=config` deployment because
`DTAGENT_OWNER` no longer has the necessary privileges to ALTER the resource monitor. The same
applies to tagged deployments where `DTAGENT_$TAG_OWNER` owns `DTAGENT_$TAG_RS`.

## Root Cause

Snowflake's implicit ownership semantics: any role that ALTERs a resource monitor via the UI
(or SQL) takes ownership if it has sufficient privileges. The `ACCOUNTADMIN` role always has
sufficient privileges, so using it in the Web UI silently steals ownership from `DTAGENT_OWNER`.

## Fix

### 1. Graceful Exception Handling (Code)

Added `EXCEPTION WHEN OTHER THEN system$log_warn(...)` at two levels:

- **Inside `P_UPDATE_RESOURCE_MONITOR`** (`035_p_update_resource_monitor.sql`): the procedure
  itself now catches the permission error, logs a descriptive warning message explaining the
  likely cause and fix, and returns `1` instead of raising an exception.

- **At the call site in `UPDATE_FROM_CONFIGURATIONS`** (`038_p_update_from_configuration.sql`):
  the call to `P_UPDATE_RESOURCE_MONITOR` is wrapped in a `BEGIN...EXCEPTION...END` block
  (same pattern as `SETUP_EVENT_TABLE`), ensuring the rest of the configuration update
  (warehouse timeout, data retention, plugin schedules) proceeds even if the resource monitor
  update fails.

### 2. Documentation Warning

Added a prominent `> [!CAUTION]` admonition to `docs/INSTALL_ADVANCED.md` in the
"Required vs Optional Objects" section explaining:
- Do not modify the resource monitor via Snowflake UI with any role other than DTAGENT_OWNER
- What happens if ACCOUNTADMIN is used (ownership reassignment)
- How to fix it (re-run `scope=init`)
- How to change quota safely (config YAML or switch role in UI)

Added a troubleshooting entry to `docs/INSTALL.md` for users who hit the error.

## Files Changed

| File | Change |
|------|--------|
| `src/dtagent.sql/setup/035_p_update_resource_monitor.sql` | Added exception handler |
| `src/dtagent.sql/setup/038_p_update_from_configuration.sql` | Wrapped call in begin/exception block |
| `docs/INSTALL_ADVANCED.md` | Added `> [!CAUTION]` warning box |
| `docs/INSTALL.md` | Added troubleshooting entry |
| `docs/CHANGELOG.md` | User-facing entry |

## Recovery Path

If a user has already hit this issue:

```bash
# Re-run init scope to restore resource monitor ownership to DTAGENT_OWNER
./scripts/deploy/deploy.sh --env=<ENV> --scope=init --options=skip_confirm
```

This re-executes `005_resource_monitor.sql` which grants ownership back to `DTAGENT_OWNER`.

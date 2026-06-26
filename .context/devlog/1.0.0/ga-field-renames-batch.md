# GA Field Renames Batch (Semantic Dictionary Alignment)

## Problem

A set of emitted telemetry field names did not follow Dynatrace Semantic Dictionary (SD) /
OpenTelemetry conventions: bare namespace parents used as string leaves, `_type` suffixes that
imply enums, array leaves without the `.list` signal, un-namespaced control fields (`session.id`,
`status.code`, `status.message`), an orphaned `warehouses.*` top-level namespace, and
`plugins.*` config-surface attributes living outside the `dsoa.*` namespace.

This is a **pure rename batch** — no query logic, algorithms, or Snowflake API columns change.
Only the emitted attribute/dimension/metric key strings (and the Python keys that read them back)
change. Shipped as part of the 1.0.0 SD-alignment effort tracked in
[Appendix C](../../../docs/APPENDIX.md#appendix-c-sec).

## Renames

| Current                                   | GA                                            | Plugin            |
|-------------------------------------------|-----------------------------------------------|-------------------|
| `snowflake.warehouse.owner`               | `snowflake.warehouse.owner.name`              | resource_monitors |
| `snowflake.warehouse.owner.role_type`     | `snowflake.warehouse.owner.role`              | resource_monitors |
| `snowflake.budget.owner`                  | `snowflake.budget.owner.name`                 | budgets           |
| `snowflake.budget.owner.role_type`        | `snowflake.budget.owner.role`                 | budgets           |
| `snowflake.task.config`                   | `snowflake.task.config.id`                    | tasks             |
| `snowflake.user.name`                     | `snowflake.user.name.login`                   | users             |
| `snowflake.user.privilege`                | `snowflake.user.privilege.name`               | users             |
| `snowflake.user.roles.direct`             | `snowflake.user.roles.direct.list`            | users             |
| `snowflake.warehouses.names`              | `snowflake.resource_monitor.warehouses`       | resource_monitors |
| `snowflake.resource_monitor.warehouses`   | `snowflake.resource_monitor.warehouses.count` | resource_monitors |
| `session.id`                              | `snowflake.session.id`                        | query_history, active_queries, login_history |
| `status.code`                             | `snowflake.status.code`                       | login_history     |
| `status.message`                          | `snowflake.status.message`                    | login_history, trust_center |

## Implementation notes

### resource_monitors metric/attribute name swap

`snowflake.resource_monitor.warehouses` was already in use as a **metric** (the integer count of
warehouses attached to a monitor, `array_size(dv.warehouses)`). The orphaned attribute
`snowflake.warehouses.names` (the `string[]` of warehouse names) is the natural owner of that
namespace, so the count metric was renamed to `snowflake.resource_monitor.warehouses.count` to
free the name, and the name list took over `snowflake.resource_monitor.warehouses`. Ordering
matters anywhere a sequential rewrite is applied (CSV migration, fixtures): the metric→`.count`
rename must run **before** the names→`warehouses` rename.

### `plugins.query_history.*` NOT renamed (dropped from scope)

The spec's `plugins.* → dsoa.plugins.*` item targeted `plugins.query_history.obfuscation_mode`
and `.track_ddl_changes`. Investigation showed both are **config keys**, not emitted telemetry:
they are read via `Configuration.get()` / `F_GET_CONFIG_VALUE('plugins.query_history.…')`, whose
resolution is built around the `plugins.` prefix in `config.py`. The documentation cross-check
(`test/list_semantics.py`) extracts the `f_get_config_value('plugins.query_history.obfuscation_mode', …)`
string from inside the `ATTRIBUTES` `OBJECT_CONSTRUCT` and treats it as a documented field, so the
instruments-def name is pinned to the config-key string. Renaming only instruments-def breaks that
check; renaming the config key itself would change config-resolution logic (out of scope for a pure
rename, and would break the `plugins.` prefix used by every plugin). Decision: leave
`plugins.query_history.obfuscation_mode` and `.track_ddl_changes` unchanged. A dedicated
config-namespace migration can revisit this later.

### `status.code` / `status.message` read-back

`status.code` drives generic log-level selection in `Plugin.get_log_level` and
`Connector` (ad-hoc telemetry), and `status.message` is read in `login_history.py` for the failed
-login event message. All three read-back sites were updated to the namespaced keys so log-level
and event-message behavior is preserved.

### event_log echo

`event_log` re-emits prior OTLP logs from the Snowflake event table; an echoed `query_history`
log carried `session.id`. Since `query_history` now emits `snowflake.session.id`, the echoed
value follows — fixtures were updated accordingly.

## Migration

All renames are appended to `src/assets/appx-c-query-step-operator-refactoring.csv` and surface in
`docs/APPENDIX.md`. Customers run `refactor_field_names.sh` against exported assets. Note the
script does unanchored global substitution, so bare→child renames where siblings exist (e.g.
`snowflake.user.privilege` alongside `.privilege.grants_on`) will also rewrite the sibling
prefixes in customer assets — a pre-existing limitation of the tool (same as the existing
`snowflake.credits.quota` → `.value` entry), best-effort, customers should verify.

## Out of scope

- `snowflake.warehouse.event` → `.event.trigger` code path (BIZOBS-1938; the migration row already
  existed in appx-c).
- `snowflake.user.roles.direct.removed` / `.removed_on` siblings (not part of this batch).
- Dashboard/workflow DQL updates (tracked separately).

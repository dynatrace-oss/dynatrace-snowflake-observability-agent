# Semantic Dictionary Export — IA Fixes

## Summary

Fixed a set of information-architecture defects in the SD export pipeline and the
`instruments-def.yml` source files identified during pre-submission IA review.

## Changes

### A1 — Group ID collision fix (`_RES_NS`)

**Problem:** Two resource-field group IDs collided with signal-field group IDs of the same name:

- `("snowflake.warehouse", "snowflake.warehouse", "resource")` in `_RES_NS` collided with
  `("snowflake.warehouse", "snowflake.warehouse", "attribute_group")` in `_SIG_NS`.
- `("db", "db", "resource")` in `_RES_NS` collided with `("db", "db", "attribute_group")`
  in `_SIG_NS`.

**Fix:** Renamed resource group IDs to carry a `.resource` suffix:

- `snowflake.warehouse.resource` (resource group for warehouse-scoped resource fields)
- `db.resource` (resource group for db-scoped resource fields)

**Test:** Updated `test_warehouse_resource_group` to assert the new ID; added
`test_db_resource_group`.

---

### A2 — Enum union dedup (`_merge_field_entries`)

**Problem:** The dedup loop in `export()` used first-seen-wins for all duplicate keys.
Five fields had their enum-rich definition discarded because a different plugin defined
the same key first (without `__enum`):

- `db.operation.name`, `snowflake.query.execution_status`, `snowflake.warehouse.type`,
  `snowflake.object.type`, `snowflake.object.ddl.operation`

**Fix:** Extracted `_merge_field_entries(key, existing, incoming)`:

- No-enum → enum: upgrade to enum-rich definition.
- Enum + enum: union members by value (first-seen wins for dupes); `allow_custom_values = OR`.
- No-enum + no-enum: first-seen wins unchanged.

**Tests:** `TestMergeFieldEntries` — four cases covering all merge scenarios.

---

### A3 — Dimension ownership tracking (`dim_plugins`)

**Problem:** `_select_interfaces()` and `_build_metric_model_yaml()` used
`dim_meta["plugin"] != m_plugin` to decide if a no-`__context_names` dimension belongs to a
plugin. But after dedup, `dim_meta["plugin"]` stores only the dedup winner's plugin, so
later-defined plugins that also own the dimension (but lost dedup) got no dimension refs in
their metric models.

**Fix:**

- Built `dim_plugins: Dict[str, Set[str]]` during the parse loop, recording every plugin
  that defines each dimension key (before dedup filtering).
- Added optional `dim_plugins` parameter to `_select_interfaces()` and
  `_build_metric_model_yaml()`. When provided, the check becomes:
  `m_plugin not in dim_plugins.get(dim_key, set())`.
- Updated `export()` caller to pass `dim_plugins`.

**Test:** `TestDimPluginsOwnership.test_dim_from_discarded_plugin_appears_in_metric_model` —
verifies that a dimension defined in plugin_b (but dedup-won by plugin_a) appears in plugin_b's
metric model when `dim_plugins` is passed.

---

### A4 — Remove ref: nodes from field definition files

**Problem:** `_build_resource_fields_yaml` included `semdict == "ref"` entries (host.name,
service.name, etc.) in `dsoa.yaml`. This produced `ref:` nodes in a field definition file,
which is incorrect SD structure. Refs belong exclusively in the `i.dsoa_resource` interface
(already emitted by `_build_interfaces_yaml`).

**Fix:** Excluded `semdict == "ref"` from both `dsoa_keys` and `snowflake_keys` in
`_build_resource_fields_yaml`. Updated docstring to explain the intent.

**Test:** Updated `test_dsoa_resource_file_has_dsoa_fields` to assert no `ref:` nodes in the
dsoa group's attributes list.

---

### B-bool — Boolean field type annotations

**Problem:** All boolean fields emitted as `type: string` because no `__type` annotation was
present. String examples `"true"` and `"false"` were also incorrect SD YAML.

**Fix:**

- Added `_coerce_attribute_example()` to convert Python `True`/`False` (from YAML `true`/`false`)
  to lowercase strings `"true"`/`"false"` for the semconv `examples:` list.
- Updated `_emit_id_entry()` to use `_coerce_attribute_example()` instead of `str()`.
- Added `__type: boolean` + `__example: true/false` (YAML booleans) to all boolean fields in:
  - `resource_monitors.config`: `is_active`, `has_query_acceleration_enabled`,
    `is_auto_resume`, `is_auto_suspend`, `is_current`, `is_default`, `is_unmonitored`
  - `users.config`: `ext_authn.duo`, `has_mfa`, `has_password`, `has_pat`, `has_rsa`,
    `has_workload_identity`, `is_disabled`, `is_locked`, `is_from_organization`,
    `must_change_password`
  - `query_history.config`: `is_client_generated`, `with_operator_stats`;
    `track_ddl_changes` (YAML bool example only — no `__type` as it's runtime-defined)
  - `tasks.config`: `config.allow_overlap`

**Tests:** `TestAttributeExampleCoercion` — four unit tests covering True/False/string/int.

---

### B-long — Long integer and epoch-ns type annotations

**Problem:** Integer and epoch-nanosecond fields emitted as `type: string`.

**Fix:** Added `__type: long` to:

- Integer fields: `warehouse.clusters.count`, `query.operator.id`, `query.hash_version`
  (fixed example `v1` → `1`), `query.parametrized_hash_version` (fixed example `v1` → `1`),
  `query.accel_est.upper_limit_scale_factor`, `dsoa.debug.span.events.added/failed`,
  `copy.first_error.line_number`, `copy.first_error.character_position`, `copy.errors.limit`
- Epoch-ns fields: `session.start` (both login_history and query_history — standardised
  query_history from ISO-8601 to epoch-ns), all epoch-ns event_timestamps in `users.config`,
  `user.expires_at`, `user.locked_until_time`

---

### C — `__semdict: new` + `__semdict_note` on generic-named fields

**Problem:** Fields `error.code`, `status.code`, `status.message` in `login_history` and
`trust_center` had no `__semdict` annotation (defaulted to `new` implicitly), and no
`__semdict_note` explaining their DSOA-specific semantics or divergence from OTel/SD.

**Key facts:**

- `error.code` — NOT in OTel semconv. The SD has its own `error.code` as `type: long` for
  iOS/mobile numeric codes. DSOA's `error.code` is a string Snowflake error code — incompatible
  semantics. Must NOT use `__semdict: ref`.
- `status.code` / `status.message` — NOT in OTel or SD as global fields. DSOA-owned.

**Fix:** Added explicit `__semdict: new` + `__semdict_note` to all five occurrences (two in
login_history, two in trust_center). Notes document the divergence from SD and pending rename.

---

## Files Changed

| File                                                               | Change                                                                                                                                |
|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `src/build/export_semantics.py`                                    | A1: `_RES_NS` IDs; A2: `_merge_field_entries()`; A3: `dim_plugins` tracking; A4: ref exclusion; B-bool: `_coerce_attribute_example()` |
| `test/core/test_export_semantics.py`                               | New tests for A1–A4, B-bool, A2 merge, A3 ownership                                                                                   |
| `src/dtagent/plugins/resource_monitors.config/instruments-def.yml` | B-bool: 7 fields                                                                                                                      |
| `src/dtagent/plugins/users.config/instruments-def.yml`             | B-bool: 10 fields; B-long: 9 epoch-ns fields                                                                                          |
| `src/dtagent/plugins/query_history.config/instruments-def.yml`     | B-bool: 2 fields; B-long: 5 fields + session.start ISO→epoch                                                                          |
| `src/dtagent/plugins/login_history.config/instruments-def.yml`     | B-long: session.start; C: error.code, status.code, status.message                                                                     |
| `src/dtagent/plugins/tasks.config/instruments-def.yml`             | B-bool: allow_overlap                                                                                                                 |
| `src/dtagent/plugins/warehouse_usage.config/instruments-def.yml`   | B-long: clusters.count                                                                                                                |
| `src/dtagent/plugins/snowpipes.config/instruments-def.yml`         | B-long: 3 copy error fields                                                                                                           |
| `src/dtagent/plugins/trust_center.config/instruments-def.yml`      | C: error.code, status.message                                                                                                         |
| `src/dtagent/plugins/table_health.config/instruments-def.yml`      | Fix pre-existing trailing blank line (yamllint)                                                                                       |

## Test Results

- 95 tests pass (was 84 before; +11 new tests)
- pylint 10.00/10
- `./scripts/dev/build.sh` passes
- Dry-run deploy produces valid SQL with no errors

## Known Remaining Work (out of scope for this session)

- `snowflake.query.hash_version` / `parametrized_hash_version`: examples corrected from `v1`
  to integer `1`; Snowflake QUERY_HISTORY view confirms these are integer version numbers.
- B5 (systemic): many more fields across all plugins still lack `__type` annotations.
  This change covers only the confirmed boolean and integer fields. The remaining string fields
  that happen to be numeric in Snowflake should be a follow-up pass.
- Pending rename of `error.code` → `snowflake.login.error.code` and
  `snowflake.trust_center.error.code` to resolve the generic-name collision properly.

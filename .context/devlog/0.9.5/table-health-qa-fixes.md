# Table Health Bug Fixes — QA 0.9.5

## Summary

Two bugs discovered during the 0.9.5 QA release cycle on `dev-095` when executing
`table_health` contexts via the manual `DTAGENT()` call template.

---

## Bug 1: `P_COLLECT_CLUSTERING_INFO` — Insufficient Privileges

### Symptom

```
SQL access control error: Insufficient privileges to operate on procedure
'P_COLLECT_CLUSTERING_INFO'. in function DTAGENT with handler main
```

Reproduced by both:
- `call DTAGENT_095_DB.APP.DTAGENT(ARRAY_CONSTRUCT('table_health'))`
- `call DTAGENT_095_DB.APP.DTAGENT(ARRAY_CONSTRUCT('table_health:table_clustering'))`

### Root Cause

`APP.P_COLLECT_CLUSTERING_INFO` is defined with `execute as caller`. The DTAGENT UDF
runs as `DTAGENT_VIEWER`, which therefore needs `USAGE` privilege on the procedure to
call it via `session.call(...)`. This grant was missing from
`053_p_collect_clustering_info.sql`, despite the sibling procedure
`APP.P_SNAPSHOT_TABLE_HEALTH` (`056_p_snapshot_table_health.sql:96`) having it.

### Fix

Added to `src/dtagent/plugins/table_health.sql/053_p_collect_clustering_info.sql`:

```sql
grant usage on procedure DTAGENT_DB.APP.P_COLLECT_CLUSTERING_INFO() to role DTAGENT_VIEWER;
```

No upgrade script needed — this is a new grant, not a procedure signature change.

---

## Bug 2: `dsoa.run.plugin` Polluted by Context Suffix

### Symptom

```
call DTAGENT_095_DB.APP.DTAGENT(ARRAY_CONSTRUCT('table_health:table_health_derived'))
```

reported `dsoa.run.plugin == "table_health:table_health_derived"` instead of `"table_health"`.

### Root Cause

In `src/dtagent/agent.py`, all three `report_execution_status` calls in the `process()`
loop passed `task_name=source` (the raw input string, e.g. `"table_health:table_health_derived"`)
but omitted the `plugin_name` argument. Inside `__init__.py:167`, the context builder
uses `plugin_name or task_name` — so the full source string fell through as the value
for `dsoa.run.plugin`.

```python
# Before (all three call sites)
self.report_execution_status(status="STARTED", task_name=source, exec_id=run_id)

# After
self.report_execution_status(status="STARTED", task_name=source, exec_id=run_id, plugin_name=plugin_name)
```

Note: `dsoa.task.name` intentionally retains the full `source` string (including the
`:context` suffix) — this is correct and useful for tracing manual invocations.
Only `dsoa.run.plugin` was wrong.

### Affected call sites

- `agent.py:166` — `status="STARTED"`
- `agent.py:190` — `status="FINISHED"`
- `agent.py:198` — `status="FAILED"`

---

## Test Coverage

Added `test/core/test_agent_source_parsing.py` with three unit tests:

1. `test_plugin_name_not_polluted_by_context_suffix` — regression guard: asserts
   `report_execution_status` receives `plugin_name="table_health"` (not the full source
   string) when called with `"table_health:table_health_derived"`.
2. `test_contexts_forwarded_to_plugin` — asserts the parsed context list is forwarded
   correctly to the plugin's `process()` method.
3. `test_plain_source_still_works` — confirms the fix doesn't break plain (no-colon)
   source strings.

---

## Impact

- C2.9 and C2.10 QA checks (clustering context manual invocation) were blocked by Bug 1.
- `dsoa.run.plugin` DQL filters would silently miss data for any plugin called with
  context suffixes, including `table_health:table_clustering` and
  `table_health:table_health_derived`.

## Files Changed

| File | Change |
|------|--------|
| `src/dtagent/plugins/table_health.sql/053_p_collect_clustering_info.sql` | Added `GRANT USAGE ON PROCEDURE ... TO ROLE DTAGENT_VIEWER` |
| `src/dtagent/agent.py` | Added `plugin_name=plugin_name` to 3 `report_execution_status` calls |
| `test/core/test_agent_source_parsing.py` | New test file — 3 unit tests |

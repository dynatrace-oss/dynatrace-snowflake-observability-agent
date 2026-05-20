# Overload Protection — Context Fix and Semantic Correction

## Problem

On DEV-095, with `plugins.query_history.max_entries = 50` configured, running:

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "query_history"
| filter deployment.environment == "DEV-095"
| fields timestamp, content, deployment.environment, db.collection.name, snowflake.table.full_name
```

returned **only** "Signal overload protection active" lines — no normal query telemetry visible.

## Root Causes

### 1. `max_entries_applied` flag always True when max_entries configured

In `061_p_refresh_recent_queries.sql`, the return object contained:

```sql
'max_entries_applied', v_max_entries > 0,
```

This returned `True` whenever `max_entries` was set to any non-zero value — even when the
query volume was below the threshold and no rows were dropped. While the Python guard
(`total_available > total_processed`) correctly prevented false-positive events, the semantics
of the flag were misleading.

### 2. Overload events emitted under `query_history` context

The overload protection log and bizevent used `dsoa.run.context == "query_history"` — the same
context as normal query history telemetry. This made it impossible to filter overload signals
out of query log queries without losing normal data, or to filter only normal data without
accidentally including overload noise.

On a busy account with `max_entries = 50`, every run triggered the overload event, dominating
the `query_history` context logs.

## Fixes

### SQL — semantic correction (`061_p_refresh_recent_queries.sql`)

```sql
-- BEFORE (always True when max_entries is configured):
'max_entries_applied', v_max_entries > 0,

-- AFTER (True only when rows were actually dropped):
'max_entries_applied', (v_max_entries > 0 AND v_total_available > v_total_processed),
```

### Python — switch overload event context (`query_history.py`)

`_emit_overload_protection_event()` now builds a `self_monitoring` context using the run_id
extracted from the passed-in query_history context dict:

```python
run_id = context.get("dsoa.run.id", "")
sm_context = get_context_name_and_run_id(
    plugin_name=self._plugin_name, context_name="self_monitoring", run_id=run_id
)
```

Both `send_log()` and `send_events()` now use `sm_context`. This means:

- `dsoa.run.plugin == "query_history"` — still selects ALL telemetry from the plugin
- `dsoa.run.context == "query_history"` — selects only normal query logs/spans
- `dsoa.run.context == "self_monitoring"` — selects only overload protection signals

This is consistent with how `DynatraceSnowAgent._emit_ingest_warnings()` and
`._emit_acquisition_problems()` use `self_monitoring` context for operational signals.

## DQL Queries Post-Fix

Normal query logs only:

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "query_history"
| filter dsoa.run.context != "self_monitoring"
```

Overload protection signals only:

```dql
fetch logs
| filter db.system == "snowflake"
| filter dsoa.run.plugin == "query_history"
| filter dsoa.run.context == "self_monitoring"
| filter loglevel == "WARN"
```

## Tests Added

`TestEmitOverloadProtectionEvent` class extended with:

| Test | Scenario |
|------|----------|
| `test_context_is_self_monitoring_not_query_history` | Verifies both log and bizevent use `self_monitoring` context with `query_history` plugin |
| `test_no_event_when_max_entries_set_but_cap_not_hit` | `max_entries=10000`, `total_processed==total_available` → no event (SQL fix scenario) |
| `test_event_when_total_processed_is_zero` | `max_entries=1`, `total_processed=0`, `total_available=5000` → event fires, `dropped_count=5000` |

Also added `_plugin_name = "query_history"` to `_make_plugin()` helper (was missing, would have
caused `AttributeError` in the new context-building path).

## QA Runner Skill Updates

- `AE-C11.1` and `AE-C11.2` DQL queries updated to add `dsoa.run.context == "self_monitoring"` filter
- New `AE-C11.3` test: verifies normal query logs are present when overload protection is active
  (detects the "data not flowing" scenario where `max_entries` is too low for the query volume)
- Total auto-eval count updated: 57 → 58 (Batch 4: 11 → 12)
- `dsoa.run.plugin` vs `dsoa.run.context` semantics section updated with `query_history` special case

## Deployment

Scope: `plugins,config` — procedure body change only, no schema or signature change.
No upgrade script needed.

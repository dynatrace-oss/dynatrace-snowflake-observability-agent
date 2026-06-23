# Fix: Metric Fields Emitting String Values in Grail Logs

**Date:** 2026-06-23
**Branch:** `feat/1.0.0/bizobs-151-semantic-export`
**Ticket:** BIZOBS-151 (field type audit)

## Problem

During a Grail field-type audit (querying `fetch logs | filter isNotNull(<field>) | type(<field>)`),
six metric-kind fields were found to return `string` type from log records:

- `process.cpu.utilization`
- `process.memory.usage`
- `snowflake.compute.available`
- `snowflake.compute.other`
- `snowflake.compute.provisioning`
- `snowflake.compute.quiescing`

When queried via `timeseries`, all six correctly return `double` — confirming the metrics store
is correct. The issue is that these values also appear as string-typed attributes on log records.

## Root Cause Analysis

### Group 1: `process.cpu.utilization` / `process.memory.usage` — `event_log` plugin

**File:** `src/dtagent/plugins/event_log.py:_process_metric_entries`

The `_process_metric_entries` context calls `_log_entries` without `report_logs=False`.
The SQL view `051_v_event_log_metrics_instrumented.sql` wraps metric values in a
type-keyed dict via `OBJECT_CONSTRUCT(metric_type, VALUE)` (e.g. `{"gauge": 0}`).
This dict flows through `_unpack_json_dict` → `Logger.emit` → OTLP `kvlist_value`
AnyValue → Grail types as `string`.

The metrics path correctly strips the wrapper (`__payload_lines` unwraps single-key
dicts), but the log path does not.

### Group 2: `snowflake.compute.*` — `resource_monitors` plugin

**File:** `src/dtagent/plugins/resource_monitors.sql/061_v_warehouses.sql`
**File:** `src/dtagent/plugins/resource_monitors.sql/060_p_refresh_resource_monitors.sql`

Snowflake `SHOW WAREHOUSES` returns compute percentage columns (`available`,
`provisioning`, `quiescing`, `other`) as `TEXT` (e.g. `"75"` for active, `""` for
suspended). The temp table `TMP_WAREHOUSES` declares these columns as `text`.
The values flow into `METRICS` `OBJECT_CONSTRUCT` as strings and reach log attributes
via `_process_log_wh` for unmonitored warehouses.

The metrics path works because `_is_not_blank("75") = True` → sends `"75"` as a string
token to the Dynatrace Metrics API which parses it as a double. For suspended warehouses
(`""`), `_is_not_blank("") = False` → metric skipped.

## Fix

### Fix 1 — `event_log.py`

Added `report_logs=False` to the `_log_entries` call in `_process_metric_entries`.
Metric-only rows carry no user-visible log content; suppressing log emission removes
the spurious string attributes from Grail entirely.

```python
# Before
metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt = self._log_entries(
    lambda: self._get_table_rows(t_event_log_metrics_instrumented),
    context_name="event_log_metrics",
    run_uuid=run_id,
    start_time="TIMESTAMP",
    log_completion=run_proc,
)

# After
metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt = self._log_entries(
    lambda: self._get_table_rows(t_event_log_metrics_instrumented),
    context_name="event_log_metrics",
    run_uuid=run_id,
    report_logs=False,
    start_time="TIMESTAMP",
    log_completion=run_proc,
)
```

### Fix 2 — `061_v_warehouses.sql`

Wrapped `available`, `provisioning`, `quiescing`, `other` columns with `TRY_TO_DOUBLE()`
in the METRICS `OBJECT_CONSTRUCT`. `OBJECT_CONSTRUCT` silently drops NULL keys, so:
- Suspended warehouses (`""` → `NULL`) → no metric attribute emitted in logs
- Active warehouses (`"75"` → `75.0`) → true `double` emitted in both logs and metrics

```sql
-- Before
'snowflake.compute.available',   wh.available,
'snowflake.compute.provisioning', wh.provisioning,
'snowflake.compute.quiescing',    wh.quiescing,
'snowflake.compute.other',        wh.other,

-- After
'snowflake.compute.available',   TRY_TO_DOUBLE(wh.available),
'snowflake.compute.provisioning', TRY_TO_DOUBLE(wh.provisioning),
'snowflake.compute.quiescing',    TRY_TO_DOUBLE(wh.quiescing),
'snowflake.compute.other',        TRY_TO_DOUBLE(wh.other),
```

## Test Changes

Updated `test/plugins/test_event_log.py`:
- `event_log_metrics` context `log_lines` count: `2` → `0` (logs suppressed)
- Deleted and regenerated `test/test_results/test_event_log/logs.json` and
  `test/test_results/test_event_log_multi_source/logs.json` — metric log entries removed

## Verification

- `make lint`: pylint 10.00/10, flake8 clean, black clean
- `./scripts/dev/build.sh`: passed
- `./scripts/deploy/deploy.sh test-qa --scope=plugins,agents,config --options=skip_confirm,dry_run`: no errors
- `timeseries m=max(snowflake.compute.available), from:-30d | fields m[0], type=type(m[0])`: returns `double`

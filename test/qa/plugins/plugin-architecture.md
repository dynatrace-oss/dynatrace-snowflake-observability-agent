# Plugin Architecture & Implementation Details

## Overview

The DSOA agent uses a plugin-based architecture where each plugin:

1. Queries Snowflake views/tables
1. Transforms the data
1. Emits telemetry (logs, metrics, events, spans) to Dynatrace

Both `org_costs` and `query_history` plugins follow this pattern.

---

## Plugin Invocation Flow

```text
Snowflake Task Scheduler
    ↓
DTAGENT_DB.APP.DTAGENT() stored procedure
    ↓
Parses plugin name from ARRAY argument
    ↓
Loads OrgCostsPlugin or QueryHistoryPlugin class
    ↓
Calls plugin.process() method
    ↓
Plugin queries Snowflake views
    ↓
Plugin transforms rows to telemetry
    ↓
OtelManager sends to Dynatrace (OTLP, Metrics API, Events API)
    ↓
Results logged to DTAGENT_DB.LOG.RUN_LOG
    ↓
Telemetry counts stored in DTAGENT_DB.APP.RUN_RESULTS
```

---

## org_costs Plugin Details

### Python Implementation

**File:** `src/dtagent/plugins/org_costs.py`

**Class:** `OrgCostsPlugin(Plugin)`

**Key Method:** `process(run_id, run_proc=True, contexts=None)`

```python
def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None):
    """
    Processes org costs data.

    Args:
        run_id: Unique execution identifier
        run_proc: Whether to log completion
        contexts: Specific contexts to process (all if None)

    Returns:
        Dict with telemetry counts and run_id
    """
    results = {}

    # 5 contexts, each queries a different view
    if not contexts or "org_costs_metering" in contexts:
        rows = self._get_table_rows("APP.V_ORG_METERING_DAILY")
        entries, logs, metrics, events = self._log_entries(
            lambda: rows,
            "org_costs_metering",
            run_uuid=run_id,
            log_completion=run_proc
        )
        results["org_costs_metering"] = {
            "entries": entries,
            "log_lines": logs,
            "metrics": metrics,
            "events": events
        }

    # ... similar for storage, data_transfer, billing_usage, billing_balance

    return self._report_results(results, run_id)
```

### Data Sources

| Context                        | View                                  | Query Logic                                                       |
|--------------------------------|---------------------------------------|-------------------------------------------------------------------|
| org_costs_metering             | APP.V_ORG_METERING_DAILY              | Reads ACCOUNT_USAGE.METERING_HISTORY, groups by day               |
| org_costs_storage              | APP.V_ORG_STORAGE_DAILY               | Reads ACCOUNT_USAGE.STORAGE_USAGE, groups by day                  |
| org_costs_data_transfer        | APP.V_ORG_DATA_TRANSFER_DAILY         | Reads ACCOUNT_USAGE.DATA_TRANSFER_HISTORY, groups by day          |
| org_billing_usage_in_currency  | APP.V_ORG_BILLING_USAGE_IN_CURRENCY   | Reads ORGANIZATION_USAGE.CURRENCY_USAGE                           |
| org_billing_remaining_balance  | APP.V_ORG_BILLING_REMAINING_BALANCE   | Reads ORGANIZATION_USAGE.REMAINING_BALANCE                        |

### SQL Views

**Directory:** `src/dtagent/plugins/org_costs.sql/`

Files (3-digit prefix for ordering):

- `001_v_org_metering_daily.sql` - CREATE OR REPLACE VIEW V_ORG_METERING_DAILY
- `002_v_org_storage_daily.sql` - CREATE OR REPLACE VIEW V_ORG_STORAGE_DAILY
- `003_v_org_data_transfer_daily.sql` - CREATE OR REPLACE VIEW V_ORG_DATA_TRANSFER_DAILY
- `004_v_org_billing_usage_in_currency.sql` - CREATE OR REPLACE VIEW V_ORG_BILLING_USAGE_IN_CURRENCY
- `005_v_org_billing_remaining_balance.sql` - CREATE OR REPLACE VIEW V_ORG_BILLING_REMAINING_BALANCE
- `801_org_costs_task.sql` - CREATE OR REPLACE TASK to invoke the plugin

### Telemetry Generation

**Log Entry Example:**

```text
Level: INFO
Message: "Processed org_costs_metering: 45 entries"
Context: org_costs_metering
Attributes:
  - dsoa.run.id: <run_uuid>
  - dsoa.plugin.name: org_costs
  - snowflake.organization_name: <org>
```

**Metrics Generated per Row:**

```text
For each metering record:
  - dsoa.org_costs.metering.amount (gauge, in credits)
  - dsoa.org_costs.metering.by_service (with service tag)
  - dsoa.org_costs.metering.by_region (with region tag)

Similar breakdown for storage, data_transfer, billing_usage, etc.
```

**Events Generated per Row:**

```text
BizEvent per row with:
  - context: "org_costs_metering" (or respective context)
  - cost_amount: <value>
  - cost_currency: "USD" (or account currency)
  - service_type: <service_name>
  - account_name: <account>
  - timestamp: <billing_date>
```

---

## query_history Plugin Details

### Python Implementation

**File:** `src/dtagent/plugins/query_history.py`

**Class:** `QueryHistoryPlugin(Plugin)`

**Key Method:** `process(run_id, run_proc=True, contexts=None)`

```python
def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None):
    """
    Processes query history data with DDL change detection.

    Args:
        run_id: Unique execution identifier
        run_proc: Whether to log completion
        contexts: Specific contexts to process (all if None)

    Returns:
        Dict with telemetry counts including spans and DDL events
    """
    # Query ACCOUNT_USAGE.QUERY_HISTORY (typically last 10 minutes)
    rows = self._get_table_rows("ACCOUNT_USAGE.QUERY_HISTORY")

    entries, logs, metrics, spans, span_events, errors = self._log_entries(
        lambda: rows,
        "query_history",
        run_uuid=run_id,
        log_completion=run_proc
    )

    results["query_history"] = {
        "entries": entries,
        "log_lines": logs,
        "metrics": metrics,
        "spans": spans,
        "span_events": span_events,
        "errors": errors
    }

    # ... process query_cost_attribution if enabled

    return self._report_results(results, run_id)
```

### Data Sources

| Context                  | Source                        | Timeframe                       |
|--------------------------|-------------------------------|---------------------------------|
| query_history            | ACCOUNT_USAGE.QUERY_HISTORY   | Last 10 minutes (configurable)  |
| query_cost_attribution   | ACCOUNT_USAGE.QUERY_HISTORY   | Last 10 minutes (configurable)  |

**Key Fields Extracted:**

- Query ID, status, type (SELECT, INSERT, CREATE, etc.)
- Execution timestamps and duration
- Rows produced, rows scanned, bytes scanned
- Warehouse, database, schema, user, role
- Query text (for DDL detection)
- QUERY_OPERATOR_STATS (JSON) for operator breakdown

### SQL Views

**Directory:** `src/dtagent/plugins/query_history.sql/`

Files (3-digit prefix for ordering):

- `001_v_query_history.sql` - Base view with filtering and transformations
- `002_v_query_operators.sql` - Extracts QUERY_OPERATOR_STATS JSON
- `801_query_history_task.sql` - CREATE OR REPLACE TASK to invoke the plugin

### Telemetry Generation

**Log Entry Example (per query):**

```text
Level: INFO
Message: "Query 01b4f12a-... executed in 5123ms"
Context: query_history
Attributes:
  - dsoa.run.id: <run_uuid>
  - dsoa.plugin.name: query_history
  - snowflake.query.id: 01b4f12a-0000-0000-0000-...
  - snowflake.query.type: SELECT
  - snowflake.query.status: SUCCESS
  - snowflake.query.duration_ms: 5123
  - snowflake.warehouse: COMPUTE_WH
  - snowflake.user: SERVICE_ACCOUNT
```

**Metrics Generated per Query:**

```text
- dsoa.query_history.execution_count (counter, +1 per query)
- dsoa.query_history.duration_ms (histogram, query execution time)
- dsoa.query_history.rows_produced (gauge, output rows)
- dsoa.query_history.rows_scanned (gauge, input rows)
- dsoa.query_history.bytes_scanned (gauge, data read from storage)
- dsoa.query_history.cost_credits (gauge, credit cost)
- dsoa.query_history.compilation_time_ms (gauge, plan time)
- dsoa.query_history.execution_time_ms (gauge, runtime)

All metrics have tags:
  - snowflake.query.type (SELECT, INSERT, CREATE, etc.)
  - snowflake.warehouse
  - snowflake.database
  - snowflake.user
  - status (SUCCESS, TIMEOUT, ERROR)
```

**Spans Generated per Query:**

```text
OpenTelemetry Span:
- name: "snowflake.query"
- startTime: Query start timestamp
- endTime: Query end timestamp (or current if still running)
- spanId: Derived from query ID
- traceId: Derived from run ID

Attributes:
  - dsoa.run.id: <run_uuid>
  - dsoa.plugin.name: query_history
  - snowflake.query.id: <query_id>
  - snowflake.query.type: <type>
  - snowflake.query.status: <status>
  - snowflake.query.duration_ms: <duration>
  - snowflake.warehouse: <warehouse>
  - snowflake.database: <database>
  - snowflake.schema: <schema>
  - snowflake.user: <user>
  - snowflake.role: <role>
  - [All query metrics as attributes]
```

**Span Events Generated per Operator (with DDL tracking):**

```text
Per operator in QUERY_OPERATOR_STATS JSON:

Example for TableScan:
{
  "name": "TableScan 01b4f12a:0",
  "timestamp": <operator_start_time>,
  "attributes": {
    "snowflake.query.operator.type": "TableScan",
    "snowflake.query.operator.id": 0,
    "snowflake.query.operator.rows": 50000,
    "snowflake.query.operator.duration_ms": 1000
  }
}

DDL Change Event (if query is CREATE/ALTER/DROP):
{
  "name": "DDL_CHANGE 01b4f12a:99",
  "timestamp": <query_completion_time>,
  "attributes": {
    "snowflake.query.operator.type": "CREATE TABLE",
    "snowflake.query.operator.id": 99,
    "ddl_type": "CREATE",
    "ddl_target": "MY_DB.PUBLIC.NEW_TABLE",
    "ddl_statement": "<full DDL text>"
  }
}
```

**Events Generated (BizEvents):**

```text
Per query (if query_cost_attribution enabled):

{
  "context": "query_cost_attribution",
  "timestamp": <query_end_time>,
  "properties": {
    "dsoa.run.id": <run_uuid>,
    "dsoa.plugin.name": "query_history",
    "snowflake.query.id": <query_id>,
    "snowflake.query.type": "SELECT",
    "execution_status": "SUCCESS",
    "cost_credits": 0.25,
    "cost_currency": "USD",
    "warehouse": "COMPUTE_WH",
    "warehouse_size": "XSMALL",
    "database": "MY_DB",
    "schema": "PUBLIC",
    "user": "SERVICE_ACCOUNT",
    "role": "TRANSFORMER",
    "duration_ms": 5123,
    "rows_produced": 1000,
    "rows_scanned": 50000,
    "bytes_scanned": 104857600
  }
}
```

---

## Plugin Base Class (Parent Class)

**File:** `src/dtagent/plugins/__init__.py`

**Class:** `Plugin(ABC)`

### Key Methods

#### `_get_table_rows(table_name: str) -> Iterator[Dict]`

- Queries specified table/view in Snowflake
- Returns rows as dictionaries
- Mock mode: loads from NDJSON fixture files
- Live mode: executes SELECT \* query

#### `_log_entries(get_rows_fn, context, run_uuid, log_completion=True)`

- Main telemetry generation method
- Iterates over rows from get_rows_fn
- Transforms each row to logs, metrics, events, spans
- Sends via OtelManager
- Returns counts: (entries, logs, metrics, events)
- For query_history: (entries, logs, metrics, spans, span_events, errors)

#### `_report_results(results: Dict, run_id: str)`

- Formats final result as JSON
- Includes run_id UUID
- Returns to caller (Snowflake procedure)

---

## Telemetry Transmission

### Transport Layers

#### 1. Logs & Spans (OpenTelemetry OTLP)

```text
HTTP POST to: https://{dynatrace_tenant}/api/v2/otlp/v1/traces
Header: Authorization: Api-Token {token}
Body: OTLP/Protobuf format
```

#### 2. Metrics (Dynatrace Metrics API)

```text
HTTP POST to: https://{dynatrace_tenant}/api/v2/metrics/ingest
Header: Authorization: Api-Token {token}
Body: Line protocol format (Prometheus compatible)
```

#### 3. Events (Dynatrace Events API)

```text
HTTP POST to: https://{dynatrace_tenant}/api/v1/events
Header: Authorization: Api-Token {token}
Body: JSON event payload
```

### Configuration for Transmission

**File:** `src/dtagent/otel/__init__.py`

**Manager Class:** `OtelManager`

- Aggregates logs, metrics, events, spans
- Batches telemetry for efficiency
- Handles retries and failures
- Logs transmission status to RUN_LOG

---

## Configuration Files

### org_costs Configuration

**File:** `src/dtagent/plugins/org_costs.config/org_costs-config.yml`

```yaml
enabled: true
schedule_interval_minutes: 360  # 6 hours
contexts:
  - org_costs_metering
  - org_costs_storage
  - org_costs_data_transfer
  - org_billing_usage_in_currency
  - org_billing_remaining_balance
disabled_telemetry: []  # Send all types by default
```

### query_history Configuration

**File:** `src/dtagent/plugins/query_history.config/query_history-config.yml`

```yaml
enabled: true
schedule_interval_minutes: 30  # 30 minutes
contexts:
  - query_history
  - query_cost_attribution
query_timeframe_minutes: 10  # Look back 10 minutes
track_ddl_changes: true  # Enable DDL tracking
disabled_telemetry: []  # Send all types by default
```

---

## Execution Flow Diagram

```text
START: Plugin Invocation
    ↓
[1] Plugin.process() called with run_id
    ↓
[2] For each context to process:
    ├─→ Call _get_table_rows(table_name)
    │   ├─→ [Mock mode] Load from test/test_data/*.ndjson
    │   └─→ [Live mode] Execute SELECT * from table
    │
    ├─→ Call _log_entries(rows_iterator, context_name, run_id)
    │   └─→ For each row:
    │       ├─→ Create log record
    │       ├─→ Create metrics (multiple per row)
    │       ├─→ Create events (per row)
    │       ├─→ For query_history: Create span + span events
    │       └─→ Send via OtelManager
    │
    └─→ Accumulate counts: entries, logs, metrics, events, [spans]
    ↓
[3] Compile results dictionary with all counts
    ↓
[4] Call _report_results(results, run_id)
    ├─→ Format as JSON
    ├─→ Log to DTAGENT_DB.LOG.RUN_LOG
    ├─→ Store counts in DTAGENT_DB.APP.RUN_RESULTS
    └─→ Return to Snowflake procedure
    ↓
[5] DTAGENT procedure returns result to caller
    ↓
[6] Telemetry transmitted to Dynatrace (async)
    └─→ Appears in Dynatrace UI within 1-2 minutes
    ↓
END
```

---

## Testing & Verification

### Snowflake-side Verification

```sql
-- Check execution status
SELECT * FROM DTAGENT_DB.LOG.RUN_LOG
WHERE plugin_name IN ('org_costs', 'query_history')
AND execution_end_time >= CURRENT_TIMESTAMP() - INTERVAL '1 hour'
ORDER BY execution_end_time DESC;

-- Check telemetry counts
SELECT * FROM DTAGENT_DB.APP.RUN_RESULTS
WHERE plugin_name IN ('org_costs', 'query_history')
AND updated_at >= CURRENT_TIMESTAMP() - INTERVAL '1 hour'
ORDER BY updated_at DESC;
```

### Dynatrace-side Verification

```dql
-- Check BizEvents
fetch bizevents
| filter context LIKE "org_costs_*" OR context == "query_history"
| filter timestamp >= now()-1h
| summarize event_count = count(), by: {context}

-- Check Spans
fetch spans
| filter span.origin == "DSOA"
| filter timestamp >= now()-1h
| summarize span_count = count(), by: {span.db.operation}

-- Check Metrics
fetch metrics
| filter metric.name LIKE "dsoa.*"
| filter timestamp >= now()-1h
| summarize point_count = count()
```

---

## Key Implementation Files

### Core Files

- `src/dtagent/plugins/__init__.py` - Plugin base class
- `src/dtagent/agent.py` - Entry point
- `src/dtagent/otel/__init__.py` - Telemetry manager

### Plugin Files

- `src/dtagent/plugins/org_costs.py`
- `src/dtagent/plugins/query_history.py`

### SQL Files

- `src/dtagent/plugins/org_costs.sql/`
- `src/dtagent/plugins/query_history.sql/`

### Configuration Files

- `src/dtagent/plugins/org_costs.config/`
- `src/dtagent/plugins/query_history.config/`

### Test Files

- `test/plugins/test_org_costs.py`
- `test/plugins/test_query_history.py`

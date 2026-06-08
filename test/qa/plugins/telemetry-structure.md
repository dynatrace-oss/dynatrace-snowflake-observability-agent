# Plugin Telemetry Structure & Expected Results

## Procedure Invocation

Both plugins are invoked through a single entry point: `DTAGENT_DB.APP.DTAGENT()`

### org_costs Plugin Invocation

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('org_costs'));
```

This internally calls `OrgCostsPlugin.process()` which processes these contexts:

| Context                         | Source Table                          | Purpose                                      |
|---------------------------------|---------------------------------------|----------------------------------------------|
| `org_costs_metering`            | `APP.V_ORG_METERING_DAILY`            | Metering costs (compute, storage by product) |
| `org_costs_storage`             | `APP.V_ORG_STORAGE_DAILY`             | Storage costs breakdown                      |
| `org_costs_data_transfer`       | `APP.V_ORG_DATA_TRANSFER_DAILY`       | Data transfer costs                          |
| `org_billing_usage_in_currency` | `APP.V_ORG_BILLING_USAGE_IN_CURRENCY` | Billing amounts in account currency          |
| `org_billing_remaining_balance` | `APP.V_ORG_BILLING_REMAINING_BALANCE` | Account credit balance                       |

### query_history Plugin Invocation

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));
```

This internally calls `QueryHistoryPlugin.process()` which processes these contexts:

| Context                  | Source Table                  | Purpose                                 |
|--------------------------|-------------------------------|-----------------------------------------|
| `query_history`          | `ACCOUNT_USAGE.QUERY_HISTORY` | Query execution data + DDL tracking     |
| `query_cost_attribution` | `ACCOUNT_USAGE.QUERY_HISTORY` | Cost attribution per query (if enabled) |

---

## Expected Return Structures

### org_costs Return Structure

```json
{
  "dsoa.run.results": {
    "org_costs_metering": {
      "entries": 45,
      "log_lines": 45,
      "metrics": 180,
      "events": 45
    },
    "org_costs_storage": {
      "entries": 30,
      "log_lines": 30,
      "metrics": 120,
      "events": 30
    },
    "org_costs_data_transfer": {
      "entries": 15,
      "log_lines": 15,
      "metrics": 60,
      "events": 15
    },
    "org_billing_usage_in_currency": {
      "entries": 5,
      "log_lines": 5,
      "metrics": 20,
      "events": 5
    },
    "org_billing_remaining_balance": {
      "entries": 1,
      "log_lines": 1,
      "metrics": 4,
      "events": 1
    }
  },
  "dsoa.run.id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Interpretation:**

- **entries**: Row count from source table
- **log_lines**: Number of log messages sent to Dynatrace (one per entry typically)
- **metrics**: Number of individual metric data points sent
- **events**: Number of business events sent
- Each context generates multiple metrics (breakdown by cost type, service, region, etc.)

### query_history Return Structure

```json
{
  "dsoa.run.results": {
    "query_history": {
      "entries": 1250,
      "log_lines": 1250,
      "metrics": 3750,
      "spans": 1250,
      "span_events": 5000,
      "errors": 0
    },
    "query_cost_attribution": {
      "entries": 1250,
      "log_lines": 1250,
      "metrics": 3750,
      "events": 1250,
      "errors": 0
    }
  },
  "dsoa.run.id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Interpretation:**

- **entries**: Number of queries processed
- **log_lines**: Number of log messages (typically one per query)
- **metrics**: Query metrics (duration, rows, cost, etc.) - multiple per query
- **spans**: Distributed trace spans - one per query
- **span_events**: Operator events within spans - multiple per query if complex
- **events**: Business events for cost attribution
- **errors**: Count of processing failures (should be 0)

---

## Telemetry Content Details

### org_costs Telemetry Components

#### Logs (OpenTelemetry)

```text
Example log record:
{
  "severity": "INFO",
  "timestamp": "<iso8601>",
  "context": "org_costs_metering",
  "message": "Processed metering costs for 45 daily records",
  "attributes": {
    "dsoa.run.id": "550e8400-...",
    "dsoa.plugin.name": "org_costs",
    "snowflake.organization_name": "myorg"
  }
}
```

#### Metrics (OpenTelemetry)

```text
Example metrics:
- dsoa.org_costs.metering.total (counter, cumulative_dollars)
- dsoa.org_costs.metering.by_service (histogram, cost breakdown by service)
- dsoa.org_costs.storage.total (counter, cumulative_dollars)
- dsoa.org_costs.storage.database (histogram, cost per database)
- dsoa.org_costs.data_transfer.total (counter, cumulative_dollars)
- dsoa.org_billing.usage_in_currency (gauge, current balance in account currency)
- dsoa.org_billing.remaining_balance (gauge, available credits/funds)
```

#### Events (BizEvents)

```text
Example BizEvent:
{
  "context": "org_costs_metering",
  "timestamp": "<iso8601>",
  "properties": {
    "dsoa.run.id": "550e8400-...",
    "dsoa.plugin.name": "org_costs",
    "cost_currency": "USD",
    "total_cost": 1234.56,
    "service_type": "COMPUTE"
  },
  "deployment": {
    "environment": "<your-environment>"
  }
}
```

### query_history Telemetry Components

#### Logs (OpenTelemetry)

```text
Example log record per query:
{
  "severity": "INFO",
  "timestamp": "<iso8601>",
  "context": "query_history",
  "message": "Query executed",
  "attributes": {
    "dsoa.run.id": "660e8400-...",
    "dsoa.plugin.name": "query_history",
    "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
    "snowflake.query.status": "SUCCESS",
    "snowflake.query.duration_ms": 5000,
    "snowflake.query.rows_produced": 1000
  }
}
```

#### Metrics (OpenTelemetry)

```text
Example metrics per query:
- dsoa.query_history.execution_count (counter)
- dsoa.query_history.duration_ms (histogram, distribution of query durations)
- dsoa.query_history.rows_produced (histogram, row output distribution)
- dsoa.query_history.rows_scanned (histogram, data scanned)
- dsoa.query_history.bytes_scanned (histogram, bytes read from storage)
- dsoa.query_history.compilation_time_ms (histogram)
- dsoa.query_history.execution_time_ms (histogram)
- dsoa.query_history.cost_credits (histogram, cost breakdown)
```

#### Spans (Distributed Traces)

```text
Example span per query:
{
  "traceId": "550e8400e29b41d4a716446655440000",
  "spanId": "660e8400e29b41d4",
  "name": "snowflake.query",
  "startTime": "<iso8601>",
  "endTime": "<iso8601>",
  "attributes": {
    "dsoa.run.id": "660e8400-...",
    "dsoa.plugin.name": "query_history",
    "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
    "snowflake.query.status": "SUCCESS",
    "snowflake.query.duration_ms": 5123,
    "snowflake.warehouse": "COMPUTE_WH",
    "snowflake.database": "MY_DB",
    "snowflake.schema": "PUBLIC",
    "snowflake.user": "SERVICE_ACCOUNT"
  }
}
```

#### Span Events (Operator-level Details)

```text
Example span events (attached to span above):
[
  {
    "name": "TableScan 01b4f12a:0",
    "timestamp": "<iso8601>",
    "attributes": {
      "snowflake.query.operator.type": "TableScan",
      "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
      "snowflake.query.operator.id": 0,
      "snowflake.query.operator.rows": 50000,
      "snowflake.query.operator.duration_ms": 1000
    }
  },
  {
    "name": "Filter 01b4f12a:1",
    "timestamp": "<iso8601>",
    "attributes": {
      "snowflake.query.operator.type": "Filter",
      "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
      "snowflake.query.operator.id": 1,
      "snowflake.query.operator.rows": 5000,
      "snowflake.query.operator.duration_ms": 200
    }
  },
  {
    "name": "DDL_CHANGE 01b4f12a:99",
    "timestamp": "<iso8601>",
    "attributes": {
      "snowflake.query.operator.type": "CREATE TABLE",
      "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
      "snowflake.query.operator.id": 99,
      "ddl_type": "CREATE",
      "ddl_target": "MY_DB.PUBLIC.NEW_TABLE"
    }
  }
]
```

#### Events (BizEvents)

```text
Example BizEvent for query_cost_attribution:
{
  "context": "query_cost_attribution",
  "timestamp": "<iso8601>",
  "properties": {
    "dsoa.run.id": "660e8400-...",
    "dsoa.plugin.name": "query_history",
    "snowflake.query.id": "01b4f12a-0000-0000-0000-...",
    "snowflake.query.type": "SELECT",
    "cost_credits": 0.25,
    "cost_currency": "USD",
    "warehouse_size": "XSMALL",
    "user": "SERVICE_ACCOUNT",
    "role": "TRANSFORMER",
    "database": "MY_DB",
    "execution_status": "SUCCESS"
  },
  "deployment": {
    "environment": "<your-environment>"
  }
}
```

---

## BizEvent Verification Queries

Replace `<your-environment>` with the value of `deployment.environment` configured in your DSOA deployment.

### Query 1: Count BizEvents per org_costs Context

```dql
fetch bizevents
| filter context in ["org_costs_metering", "org_costs_storage", "org_costs_data_transfer",
                      "org_billing_usage_in_currency", "org_billing_remaining_balance"]
| filter timestamp >= now()-1h
| summarize event_count = count(), latest_timestamp = max(timestamp), by: {context}
```

**Expected Result:**

```text
context                          | event_count | latest_timestamp
org_costs_metering               | 45          | <recent>
org_costs_storage                | 30          | <recent>
org_costs_data_transfer          | 15          | <recent>
org_billing_usage_in_currency    | 5           | <recent>
org_billing_remaining_balance    | 1           | <recent>
```

### Query 2: Count BizEvents for query_history

```dql
fetch bizevents
| filter context == "query_history"
| filter timestamp >= now()-1h
| summarize event_count = count(), latest_timestamp = max(timestamp)
```

### Query 3: Verify DDL Events Transmitted

```dql
fetch bizevents
| filter context == "query_history"
| filter timestamp >= now()-1h
| filter contains(properties["ddl_type"], ["CREATE", "ALTER", "DROP"])
| summarize ddl_count = count(), by: {properties["ddl_type"]}
```

### Query 4: Verify Span Transmission

```dql
fetch spans
| filter span.origin == "DSOA"
| filter span.db.system == "snowflake"
| filter timestamp >= now()-1h
| summarize span_count = count(), operator_count = sum(span_event_count), by: {span.db.operation}
```

### Query 5: Verify Metrics Transmitted

```dql
fetch metrics
| filter metric.name contains "dsoa.query_history" or metric.name contains "dsoa.org_costs"
| filter timestamp >= now()-1h
| summarize metric_count = count(), samples = sum(count), by: {metric.name}
```

---

## Validation Checklist

### Snowflake-side Verification

- [ ] RUN_LOG contains entries for both org_costs and query_history
- [ ] All contexts marked as COMPLETED
- [ ] No ERROR level logs
- [ ] RUN_RESULTS has telemetry counts for all contexts
- [ ] Timestamps are recent (within last 5 minutes)

### Dynatrace-side Verification

- [ ] BizEvents appear within 1-2 minutes of procedure execution
- [ ] All 5 org_costs contexts have events
- [ ] query_history context has events
- [ ] Event counts match Snowflake RUN_RESULTS
- [ ] DDL events present (if DDL tracking is enabled and DDL was executed)
- [ ] Spans visible in distributed trace view
- [ ] Metrics dashboard populated with new data

---

## Troubleshooting Reference

### No Telemetry Appearing in Dynatrace

**Check these in order:**

1. RUN_LOG for transmission errors: `log_level = 'ERROR'`
1. Network connectivity to Dynatrace (check firewall rules)
1. API token validity (check Dynatrace API token permissions)
1. Wait 1-2 minutes for async telemetry delivery

### Metrics Not Appearing

**Check:**

- Metric names in RUN_RESULTS match metric exporter configuration
- Check instrument definitions in `instruments-def.yml`
- Verify metric.name filter in DQL matches actual transmitted metrics

### Spans Not Visible

**Check:**

- query_history context must be processed (check RUN_RESULTS)
- Spans should appear in distributed traces view
- Filter by `span.origin == "DSOA"` or `span.db.system == "snowflake"`

### DDL Events Missing

**Check:**

- `track_ddl_changes` is enabled in query_history configuration
- DDL statements were actually executed in recent timeframe
- Filter for `properties["ddl_type"]` in BizEvents query

---

## Key Metrics to Monitor

### For org_costs Context

- Total cost per day (`dsoa.org_costs.*.total`)
- Cost breakdown by service type
- Cost per database/schema
- Cost trend over time

### For query_history Context

- Average query duration
- Query success/failure rates
- Cost attribution per user/warehouse/database
- Top queries by cost
- DDL change frequency
- Query operator performance breakdown

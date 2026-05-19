# Plugin Execution Guide

## Overview

This guide provides step-by-step instructions to execute the `org_costs` and `query_history`
plugins against a live Snowflake environment using the `snow_agent_test-qa` profile.

---

## Prerequisites

- Snowflake client (SnowSQL, DBeaver, or other SQL IDE)
- Connection configured with `snow_agent_test-qa` profile
- Access to DTAGENT_DB database
- Dynatrace environment access for telemetry verification

---

## Task 1: Trigger org_costs Procedure

### Execution Command

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('org_costs'));
```

### What This Does

- Invokes the main DTAGENT stored procedure with the `org_costs` plugin
- Processes 5 cost-related contexts:
  1. `org_costs_metering` - Metering costs
  1. `org_costs_storage` - Storage costs
  1. `org_costs_data_transfer` - Data transfer costs
  1. `org_billing_usage_in_currency` - Billing in currency
  1. `org_billing_remaining_balance` - Remaining balance

### Expected Output

The procedure returns a JSON result with telemetry counts per context:

```json
{
  "dsoa.run.results": {
    "org_costs_metering": {
      "entries": "<count>",
      "log_lines": "<count>",
      "metrics": "<count>",
      "events": "<count>"
    },
    "org_costs_storage": {},
    "org_costs_data_transfer": {},
    "org_billing_usage_in_currency": {},
    "org_billing_remaining_balance": {}
  },
  "dsoa.run.id": "<uuid>"
}
```

### Success Indicators

- Result contains all 5 contexts
- Each context shows non-zero entry counts (unless data is empty in source tables)
- No SQL errors in the result
- `dsoa.run.id` is populated with a valid UUID

### Troubleshooting

| Issue                          | Cause                          | Solution                                          |
|--------------------------------|--------------------------------|---------------------------------------------------|
| `PROCEDURE_NOT_FOUND`          | DTAGENT procedure not deployed | Deploy DTAGENT_DB and procedures first            |
| Zero entries for all contexts  | Source tables empty            | Check if cost data exists in Snowflake account    |
| Permission denied              | Role lacks access              | Verify DTAGENT_OWNER role permissions             |

---

## Task 2: Trigger query_history Procedure

### Execution Command

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));
```

### What This Does

- Invokes the main DTAGENT stored procedure with the `query_history` plugin
- Processes query history data from ACCOUNT_USAGE.QUERY_HISTORY
- Includes DDL change detection (if `track_ddl_changes` is enabled in config)
- Processes 2 contexts:
  1. `query_history` - Query execution data with DDL tracking
  1. `query_cost_attribution` - Cost attribution data (if enabled)

### Expected Output

The procedure returns a JSON result with telemetry counts:

```json
{
  "dsoa.run.results": {
    "query_history": {
      "entries": "<count>",
      "log_lines": "<count>",
      "metrics": "<count>",
      "spans": "<count>",
      "span_events": "<count>",
      "errors": "<count>"
    },
    "query_cost_attribution": {}
  },
  "dsoa.run.id": "<uuid>"
}
```

### Success Indicators

- Result contains `query_history` context
- Entry count > 0 (unless no queries executed in timeframe)
- Spans and span_events populated with operator statistics
- No SQL errors in the result
- DDL changes detected (if DDL queries were executed recently)

### DDL Change Detection

The plugin tracks DDL changes:

- `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE` statements
- `CREATE/DROP SCHEMA`, `CREATE/DROP DATABASE` statements
- Each DDL statement generates a separate span event

### Troubleshooting

| Issue                          | Cause                                       | Solution                                          |
|--------------------------------|---------------------------------------------|---------------------------------------------------|
| Zero query entries             | No queries in last 10 minutes               | Execute some queries before running plugin        |
| No span_events                 | QUERY_OPERATOR_STATS not populated          | Run complex queries with operators                |
| DDL changes not detected       | track_ddl_changes disabled                  | Enable in CONFIG.CONFIGURATIONS                   |

---

## Task 3: Verify Procedures Executed Successfully

### Step 3a: Check Agent Execution Logs (In Snowflake)

```sql
-- View recent plugin execution logs
select
    run_id,
    plugin_name,
    context_name,
    log_level,
    execution_status,
    execution_end_time,
    count(*) as log_entries
from DTAGENT_DB.LOG.RUN_LOG
where execution_end_time >= current_timestamp() - interval '1 hour'
  and plugin_name in ('org_costs', 'query_history')
group by run_id, plugin_name, context_name, log_level, execution_status, execution_end_time
order by execution_end_time desc;
```

**What to look for:**

- Rows with `plugin_name = 'org_costs'` and `'query_history'`
- `execution_status = 'COMPLETED'` for both plugins
- Multiple contexts per plugin (org_costs has 5, query_history has 2)
- No rows with `log_level = 'ERROR'` (unless expected)

### Step 3b: Check Run Results (In Snowflake)

```sql
-- View telemetry counts for both plugins
select
    run_id,
    plugin_name,
    context_name,
    entries,
    log_lines,
    metrics,
    events,
    spans
from DTAGENT_DB.APP.RUN_RESULTS
where updated_at >= current_timestamp() - interval '1 hour'
  and plugin_name in ('org_costs', 'query_history')
order by updated_at desc;
```

**What to look for:**

- All 5 contexts for org_costs
- 2 contexts for query_history (query_history, query_cost_attribution if enabled)
- Non-zero telemetry counts (log_lines, metrics, events, spans)
- Most recent `updated_at` timestamp should be within the last few minutes

### Step 3c: Verify BizEvents in Dynatrace

#### Query 3c-1: org_costs BizEvents

Open Dynatrace and execute this DQL query:

```dql
fetch bizevents
| filter context == "org_costs_metering"
    or context == "org_costs_storage"
    or context == "org_costs_data_transfer"
    or context == "org_billing_usage_in_currency"
    or context == "org_billing_remaining_balance"
| filter timestamp >= now()-1h
| summarize event_count = count(), by: {context}
```

**Expected result:**

- 5 rows (one per context)
- Non-zero event_count for each context

#### Query 3c-2: query_history BizEvents

```dql
fetch bizevents
| filter context == "query_history"
| filter timestamp >= now()-1h
| summarize event_count = count()
```

#### Query 3c-3: Verify DDL Events (if applicable)

```dql
fetch bizevents
| filter context == "query_history"
| filter timestamp >= now()-1h
| filter properties["ddl_type"] exists
| summarize ddl_count = count(), by: {properties["ddl_type"]}
```

---

## Execution Sequence

### Option A: Manual Execution (Recommended for Testing)

1. Connect to Snowflake using `snow_agent_test-qa` profile
1. Execute the org_costs procedure (Task 1)
1. Verify it completes successfully
1. Execute the query_history procedure (Task 2)
1. Verify it completes successfully
1. Query execution logs in Snowflake (Step 3a)
1. Query run results in Snowflake (Step 3b)
1. Query BizEvents in Dynatrace (Step 3c)

### Option B: Automated Execution

Use the prepared SQL file: `test/qa/plugins/plugin-execution.sql`

---

## Key Files

- **Procedure implementations:**
  - `src/dtagent/plugins/org_costs.py`
  - `src/dtagent/plugins/query_history.py`

- **Procedure SQL definitions:**
  - `src/dtagent/plugins/org_costs.sql/801_org_costs_task.sql`
  - `src/dtagent/plugins/query_history.sql/801_query_history_task.sql`

- **Execution script:**
  - `test/qa/plugins/plugin-execution.sql`

---

## Configuration

### org_costs Plugin Configuration

Location: `src/dtagent/plugins/org_costs.config/org_costs-config.yml`

Contexts processed:

- `org_costs_metering` - Metering costs
- `org_costs_storage` - Storage costs
- `org_costs_data_transfer` - Data transfer costs
- `org_billing_usage_in_currency` - Billing in currency
- `org_billing_remaining_balance` - Remaining balance

### query_history Plugin Configuration

Location: `src/dtagent/plugins/query_history.config/query_history-config.yml`

Key configuration option for this test:

- `track_ddl_changes: true` - Enables DDL change detection

Contexts processed:

- `query_history` - Query execution data
- `query_cost_attribution` - Cost attribution (if enabled)

---

## Success Criteria Checklist

### Task 1: org_costs

- [ ] Procedure executed without SQL errors
- [ ] Result contains all 5 contexts
- [ ] At least one context has entry_count > 0
- [ ] Run ID is populated
- [ ] No ERROR level logs in RUN_LOG

### Task 2: query_history

- [ ] Procedure executed without SQL errors
- [ ] Result contains query_history context
- [ ] entry_count > 0 (unless no queries recent)
- [ ] Spans are populated
- [ ] Run ID is populated
- [ ] No ERROR level logs in RUN_LOG

### Task 3: Verification

- [ ] org_costs BizEvents count > 0 in Dynatrace
- [ ] query_history BizEvents count > 0 in Dynatrace
- [ ] RUN_RESULTS table updated with latest run
- [ ] All telemetry types (logs, metrics, spans, events) sent
- [ ] DDL events present (if DDL changes were made)

---

## Expected Telemetry Breakdown

### org_costs Plugin

Per context (5 total):

- **Logs:** 1 per context (status/summary)
- **Metrics:** ~10-15 per context (cost breakdown by resource type)
- **Events:** ~10-15 per context (detailed events for billing/cost)
- **Spans:** 0 (org_costs doesn't generate spans)

### query_history Plugin

Per context (2 total):

- **Logs:** 5-10 per context (query execution details)
- **Metrics:** 20-30 per context (query duration, cost, data scanned)
- **Spans:** 100-500 per context (one span per query, with operator events)
- **Span Events:** 500-2000 per context (operator-level events)
- **Events:** 10-20 per context (summary events)

---

## Troubleshooting

### "PROCEDURE_NOT_FOUND" Error

```text
SQL Error: Code: 2003, Message: 002003 (42601): SQL compilation error:
  Object 'DTAGENT' of type 'PROCEDURE' does not exist or not authorized.
```

**Solution:**

- Verify the DTAGENT stored procedure was deployed
- Check if compiled file was uploaded to Snowflake
- Verify role has USAGE permission on DTAGENT_DB and APP schema

### "Table doesn't exist" Error

```text
SQL Error: Code: 2003, Message: Table 'V_ORG_METERING_DAILY' doesn't exist
```

**Solution:**

- Verify all prerequisite views were created
- Run the complete setup/deploy script
- Check if views have correct names and locations

### Zero Telemetry Entries

**Cause:** Source data is empty or doesn't exist in timeframe

**Solution:**

- For org_costs: Ensure account has billing/cost data
- For query_history: Execute some queries before running the plugin
- Check the query result window (default: last 10 minutes)

### BizEvents Not Appearing in Dynatrace

**Cause:** Telemetry not transmitted or authentication failed

**Solution:**

- Check network connectivity to Dynatrace
- Verify API token is valid and has correct permissions
- Check DTAGENT_DB.LOG.RUN_LOG for transmission errors

---

## Contact & Support

For issues or questions:

- Check `docs/CONTRIBUTING.md`
- Review plugin documentation in `docs/`
- Check agent logs in DTAGENT_DB.LOG tables

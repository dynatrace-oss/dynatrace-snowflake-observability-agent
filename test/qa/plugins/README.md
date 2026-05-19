# Plugin Execution Test Suite

This directory contains documentation and scripts to manually execute and verify
DSOA plugins against a live Snowflake environment.

## Files in This Directory

### Quick Start

- **`QUICKSTART.txt`** - 3-step execution guide with expected results

### Execution Scripts

- **`plugin-execution.sql`** - All-in-one SQL script for running plugins
- **`execution-commands.txt`** - Copy-paste ready commands with detailed output expectations

### Detailed Documentation

- **`execution-guide.md`** - Comprehensive step-by-step guide with troubleshooting
- **`telemetry-structure.md`** - Detailed telemetry structure and expected BizEvent payloads
- **`plugin-architecture.md`** - Technical deep-dive into plugin implementation and flow

## Quick Summary

### Execute org_costs Plugin

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('org_costs'));
```

Processes 5 cost-related contexts with billing, storage, and metering data.

### Execute query_history Plugin

```sql
call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));
```

Processes query execution data with operator breakdowns and DDL change detection.

### Verify in Dynatrace

Check BizEvents are transmitted with correct counts for all contexts:

```dql
fetch bizevents
| filter timestamp >= now()-1h
| summarize count(), by: {context}
```

## Expected Results

### org_costs Plugin

- 5 cost contexts with telemetry (metering, storage, data_transfer, billing_usage, remaining_balance)
- Generates: logs, metrics, events
- Does NOT generate spans

### query_history Plugin

- 2 contexts with query data (query_history, query_cost_attribution)
- Generates: logs, metrics, spans, span events (operator breakdown)
- DDL change detection included

### In Dynatrace

- All contexts appear as BizEvents within 1-2 minutes
- Event counts match Snowflake RUN_RESULTS table

## Success Criteria

- Procedures execute without SQL errors
- Results contain valid run_id UUIDs
- Entry counts > 0 (or source data is empty)
- BizEvents appear in Dynatrace within 1-2 minutes
- All telemetry types sent: logs, metrics, events, spans
- No ERROR level logs in RUN_LOG

## Key Information

**Connection Profile:** `snow_agent_test-qa`

**Database:** `DTAGENT_DB`

**Schema:** `APP` (procedures), `LOG` (results)

**Key Tables:**

- `DTAGENT_DB.LOG.RUN_LOG` - Execution logs
- `DTAGENT_DB.APP.RUN_RESULTS` - Telemetry counts

**BizEvent Contexts Expected:**

- org_costs_metering
- org_costs_storage
- org_costs_data_transfer
- org_billing_usage_in_currency
- org_billing_remaining_balance
- query_history
- query_cost_attribution (optional)

## How to Use

### First Time Users

1. Read **QUICKSTART.txt** (5 minutes)
1. Copy commands from **execution-commands.txt**
1. Execute in Snowflake and verify in Dynatrace

### Need Step-by-Step Instructions

→ Read **execution-guide.md**

### Want Technical Details

→ Read **plugin-architecture.md**

### Need to Verify Telemetry

→ Read **telemetry-structure.md** (includes DQL queries)

### Troubleshooting

→ See **execution-guide.md** (dedicated troubleshooting section)

## File Locations

All files are in `test/qa/plugins/`:

```text
test/qa/plugins/
├── README.md                  ← You are here
├── QUICKSTART.txt             ← Start here
├── execution-commands.txt     ← Copy-paste commands
├── execution-guide.md         ← Step-by-step + troubleshooting
├── telemetry-structure.md     ← Telemetry specs + DQL
├── plugin-architecture.md     ← Technical details
└── plugin-execution.sql       ← SQL script
```

## Next Steps

1. **Read:** QUICKSTART.txt (5 minutes)
1. **Execute:** Commands from execution-commands.txt
1. **Verify:** Check Snowflake logs and Dynatrace BizEvents
1. **Reference:** Use other files as needed

## Questions?

- How do I start? → QUICKSTART.txt
- What's the procedure? → execution-commands.txt
- How do I troubleshoot? → execution-guide.md
- How does it work? → plugin-architecture.md
- What telemetry is sent? → telemetry-structure.md

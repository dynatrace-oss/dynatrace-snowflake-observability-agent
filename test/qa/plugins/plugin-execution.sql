-- ============================================================================
-- Plugin Execution Test Suite
-- Purpose: Trigger org_costs and query_history plugins and verify telemetry
-- Profile: snow_agent_test-qa
-- ============================================================================

-- ============================================================================
-- TASK 1: Trigger org_costs procedure
-- ============================================================================

select 'TASK 1: Executing org_costs plugin' as task_info;

call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('org_costs'));

-- Expected output: Should show telemetry counts in the result
-- Look for: org_costs_metering, org_costs_storage, org_costs_data_transfer,
--           org_billing_usage_in_currency, org_billing_remaining_balance contexts


-- ============================================================================
-- TASK 2: Trigger query_history procedure
-- ============================================================================

select 'TASK 2: Executing query_history plugin' as task_info;

call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));

-- Expected output: Should show telemetry counts including query data
-- Look for: query_history context with entries, log_lines, metrics, spans, span_events


-- ============================================================================
-- TASK 3: Verify BizEvents were sent to Dynatrace
-- ============================================================================
-- Run these queries in Dynatrace DQL to confirm telemetry transmission

-- Query 3a: Check org_costs BizEvents
-- Execute in Dynatrace:
-- fetch bizevents
-- | filter context == "org_costs_metering" or context == "org_costs_storage"
--     or context == "org_costs_data_transfer"
--     or context == "org_billing_usage_in_currency"
--     or context == "org_billing_remaining_balance"
-- | filter timestamp >= now()-1h
-- | summarize event_count = count(), by: {context}

-- Query 3b: Check query_history BizEvents
-- Execute in Dynatrace:
-- fetch bizevents
-- | filter context == "query_history"
-- | filter timestamp >= now()-1h
-- | summarize event_count = count()

-- ============================================================================
-- TASK 3 ALTERNATIVE: Query agent logs directly
-- ============================================================================

select 'TASK 3: Checking agent execution logs' as task_info;

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

-- ============================================================================
-- TASK 3B: Verify telemetry counters
-- ============================================================================

select 'TASK 3B: Checking run results' as task_info;

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

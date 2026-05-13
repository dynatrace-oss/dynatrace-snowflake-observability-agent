-- ============================================================================
-- Cross-batch span parent persistence test for DSOA telemetry validation
-- Exercises: parent-child span linking across separate agent runs (BDX-644)
--
-- Coverage:
--   C4.10 — Cross-batch span parent persistence
--   C4.6  — Span.parent_id is reported
--   C4.7  — All queries in the same run have span.parent_id
--
-- Strategy:
--   The query_history plugin links child queries to parent queries via
--   QUERY_HISTORY.PARENT_QUERY_ID. When a parent query was processed in a
--   previous agent run, the plugin uses the STATUS.PROCESSED_QUERIES_CACHE
--   table to resolve the parent's span.id and set span.parent_id correctly.
--
--   To simulate cross-batch parent-child:
--     1. Create a stored procedure (SP_PARENT) that calls a child procedure
--        (SP_CHILD). The CALL statement generates PARENT_QUERY_ID linkage.
--     2. Run SP_PARENT, wait for one agent cycle to process the parent query.
--     3. Run SP_PARENT again — the child from run 2 should link to the parent
--        from run 2, demonstrating within-batch linking.
--     4. Create a TASK that calls SP_PARENT every few minutes — this generates
--        parent queries that span across agent cycles.
--
--   The key signal: a child query's span.parent_id should point to a span
--   from a DIFFERENT dsoa.run.id (cross-batch).
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - query_history plugin must be enabled with appropriate lookback
--
-- Cost: near-zero (XSMALL, auto-suspend 60s)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_span_cross_batch.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Shared warehouse for DSOA synthetic test setups';
GRANT USAGE ON WAREHOUSE DSOA_TEST_WH TO ROLE DTAGENT_QA_OWNER;

USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.SPAN_CROSS_BATCH;
USE SCHEMA DSOA_TEST_DB.SPAN_CROSS_BATCH;

-- ============================================================================
-- 2. Create a results table to track procedure executions
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.SPAN_CROSS_BATCH.EXECUTION_LOG (
    RUN_ID     NUMBER IDENTITY(1,1),
    CALLER     VARCHAR(50)  NOT NULL,
    RUN_TS     TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RESULT     VARCHAR(200)
);

-- ============================================================================
-- 3. Child procedure — called by the parent
--    The CALL statement produces PARENT_QUERY_ID linkage in QUERY_HISTORY
-- ============================================================================
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.SPAN_CROSS_BATCH.SP_CHILD()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
BEGIN
    -- Execute a query that takes measurable time
    LET v_count NUMBER;
    SELECT COUNT(*) INTO :v_count FROM TABLE(GENERATOR(ROWCOUNT => 5000));

    INSERT INTO DSOA_TEST_DB.SPAN_CROSS_BATCH.EXECUTION_LOG (CALLER, RESULT)
    VALUES ('SP_CHILD', 'Processed ' || :v_count || ' rows');

    RETURN 'child_done';
END;
$$;

-- ============================================================================
-- 4. Parent procedure — calls SP_CHILD and does its own work
--    QUERY_HISTORY will show: parent query (CALL SP_PARENT) -> child queries
--    inside SP_PARENT -> CALL SP_CHILD -> child queries inside SP_CHILD
-- ============================================================================
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.SPAN_CROSS_BATCH.SP_PARENT()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
BEGIN
    -- Parent's own work (generates query history entries linked to this call)
    LET v_sum NUMBER;
    SELECT SUM(UNIFORM(1, 100, RANDOM())) INTO :v_sum
    FROM TABLE(GENERATOR(ROWCOUNT => 10000));

    INSERT INTO DSOA_TEST_DB.SPAN_CROSS_BATCH.EXECUTION_LOG (CALLER, RESULT)
    VALUES ('SP_PARENT', 'Sum=' || :v_sum);

    -- Call child procedure — this creates the parent-child query linkage
    CALL DSOA_TEST_DB.SPAN_CROSS_BATCH.SP_CHILD();

    -- More parent work after child returns
    SELECT COUNT(*) INTO :v_sum
    FROM DSOA_TEST_DB.SPAN_CROSS_BATCH.EXECUTION_LOG;

    RETURN 'parent_done: ' || :v_sum || ' total executions';
END;
$$;

-- ============================================================================
-- 5. Task — runs SP_PARENT every 3 minutes to generate cross-batch data
--    Agent runs every 5 minutes by default, so:
--      - Task run at T+0: parent+child queries processed in agent run A
--      - Task run at T+3: parent+child queries may be in agent run A or B
--      - Task run at T+6: processed in agent run B
--    This guarantees cross-batch scenario where child in run B references
--    parent from run A (via PROCESSED_QUERIES_CACHE).
-- ============================================================================
CREATE OR REPLACE TASK DSOA_TEST_DB.SPAN_CROSS_BATCH.T_SPAN_WORKLOAD
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '3 MINUTE'
AS
    CALL DSOA_TEST_DB.SPAN_CROSS_BATCH.SP_PARENT();

-- ============================================================================
-- 6. Run immediately and start task
-- ============================================================================

-- First immediate execution (will be in agent run N)
CALL DSOA_TEST_DB.SPAN_CROSS_BATCH.SP_PARENT();

-- Resume task for continuous cross-batch generation
ALTER TASK DSOA_TEST_DB.SPAN_CROSS_BATCH.T_SPAN_WORKLOAD RESUME;

-- ============================================================================
-- 7. Verify setup
-- ============================================================================
SHOW PROCEDURES IN SCHEMA DSOA_TEST_DB.SPAN_CROSS_BATCH;
SHOW TASKS IN SCHEMA DSOA_TEST_DB.SPAN_CROSS_BATCH;
SELECT * FROM DSOA_TEST_DB.SPAN_CROSS_BATCH.EXECUTION_LOG ORDER BY RUN_TS DESC LIMIT 10;

-- ============================================================================
-- 8. Verification DQL (run after 2+ agent cycles)
-- ============================================================================
-- Cross-batch verification:
--   fetch spans
--   | filter db.system == "snowflake"
--   | filter deployment.environment == "DEV-095"
--   | filter isNotNull(span.parent_id)
--   | filter isNotNull(dsoa.run.id)
--   | fields trace.id, span.id, span.parent_id, dsoa.run.id, db.query.text
--   | joinNested parent = [
--     fetch spans
--     | filter db.system == "snowflake"
--     | filter deployment.environment == "DEV-095"
--     | fields span.id, dsoa.run.id
--   ], on: {left[span.parent_id] == right[span.id]}
--   | expand parent
--   | fieldsFlatten parent, prefix: "parent."
--   | filter dsoa.run.id != parent.dsoa.run.id
--   | limit 10
--
-- Expected: rows where dsoa.run.id != parent.dsoa.run.id (cross-batch)

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   ALTER TASK DSOA_TEST_DB.SPAN_CROSS_BATCH.T_SPAN_WORKLOAD SUSPEND;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.SPAN_CROSS_BATCH CASCADE;
-- ============================================================================

-- ============================================================================
-- Signal Protection / Overload test setup for DSOA telemetry validation
-- Exercises: max_entries cap and overload warning (BDX-1965)
--
-- Coverage:
--   C11.1 — max_entries cap is enforced (dsoa.acquisition.skipped_count > 0)
--   C11.2 — Overload warning logged (WARN level mentioning "max_entries")
--
-- Strategy:
--   The query_history plugin applies signal protection via max_entries config.
--   When the number of queries in a collection window exceeds max_entries,
--   the plugin keeps only the top N queries by execution_time (via SQL
--   ROW_NUMBER() + QUALIFY) and logs a warning. A self-monitoring bizevent
--   with dsoa.acquisition.skipped_count is also emitted.
--
--   To trigger this:
--     1. Generate a LARGE number of queries in a short window
--     2. Set max_entries to a value LOWER than the generated count
--     3. Run the agent — it should cap at max_entries and report skipped count
--
--   We generate ~500 queries in a burst, then set max_entries: 50.
--   Expected: agent processes 50, skips ~450.
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - query_history plugin enabled with max_entries set LOW
--
-- Cost: minimal (500 trivial queries on XSMALL)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_overload.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.OVERLOAD_TEST;
USE SCHEMA DSOA_TEST_DB.OVERLOAD_TEST;

-- ============================================================================
-- 2. Create a base table for queries to target
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.OVERLOAD_TEST.LOAD_TARGET (
    ID    NUMBER        NOT NULL,
    VALUE NUMBER(10, 2) NOT NULL,
    TAG   VARCHAR(50)   NOT NULL
);

INSERT INTO DSOA_TEST_DB.OVERLOAD_TEST.LOAD_TARGET
SELECT
    SEQ4() + 1,
    ROUND(UNIFORM(1, 9999, RANDOM()) / 100.0, 2),
    'overload_test'
FROM TABLE(GENERATOR(ROWCOUNT => 1000));

-- ============================================================================
-- 3. Generate a burst of queries (procedure that runs 500 individual queries)
--    Each query is distinct enough to appear as a separate row in QUERY_HISTORY.
-- ============================================================================
CREATE OR REPLACE PROCEDURE DSOA_TEST_DB.OVERLOAD_TEST.SP_GENERATE_QUERY_BURST()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    i NUMBER DEFAULT 0;
    v_cnt NUMBER;
BEGIN
    -- Generate 500 queries with varying predicates so each is unique
    -- Snowflake QUERY_HISTORY records each as a separate entry
    WHILE (i < 500) DO
        EXECUTE IMMEDIATE
            'SELECT COUNT(*) FROM DSOA_TEST_DB.OVERLOAD_TEST.LOAD_TARGET WHERE ID > ' || i::VARCHAR;
        i := i + 1;
    END WHILE;

    SELECT COUNT(*) INTO :v_cnt FROM DSOA_TEST_DB.OVERLOAD_TEST.LOAD_TARGET;
    RETURN 'Generated 500 queries, table has ' || :v_cnt || ' rows';
END;
$$;

-- ============================================================================
-- 4. Execute the burst
-- ============================================================================
CALL DSOA_TEST_DB.OVERLOAD_TEST.SP_GENERATE_QUERY_BURST();

-- ============================================================================
-- 5. Config instructions
-- ============================================================================
-- Set max_entries LOW to trigger the cap. In conf/config-test-qa.yml:
--
--   plugins:
--     query_history:
--       is_enabled: true
--       max_entries: 50
--       max_lookback_minutes: 10
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=config --options=skip_confirm
--
-- Then trigger agent run:
--   snow sql --connection snow_agent_test-qa \
--     --role DTAGENT_QA_VIEWER --database DTAGENT_QA_DB --warehouse DTAGENT_WH \
--     -q "CALL APP.DTAGENT(ARRAY_CONSTRUCT('query_history'))"
--
-- Verification DQL:
--
--   # C11.1 — skipped count > 0:
--   fetch bizevents
--   | filter dsoa.run.plugin == "query_history"
--   | filter isNotNull(dsoa.acquisition.skipped_count)
--   | summarize total_skipped = sum(dsoa.acquisition.skipped_count)
--
--   # C11.2 — overload warning logged:
--   fetch logs
--   | filter dsoa.run.context == "self_monitoring"
--   | filter loglevel == "WARN"
--   | filter contains(content, "max_entries")
--   | summarize count()
--
-- IMPORTANT: After verifying, RESTORE max_entries to production value:
--   plugins.query_history.max_entries: 5000  (or remove the key for unlimited)

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.OVERLOAD_TEST CASCADE;
-- ============================================================================

--
--
-- Copyright (c) 2025 Dynatrace Open Source
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
--
--
-- ============================================================================
-- QA simulation: DTAGENT_DB.APP.V_TASK_HISTORY limit, time boundary and watermark
--
-- INFORMATION_SCHEMA.TASK_HISTORY() cannot be mocked, so the view is only
-- exercised by generating real task runs. This script creates:
--   * 110 one-shot tasks, each executed once  -> more than 100 runs in the history window
--   * T_LONG_RUNNING (SYSTEM$WAIT 600s)       -> run stays EXECUTING across agent cycles,
--                                                its final state must be reported later
--   * T_SCHEDULED (resumed, 1-day schedule)   -> future run in state SCHEDULED
--                                                (no upper time bound on the view)
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role and DSOA_TEST_DB database exist
--   - tasks plugin enabled
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_task_history.sql
--
-- Verification: AE-C4.13 in the qa-runner skill / C4.13 in the release checklist.
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
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.TASK_HISTORY_SIM;
USE SCHEMA DSOA_TEST_DB.TASK_HISTORY_SIM;

-- The agent role must be able to see the simulated tasks in TASK_HISTORY().
GRANT USAGE ON DATABASE DSOA_TEST_DB TO ROLE DTAGENT_VIEWER;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.TASK_HISTORY_SIM TO ROLE DTAGENT_VIEWER;
GRANT MONITOR ON FUTURE TASKS IN SCHEMA DSOA_TEST_DB.TASK_HISTORY_SIM TO ROLE DTAGENT_VIEWER;

-- Long-running and scheduled tasks
CREATE OR REPLACE TASK T_LONG_RUNNING
    WAREHOUSE = DSOA_TEST_WH
AS
    CALL SYSTEM$WAIT(600);

CREATE OR REPLACE TASK T_SCHEDULED
    WAREHOUSE = DSOA_TEST_WH
    SCHEDULE  = '1440 MINUTE'
AS
    SELECT 1;

ALTER TASK T_SCHEDULED RESUME;
GRANT MONITOR ON ALL TASKS IN SCHEMA DSOA_TEST_DB.TASK_HISTORY_SIM TO ROLE DTAGENT_VIEWER;

-- 110 distinct tasks, one run each: runs in parallel, so they appear in the history at once
EXECUTE IMMEDIATE $$
BEGIN
    FOR i IN 1 TO 110 DO
        EXECUTE IMMEDIATE 'CREATE OR REPLACE TASK DSOA_TEST_DB.TASK_HISTORY_SIM.T_BULK_' || i
            || ' WAREHOUSE = DSOA_TEST_WH AS SELECT ' || i;
        EXECUTE IMMEDIATE 'EXECUTE TASK DSOA_TEST_DB.TASK_HISTORY_SIM.T_BULK_' || i;
    END FOR;
END;
$$;

EXECUTE TASK T_LONG_RUNNING;

-- Sanity check: expect > 110 runs
SELECT COUNT(*) AS RUNS, COUNT_IF(STATE = 'SCHEDULED') AS SCHEDULED, COUNT_IF(STATE = 'EXECUTING') AS EXECUTING
FROM TABLE(DSOA_TEST_DB.INFORMATION_SCHEMA.TASK_HISTORY(RESULT_LIMIT => 1000));

-- ============================================================================
-- CLEANUP:
--   USE ROLE DTAGENT_QA_OWNER;
--   ALTER TASK DSOA_TEST_DB.TASK_HISTORY_SIM.T_SCHEDULED SUSPEND;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.TASK_HISTORY_SIM CASCADE;
-- ============================================================================

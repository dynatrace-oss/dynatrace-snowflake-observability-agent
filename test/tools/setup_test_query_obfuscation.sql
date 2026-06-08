-- ============================================================================
-- Query Text Obfuscation test setup for DSOA telemetry validation
-- Exercises: obfuscation_mode = off | literals | full (BDX-1916)
--
-- Coverage:
--   C10.1 — Mode: off — db.query.text contains original SQL with literals intact
--   C10.2 — Mode: literals — string and integer literals replaced with ?
--   C10.3 — Mode: full — db.query.text contains only normalized hash
--
-- Strategy:
--   Execute queries with KNOWN, UNIQUE string literals that can be searched for
--   in DQL to verify presence (mode=off) or absence (mode=literals/full).
--   The marker string 'DSOA_OBFUSCATION_TEST' and integer 99887766 are used
--   as sentinels.
--
--   Test procedure:
--     1. Run this script (generates queries with known literals)
--     2. Set obfuscation_mode: "off" in config, deploy, wait for agent cycle
--     3. Verify C10.1: DQL finds 'DSOA_OBFUSCATION_TEST' in db.query.text
--     4. Set obfuscation_mode: "literals", deploy, wait for cycle
--     5. Run this script AGAIN (new queries with same literals)
--     6. Verify C10.2: NEW queries should NOT contain the literal
--     7. Set obfuscation_mode: "full", deploy, wait for cycle
--     8. Run this script AGAIN
--     9. Verify C10.3: db.query.text should not contain SELECT keyword
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - query_history plugin must be enabled
--
-- Cost: near-zero (simple SELECT queries)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_query_obfuscation.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.OBFUSCATION_TEST;
USE SCHEMA DSOA_TEST_DB.OBFUSCATION_TEST;

-- ============================================================================
-- 2. Create a test table for queries to reference
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA (
    ID    NUMBER        NOT NULL,
    NAME  VARCHAR(100)  NOT NULL,
    VALUE NUMBER(10, 2) NOT NULL
);

INSERT INTO DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA
SELECT
    SEQ4() + 1,
    'item_' || (SEQ4() + 1),
    ROUND(UNIFORM(1, 9999, RANDOM()) / 100.0, 2)
FROM TABLE(GENERATOR(ROWCOUNT => 200));

-- ============================================================================
-- 3. Execute queries with known sentinel literals
--    These will appear in QUERY_HISTORY and be processed by the plugin.
--    Each query uses a unique combination of sentinels for easy DQL filtering.
-- ============================================================================

-- Query with string literal sentinel
SELECT * FROM DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA
WHERE NAME = 'DSOA_OBFUSCATION_TEST';

-- Query with integer literal sentinel
SELECT * FROM DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA
WHERE ID = 99887766;

-- Query combining both sentinels
SELECT COUNT(*) AS cnt
FROM DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA
WHERE NAME LIKE 'DSOA_OBFUSCATION_TEST%'
  AND VALUE > 99887766;

-- Query with multiple string literals
SELECT ID, NAME, VALUE
FROM DSOA_TEST_DB.OBFUSCATION_TEST.SENTINEL_DATA
WHERE NAME IN ('DSOA_OBFUSCATION_TEST', 'DSOA_OBFUSCATION_CONTROL')
   OR ID BETWEEN 99887766 AND 99887799;

-- Query with string in a function call
SELECT LENGTH('DSOA_OBFUSCATION_TEST') AS sentinel_len,
       99887766 AS sentinel_int,
       CURRENT_TIMESTAMP() AS run_ts;

-- ============================================================================
-- 4. Config switching instructions
-- ============================================================================
-- To test each mode, update conf/config-test-qa.yml:
--
--   # Mode OFF (default):
--   plugins:
--     query_history:
--       obfuscation_mode: "off"
--
--   # Mode LITERALS:
--   plugins:
--     query_history:
--       obfuscation_mode: "literals"
--
--   # Mode FULL:
--   plugins:
--     query_history:
--       obfuscation_mode: "full"
--
-- After each config change:
--   ./scripts/deploy/deploy.sh test-qa --scope=config --options=skip_confirm
--
-- Then re-run this script to generate fresh queries under the new mode:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_query_obfuscation.sql
--
-- Wait for one agent cycle, then verify with DQL:
--
--   # C10.1 (mode=off, expect count > 0):
--   fetch spans
--   | filter dsoa.run.context == "query_history"
--   | filter deployment.environment == "DEV-095"
--   | filter contains(db.query.text, "'DSOA_OBFUSCATION_TEST'")
--   | summarize count()
--
--   # C10.2 (mode=literals, expect count == 0 for NEW queries):
--   fetch spans
--   | filter dsoa.run.context == "query_history"
--   | filter deployment.environment == "DEV-095"
--   | filter timestamp > now() - 30m
--   | filter contains(db.query.text, "'DSOA_OBFUSCATION_TEST'")
--   | summarize count()
--
--   # C10.3 (mode=full, expect count == 0):
--   fetch spans
--   | filter dsoa.run.context == "query_history"
--   | filter deployment.environment == "DEV-095"
--   | filter timestamp > now() - 30m
--   | filter matchesPhrase(db.query.text, "SELECT")
--   | summarize count()

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.OBFUSCATION_TEST CASCADE;
-- ============================================================================

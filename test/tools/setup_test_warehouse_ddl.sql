-- ============================================================================
-- Warehouse DDL Detection test setup for DSOA telemetry validation
-- Exercises: DDL change detection attributes on query spans (BDX-1998)
--
-- Coverage:
--   C4.13 — DDL change detection on query spans
--           (snowflake.object.type, .name, .ddl.operation, .ddl.properties)
--
-- Strategy:
--   The query_history plugin (when track_ddl_changes=true) joins
--   SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY and extracts the
--   OBJECT_MODIFIED_BY_DDL array. This array is populated for DDL queries
--   (CREATE, ALTER, DROP, etc.) with ~3h latency from query execution.
--
--   We generate varied DDL operations:
--     1. CREATE TABLE (ddl_operation = CREATE)
--     2. ALTER TABLE ADD COLUMN (ddl_operation = ALTER)
--     3. ALTER TABLE RENAME (ddl_operation = ALTER)
--     4. CREATE OR REPLACE VIEW (ddl_operation = CREATE)
--     5. DROP TABLE (ddl_operation = DROP)
--     6. ALTER WAREHOUSE (ddl_operation = ALTER) — warehouse DDL
--
--   After ~3h, ACCESS_HISTORY will contain OBJECT_MODIFIED_BY_DDL entries
--   for these queries. The agent's next run will attach DDL attributes to spans.
--
-- Prerequisites:
--   - DTAGENT_QA_OWNER role must exist
--   - DSOA_TEST_DB must exist
--   - query_history plugin must have track_ddl_changes: true
--
-- LATENCY: ACCESS_HISTORY has ~3h lag for DDL attributes.
-- Mark as [DEFERRED] in checklist — seed now, verify after 3+ hours.
--
-- Cost: near-zero (DDL metadata operations only)
--
-- HOW TO RUN:
--   snow sql --connection snow_agent_test-qa -f test/tools/setup_test_warehouse_ddl.sql
-- ============================================================================

-- ============================================================================
-- 1. Setup
-- ============================================================================
USE ROLE DTAGENT_QA_OWNER;
USE WAREHOUSE DSOA_TEST_WH;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.DDL_DETECTION_TEST;
USE SCHEMA DSOA_TEST_DB.DDL_DETECTION_TEST;

-- ============================================================================
-- 2. DDL Operation: CREATE TABLE
-- ============================================================================
CREATE OR REPLACE TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_TABLE (
    ID    NUMBER NOT NULL,
    NAME  VARCHAR(100),
    VALUE NUMBER(10, 2)
);

-- Insert some data so the table is non-trivial
INSERT INTO DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_TABLE
SELECT SEQ4() + 1, 'row_' || (SEQ4() + 1), ROUND(UNIFORM(1, 999, RANDOM()) / 10.0, 2)
FROM TABLE(GENERATOR(ROWCOUNT => 50));

-- ============================================================================
-- 3. DDL Operation: ALTER TABLE ADD COLUMN
-- ============================================================================
ALTER TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_TABLE
    ADD COLUMN CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP();

-- ============================================================================
-- 4. DDL Operation: ALTER TABLE ADD CONSTRAINT (comment change)
-- ============================================================================
ALTER TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_TABLE
    SET COMMENT = 'DSOA DDL detection test table — modified at ' || CURRENT_TIMESTAMP()::VARCHAR;

-- ============================================================================
-- 5. DDL Operation: CREATE VIEW
-- ============================================================================
CREATE OR REPLACE VIEW DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_VIEW AS
SELECT ID, NAME, VALUE
FROM DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_TARGET_TABLE
WHERE VALUE > 10;

-- ============================================================================
-- 6. DDL Operation: CREATE another table then DROP it
-- ============================================================================
CREATE TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_EPHEMERAL (
    X NUMBER NOT NULL
);

DROP TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_EPHEMERAL;

-- ============================================================================
-- 7. DDL Operation: ALTER TABLE RENAME
-- ============================================================================
CREATE TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_RENAME_SOURCE (
    A NUMBER NOT NULL
);

ALTER TABLE DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_RENAME_SOURCE
    RENAME TO DSOA_TEST_DB.DDL_DETECTION_TEST.DDL_RENAMED_TABLE;

-- ============================================================================
-- 8. DDL Operation: ALTER WAREHOUSE (warehouse DDL — held-back logic)
-- ============================================================================
-- The query_history plugin holds back warehouse/resource-monitor DDL queries
-- until ACCESS_HISTORY catches up. This tests that hold-back path.
ALTER WAREHOUSE DSOA_TEST_WH SET COMMENT = 'DDL detection test — ' || CURRENT_TIMESTAMP()::VARCHAR;

-- ============================================================================
-- 9. Config requirements
-- ============================================================================
-- In conf/config-test-qa.yml:
--   plugins:
--     query_history:
--       is_enabled: true
--       track_ddl_changes: true
--
-- Deploy:
--   ./scripts/deploy/deploy.sh test-qa --scope=plugins,config --options=skip_confirm

-- ============================================================================
-- 10. Verification DQL (run 3+ hours after executing this script)
-- ============================================================================
-- C4.13 — DDL attributes on spans:
--   fetch spans
--   | filter deployment.environment == "DEV-095"
--   | filter isNotNull(snowflake.object.ddl.operation)
--   | fields snowflake.object.name, snowflake.object.type,
--           snowflake.object.ddl.operation, snowflake.object.ddl.properties
--   | limit 20
--
-- Expected: rows with ddl.operation in {CREATE, ALTER, DROP}
-- and object.name matching DDL_TARGET_TABLE, DDL_TARGET_VIEW, etc.

-- ============================================================================
-- CLEANUP (run when done testing):
--   USE ROLE DTAGENT_QA_OWNER;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.DDL_DETECTION_TEST CASCADE;
--   ALTER WAREHOUSE DSOA_TEST_WH SET COMMENT = '';
-- ============================================================================

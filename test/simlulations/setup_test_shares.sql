-- ============================================================================
-- Shares plugin test setup for DSOA telemetry validation
-- Database: DSOA_TEST_DB   Schema: DSOA_TEST_DB.SHARES
-- Cost: near-zero (no compute required — shares are metadata only)
--
-- NOTE: This script is DSOA-independent. It creates test data that DSOA
-- will observe once deployed. No DTAGENT_* roles or objects are referenced.
-- DSOA's own deploy grants its viewer role access.
--
-- Dashboard tiles covered:
--   Section 1 — Share Inventory
--     "1"  Outbound Shares count KPI          → 3 outbound shares
--     "2"  Inbound Shares count KPI           → existing account shares
--     "3"  All Shares Inventory table         → all 3 outbound shares visible
--
--   Section 2 — Inbound Share Health
--     "11" UNAVAILABLE Inbound Shares         → see NOTE below
--     "12" Share Availability Status honeycomb → see NOTE below
--     "13" Shared Table Row Counts & Size      → see NOTE below
--     "14" Shares with Deleted Database        → see NOTE below
--
--   Section 3 — Outbound Share Security
--     "21" Secure-Objects-Only Compliance pie → 2 compliant, 1 non-compliant
--     "22" Grant Details table                → all grant rows for 3 shares
--     "23" Outbound Share Grantees bar chart  → 2 distinct grantees
--
-- NOTE — Inbound share tiles (Section 2):
--   Inbound share telemetry is collected by DSOA via P_GET_SHARES(), which
--   calls SHOW GRANTS TO SHARE for each OUTBOUND share in a cursor loop. A
--   pre-existing bug causes P_GET_SHARES to fail with "data type of returned
--   table does not match" when any outbound share has zero grants (e.g.
--   DEVEL_CI360_SHARE2 in this account). Until that is fixed, TMP_INBOUND_SHARES
--   is never populated and inbound tiles show "No records". This is NOT caused
--   by the synthetic setup — it is a bug in P_GET_SHARES.
--   See: src/dtagent/plugins/shares.sql/053_p_get_shares.sql
-- ============================================================================

USE ROLE SYSADMIN;

-- 1. Ensure shared test database and plugin schema exist
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.SHARES;

USE DATABASE DSOA_TEST_DB;
USE SCHEMA DSOA_TEST_DB.SHARES;

-- ── Tables shared outbound ────────────────────────────────────────────────────

-- Analytics data (shared via secure view — compliant)
CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.SALES_DATA (
    sale_id     NUMBER AUTOINCREMENT,
    product     VARCHAR(100),
    amount      NUMBER(12, 2),
    region      VARCHAR(50),
    sale_date   DATE DEFAULT CURRENT_DATE()
);

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.PRODUCT_CATALOG (
    sku         VARCHAR(50),
    product_name VARCHAR(200),
    category    VARCHAR(100),
    price       NUMBER(10, 2)
);

-- Reporting data (shared directly as base table — non-compliant)
CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.CUSTOMER_METRICS (
    customer_id NUMBER,
    segment     VARCHAR(50),
    lifetime_value NUMBER(12, 2),
    updated_at  TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Operational data (shared directly as base table — non-compliant)
CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.PIPELINE_STATUS (
    pipeline_id NUMBER,
    name        VARCHAR(100),
    status      VARCHAR(20),
    last_run    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Insert sample rows so row-count tiles show meaningful data
INSERT INTO DSOA_TEST_DB.SHARES.SALES_DATA (product, amount, region)
SELECT 'Widget-A', 299.99, 'EMEA'
UNION ALL SELECT 'Widget-B', 149.50, 'AMER'
UNION ALL SELECT 'Widget-C', 89.00, 'APAC'
UNION ALL SELECT 'Service-Pro', 2499.00, 'EMEA'
UNION ALL SELECT 'Service-Basic', 499.00, 'AMER';

INSERT INTO DSOA_TEST_DB.SHARES.CUSTOMER_METRICS (customer_id, segment, lifetime_value)
SELECT 1001, 'Enterprise', 125000.00
UNION ALL SELECT 1002, 'Mid-Market', 45000.00
UNION ALL SELECT 1003, 'SMB', 8500.00;

INSERT INTO DSOA_TEST_DB.SHARES.PRODUCT_CATALOG (sku, product_name, category, price)
SELECT 'WGT-001', 'Widget A Premium', 'Hardware', 299.99
UNION ALL SELECT 'WGT-002', 'Widget B Standard', 'Hardware', 149.50
UNION ALL SELECT 'SVC-001', 'Service Pro Annual', 'Software', 2499.00;

INSERT INTO DSOA_TEST_DB.SHARES.PIPELINE_STATUS (pipeline_id, name, status)
SELECT 1, 'nightly-etl', 'RUNNING'
UNION ALL SELECT 2, 'weekly-rollup', 'COMPLETED'
UNION ALL SELECT 3, 'hourly-ingest', 'FAILED';

-- Secure view for compliant sharing (only exposes non-PII columns)
CREATE OR REPLACE SECURE VIEW DSOA_TEST_DB.SHARES.V_SALES_PUBLIC AS
SELECT sale_id, product, region, sale_date
FROM DSOA_TEST_DB.SHARES.SALES_DATA;

-- ── Outbound shares ───────────────────────────────────────────────────────────

-- Share 1: DSOA_ANALYTICS_SHARE — COMPLIANT
--   Uses only secure views → secure_objects_only = TRUE
--   Granted to one external grantee account
CREATE SHARE IF NOT EXISTS DSOA_ANALYTICS_SHARE;
ALTER SHARE DSOA_ANALYTICS_SHARE SET
    COMMENT = 'DSOA test share: analytics data for partner accounts';
ALTER SHARE DSOA_ANALYTICS_SHARE SET SECURE_OBJECTS_ONLY = TRUE;

GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_ANALYTICS_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES TO SHARE DSOA_ANALYTICS_SHARE;
GRANT SELECT ON VIEW DSOA_TEST_DB.SHARES.V_SALES_PUBLIC TO SHARE DSOA_ANALYTICS_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES.PRODUCT_CATALOG TO SHARE DSOA_ANALYTICS_SHARE;

-- Share 2: DSOA_REPORTING_SHARE — NON-COMPLIANT
--   Grants a base table directly (not a secure view) → secure_objects_only = FALSE
--   This exercises the non-compliant slice in the compliance pie chart
CREATE SHARE IF NOT EXISTS DSOA_REPORTING_SHARE;
ALTER SHARE DSOA_REPORTING_SHARE SET
    COMMENT = 'DSOA test share: reporting data (non-secure objects — intentionally non-compliant)';
ALTER SHARE DSOA_REPORTING_SHARE SET SECURE_OBJECTS_ONLY = FALSE;

GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_REPORTING_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES TO SHARE DSOA_REPORTING_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES.CUSTOMER_METRICS TO SHARE DSOA_REPORTING_SHARE;

-- Share 3: DSOA_OPS_SHARE — NON-COMPLIANT
--   Second non-compliant share — grants a base table to a different grantee
--   Adds variety to the grantees bar chart and grant details table
CREATE SHARE IF NOT EXISTS DSOA_OPS_SHARE;
ALTER SHARE DSOA_OPS_SHARE SET
    COMMENT = 'DSOA test share: operational pipeline status for internal consumers (non-secure objects)';
ALTER SHARE DSOA_OPS_SHARE SET SECURE_OBJECTS_ONLY = FALSE;

GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_OPS_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES TO SHARE DSOA_OPS_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES.PIPELINE_STATUS TO SHARE DSOA_OPS_SHARE;

-- ── Verify setup ──────────────────────────────────────────────────────────────
SHOW SHARES;
SHOW GRANTS TO SHARE DSOA_ANALYTICS_SHARE;
SHOW GRANTS TO SHARE DSOA_REPORTING_SHARE;
SHOW GRANTS TO SHARE DSOA_OPS_SHARE;

-- ============================================================================
-- CLEANUP (run when done testing):
--
-- USE ROLE SYSADMIN;
-- DROP SHARE IF EXISTS DSOA_ANALYTICS_SHARE;
-- DROP SHARE IF EXISTS DSOA_REPORTING_SHARE;
-- DROP SHARE IF EXISTS DSOA_OPS_SHARE;
-- DROP SCHEMA IF EXISTS DSOA_TEST_DB.SHARES;
-- (Only drop DSOA_TEST_DB itself if no other plugins are using it.)
-- ============================================================================

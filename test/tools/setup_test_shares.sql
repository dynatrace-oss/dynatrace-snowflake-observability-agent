-- ============================================================================
-- Shares plugin test setup for DSOA telemetry validation
-- Creates test OUTBOUND shares with granted objects to exercise all dashboard
-- tiles for the Shares & Governance dashboard.
--
-- NOTE: This script is DSOA-independent. It creates test data that DSOA
-- will observe once deployed. No DTAGENT_* roles or objects are referenced.
-- DSOA's own deploy grants its viewer role access.
--
-- Dashboard tiles covered:
--   Section 1 — Share Inventory: count KPIs, all-shares table
--   Section 2 — Inbound Share Health: availability status, row counts,
--               UNAVAILABLE shares (existing INBOUND shares cover this)
--   Section 3 — Outbound Share Security: secure-objects-only, grant details,
--               grantee bar chart
--
-- Inbound shares: Already present in this account via Snowflake-provided
--   shares (ACCOUNT_USAGE, SAMPLE_DATA, SANDBOX_TEST_SHARE, etc.).
--   No additional inbound shares need to be created.
-- ============================================================================

USE ROLE SYSADMIN;

-- 1. Create a test database and tables that will be shared outbound.
--    All objects owned by SYSADMIN.
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.SHARES;

USE DATABASE DSOA_TEST_DB;
USE SCHEMA DSOA_TEST_DB.SHARES;

-- Shared tables that will be added to outbound shares
CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.SALES_DATA (
    sale_id     NUMBER AUTOINCREMENT,
    product     VARCHAR(100),
    amount      NUMBER(12, 2),
    region      VARCHAR(50),
    sale_date   DATE DEFAULT CURRENT_DATE()
);

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.CUSTOMER_METRICS (
    customer_id NUMBER,
    segment     VARCHAR(50),
    lifetime_value NUMBER(12, 2),
    updated_at  TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE DSOA_TEST_DB.SHARES.PRODUCT_CATALOG (
    sku         VARCHAR(50),
    product_name VARCHAR(200),
    category    VARCHAR(100),
    price       NUMBER(10, 2)
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

-- 2. Create secure views required for outbound shares (secure objects only compliance)
CREATE OR REPLACE SECURE VIEW DSOA_TEST_DB.SHARES.V_SALES_PUBLIC AS
SELECT sale_id, product, region, sale_date
FROM DSOA_TEST_DB.SHARES.SALES_DATA;

-- 3. Create outbound shares
--    Share 1: compliant (secure_objects_only = true, uses secure view)
CREATE SHARE IF NOT EXISTS DSOA_ANALYTICS_SHARE;
ALTER SHARE DSOA_ANALYTICS_SHARE SET COMMENT = 'DSOA test share: analytics data for partner accounts';

GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_ANALYTICS_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES TO SHARE DSOA_ANALYTICS_SHARE;
GRANT SELECT ON VIEW DSOA_TEST_DB.SHARES.V_SALES_PUBLIC TO SHARE DSOA_ANALYTICS_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES.PRODUCT_CATALOG TO SHARE DSOA_ANALYTICS_SHARE;

--    Share 2: non-compliant (grants access to a base table, not a secure view)
--    This exercises the secure-objects-only compliance pie chart
CREATE SHARE IF NOT EXISTS DSOA_REPORTING_SHARE;
ALTER SHARE DSOA_REPORTING_SHARE SET COMMENT = 'DSOA test share: reporting data (non-secure objects)';

GRANT USAGE ON DATABASE DSOA_TEST_DB TO SHARE DSOA_REPORTING_SHARE;
GRANT USAGE ON SCHEMA DSOA_TEST_DB.SHARES TO SHARE DSOA_REPORTING_SHARE;
GRANT SELECT ON TABLE DSOA_TEST_DB.SHARES.CUSTOMER_METRICS TO SHARE DSOA_REPORTING_SHARE;

-- 4. Verify setup
SHOW SHARES;
SHOW GRANTS TO SHARE DSOA_ANALYTICS_SHARE;
SHOW GRANTS TO SHARE DSOA_REPORTING_SHARE;

-- ============================================================================
-- CLEANUP (run when done testing):
--
-- USE ROLE SYSADMIN;
-- DROP SHARE IF EXISTS DSOA_ANALYTICS_SHARE;
-- DROP SHARE IF EXISTS DSOA_REPORTING_SHARE;
-- DROP SCHEMA IF EXISTS DSOA_TEST_DB.SHARES;
-- (Only drop the DB itself if no other plugins are using it.)
-- ============================================================================

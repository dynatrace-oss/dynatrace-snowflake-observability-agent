-- ============================================================================
-- Data Volume & Storage test setup for DSOA telemetry validation
-- Creates objects to exercise the `data_volume` and `data_schemas` plugins.
--
-- Self-contained: creates DSOA_TEST_WH warehouse and DSOA_TEST_DB database
-- (both with IF NOT EXISTS guards). No DSOA installation required — this
-- script is intentionally DSOA-independent and can run before DSOA is deployed.
-- DSOA's own admin deploy grants its viewer role access to DSOA_TEST_DB.
--
-- Objects created
--   Warehouse: DSOA_TEST_WH            (XSMALL, auto-suspend 60 s, shared)
--   Database : DSOA_TEST_DB
--   Schema   : DSOA_TEST_DB.DATA_VOLUME
--
--   Base tables (exercises data_volume plugin — size + row count metrics):
--     FACTS_ORDERS       — large table (~5 000 rows) simulating order facts
--     FACTS_EVENTS       — medium table (~2 000 rows) simulating event facts
--     DIM_CUSTOMERS      — small dimension table (~200 rows)
--     DIM_PRODUCTS       — small dimension table (~100 rows)
--     ARCHIVE_OLD_ORDERS — stale table: populated then left untouched
--
--   DDL churn objects (exercises data_schemas plugin — ACCESS_HISTORY DDL rows):
--     DDL_TEST_TABLE_A   — created, then altered (ADD COLUMN), producing ALTER events
--     DDL_TEST_TABLE_B   — created then dropped, producing CREATE + DROP events
--     SCHEMA_V1          — created then dropped, producing schema-level DDL events
--
-- Coverage per dashboard tile
--   Total Storage KPI              → bytes from FACTS_ORDERS, FACTS_EVENTS, DIM_*
--   Total Row Count KPI            → row_count from all base tables
--   Storage growth over time       → bytes trended per db.namespace
--   Row count trends               → row_count trended per db.namespace
--   Top 20 tables by size          → FACTS_ORDERS, FACTS_EVENTS ranked first
--   Table type distribution        → BASE TABLE entries (Snowflake internal stages
--                                    cannot back external tables — cloud storage only)
--   Stale tables                   → ARCHIVE_OLD_ORDERS (last_altered at creation)
--   Days since last DDL dist.      → spread across tables created at different times
--   DDL operations over time       → CREATE/ALTER/DROP events from DDL churn objects
--   Object type breakdown          → Table + Schema DDL events
--   Recent DDL operations          → DDL_TEST_TABLE_A ALTER, DDL_TEST_TABLE_B DROP
--
-- NOTE: SNOWFLAKE.ACCOUNT_USAGE views have up to 3-hour propagation latency.
--       data_volume and data_schemas tiles may take 3-4 h after setup to appear.
--
-- Cost: near-zero — XSMALL warehouse, auto-suspends in 60 s, small row counts.
-- ============================================================================


-- ============================================================================
-- 1. Warehouse (shared across all DSOA synthetic test setups)
-- ============================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS DSOA_TEST_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Shared warehouse for DSOA synthetic test setups';

USE WAREHOUSE DSOA_TEST_WH;

-- ============================================================================
-- 2. Database and schema
-- ============================================================================
CREATE DATABASE IF NOT EXISTS DSOA_TEST_DB;

USE DATABASE DSOA_TEST_DB;

CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.DATA_VOLUME;

USE SCHEMA DSOA_TEST_DB.DATA_VOLUME;

-- ============================================================================
-- 3. Base tables with varied sizes and row counts
-- ============================================================================

-- Large fact table: simulates order facts (~5 000 rows, meaningful bytes)
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.FACTS_ORDERS (
    ORDER_ID       NUMBER        NOT NULL,
    CUSTOMER_ID    NUMBER        NOT NULL,
    PRODUCT_ID     NUMBER        NOT NULL,
    ORDER_DATE     DATE          NOT NULL,
    QUANTITY       NUMBER(10, 2) NOT NULL,
    UNIT_PRICE     NUMBER(10, 4) NOT NULL,
    TOTAL_AMOUNT   NUMBER(14, 4) NOT NULL,
    STATUS         VARCHAR(20)   NOT NULL,
    REGION         VARCHAR(50),
    NOTES          VARCHAR(500)
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.FACTS_ORDERS
WITH gen AS (
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS rn
    FROM TABLE(GENERATOR(ROWCOUNT => 5000))
)
SELECT
    rn                                                                                AS ORDER_ID,
    MOD(rn, 200) + 1                                                                  AS CUSTOMER_ID,
    MOD(rn, 100) + 1                                                                  AS PRODUCT_ID,
    DATEADD(DAY, -MOD(rn, 365), CURRENT_DATE())                                       AS ORDER_DATE,
    (MOD(rn, 20) + 1) * 1.0                                                           AS QUANTITY,
    (MOD(rn, 100) + 10) * 1.5                                                         AS UNIT_PRICE,
    ((MOD(rn, 20) + 1) * (MOD(rn, 100) + 10) * 1.5)                                  AS TOTAL_AMOUNT,
    CASE MOD(rn, 5)
        WHEN 0 THEN 'PENDING' WHEN 1 THEN 'SHIPPED' WHEN 2 THEN 'DELIVERED'
        WHEN 3 THEN 'RETURNED' ELSE 'CANCELLED'
    END                                                                               AS STATUS,
    CASE MOD(rn, 4)
        WHEN 0 THEN 'EMEA' WHEN 1 THEN 'AMER' WHEN 2 THEN 'APAC' ELSE 'LATAM'
    END                                                                               AS REGION,
    CONCAT('Order note for item ', rn, ' — synthetic data for DSOA dashboard validation.') AS NOTES
FROM gen;

-- Medium fact table: simulates application events (~2 000 rows)
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.FACTS_EVENTS (
    EVENT_ID       NUMBER        NOT NULL,
    SESSION_ID     VARCHAR(40)   NOT NULL,
    USER_ID        NUMBER        NOT NULL,
    EVENT_TYPE     VARCHAR(50)   NOT NULL,
    EVENT_TS       TIMESTAMP_NTZ NOT NULL,
    PAGE           VARCHAR(200),
    DURATION_MS    NUMBER        NOT NULL,
    IS_ERROR       BOOLEAN       NOT NULL DEFAULT FALSE
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.FACTS_EVENTS
WITH gen AS (
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS rn
    FROM TABLE(GENERATOR(ROWCOUNT => 2000))
)
SELECT
    rn                                                                                AS EVENT_ID,
    CONCAT('sess-', LPAD(MOD(rn, 400)::VARCHAR, 6, '0'))                              AS SESSION_ID,
    MOD(rn, 200) + 1                                                                  AS USER_ID,
    CASE MOD(rn, 6)
        WHEN 0 THEN 'PAGE_VIEW' WHEN 1 THEN 'CLICK'
        WHEN 2 THEN 'SUBMIT'    WHEN 3 THEN 'SCROLL'
        WHEN 4 THEN 'HOVER'     ELSE 'NAVIGATE'
    END                                                                               AS EVENT_TYPE,
    DATEADD(SECOND, -MOD(rn, 86400), CURRENT_TIMESTAMP())                             AS EVENT_TS,
    CONCAT('/page/', MOD(rn, 50))                                                     AS PAGE,
    MOD(rn, 5000) + 10                                                                AS DURATION_MS,
    (MOD(rn, 20) = 0)                                                                 AS IS_ERROR
FROM gen;

-- Small dimension: customers (~200 rows)
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.DIM_CUSTOMERS (
    CUSTOMER_ID    NUMBER       NOT NULL,
    FULL_NAME      VARCHAR(100) NOT NULL,
    EMAIL          VARCHAR(150),
    COUNTRY        VARCHAR(60),
    TIER           VARCHAR(20)
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.DIM_CUSTOMERS
WITH gen AS (
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS rn
    FROM TABLE(GENERATOR(ROWCOUNT => 200))
)
SELECT
    rn,
    CONCAT('Customer ', rn),
    CONCAT('customer', rn, '@example.com'),
    CASE MOD(rn, 5) WHEN 0 THEN 'US' WHEN 1 THEN 'DE' WHEN 2 THEN 'JP' WHEN 3 THEN 'BR' ELSE 'GB' END,
    CASE MOD(rn, 3) WHEN 0 THEN 'GOLD' WHEN 1 THEN 'SILVER' ELSE 'BRONZE' END
FROM gen;

-- Small dimension: products (~100 rows)
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.DIM_PRODUCTS (
    PRODUCT_ID     NUMBER       NOT NULL,
    PRODUCT_NAME   VARCHAR(100) NOT NULL,
    CATEGORY       VARCHAR(50),
    UNIT_COST      NUMBER(10, 4)
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.DIM_PRODUCTS
WITH gen AS (
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS rn
    FROM TABLE(GENERATOR(ROWCOUNT => 100))
)
SELECT
    rn,
    CONCAT('Product-', LPAD(rn::VARCHAR, 4, '0')),
    CASE MOD(rn, 4) WHEN 0 THEN 'Electronics' WHEN 1 THEN 'Apparel' WHEN 2 THEN 'Furniture' ELSE 'Food' END,
    (MOD(rn, 100) + 5) * 1.25
FROM gen;

-- Stale archive table: last_altered set at creation time and never touched,
-- so the data_volume plugin reports a high time_since_last_update for this table.
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.ARCHIVE_OLD_ORDERS (
    ORDER_ID       NUMBER        NOT NULL,
    ARCHIVED_DATE  DATE          NOT NULL,
    AMOUNT         NUMBER(14, 4)
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.ARCHIVE_OLD_ORDERS
WITH gen AS (
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) AS rn
    FROM TABLE(GENERATOR(ROWCOUNT => 300))
)
SELECT
    rn,
    DATEADD(DAY, -(MOD(rn, 730) + 365), CURRENT_DATE()),
    (MOD(rn, 500) + 50) * 1.0
FROM gen;

-- ============================================================================
-- 4. External table note
-- Snowflake does not allow internal named stages as external table locations
-- (cloud storage — S3/GCS/Azure — is required). The table-type-distribution
-- tile reads TABLE_TYPE from SNOWFLAKE.ACCOUNT_USAGE.TABLES; BASE TABLE rows
-- from the tables above are sufficient to exercise that tile.
-- ============================================================================

-- ============================================================================
-- 5. DDL churn objects for data_schemas plugin
--    These operations appear in SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY after
--    the ~3-hour propagation delay.
-- ============================================================================

-- Table A: created then altered twice → CREATE + 2 × ALTER events
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_A (
    ID      NUMBER        NOT NULL,
    NAME    VARCHAR(100),
    CREATED TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

ALTER TABLE DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_A
    ADD COLUMN STATUS VARCHAR(20);

ALTER TABLE DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_A
    ADD COLUMN UPDATED_AT TIMESTAMP_NTZ;

-- Table B: created, populated, then dropped → CREATE + DROP events
CREATE OR REPLACE TABLE DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_B (
    ID    NUMBER,
    VALUE VARCHAR(200)
);

INSERT INTO DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_B
SELECT SEQ4(), CONCAT('value-', SEQ4())
FROM TABLE(GENERATOR(ROWCOUNT => 50));

DROP TABLE IF EXISTS DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_B;

-- Schema DDL: create then drop an extra schema → schema-level DDL events
CREATE SCHEMA IF NOT EXISTS DSOA_TEST_DB.SCHEMA_V1;
DROP SCHEMA IF EXISTS DSOA_TEST_DB.SCHEMA_V1;

-- ============================================================================
-- 6. Spot-check verification (runs as SYSADMIN)
-- ============================================================================
SHOW TABLES IN SCHEMA DSOA_TEST_DB.DATA_VOLUME;

SELECT 'FACTS_ORDERS'       AS tbl, COUNT(*) AS cnt FROM DSOA_TEST_DB.DATA_VOLUME.FACTS_ORDERS
UNION ALL
SELECT 'FACTS_EVENTS',       COUNT(*) FROM DSOA_TEST_DB.DATA_VOLUME.FACTS_EVENTS
UNION ALL
SELECT 'DIM_CUSTOMERS',      COUNT(*) FROM DSOA_TEST_DB.DATA_VOLUME.DIM_CUSTOMERS
UNION ALL
SELECT 'DIM_PRODUCTS',       COUNT(*) FROM DSOA_TEST_DB.DATA_VOLUME.DIM_PRODUCTS
UNION ALL
SELECT 'ARCHIVE_OLD_ORDERS', COUNT(*) FROM DSOA_TEST_DB.DATA_VOLUME.ARCHIVE_OLD_ORDERS
UNION ALL
SELECT 'DDL_TEST_TABLE_A',   COUNT(*) FROM DSOA_TEST_DB.DATA_VOLUME.DDL_TEST_TABLE_A;

-- ============================================================================
-- CLEANUP (run only when done testing):
--   USE ROLE SYSADMIN;
--   DROP SCHEMA IF EXISTS DSOA_TEST_DB.DATA_VOLUME;
--   -- Drop the shared warehouse only if no other test schemas are active:
--   -- DROP WAREHOUSE IF EXISTS DSOA_TEST_WH;
-- ============================================================================

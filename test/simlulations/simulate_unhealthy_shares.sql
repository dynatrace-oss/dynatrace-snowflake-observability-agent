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
-- =============================================================================
-- SIMULATE UNHEALTHY INBOUND SHARES
-- Purpose : Exercise the two dashboard tiles that are empty under normal
--           conditions:
--             • "UNAVAILABLE Inbound Shares"    (tile 11)
--             • "Shares with Deleted Database"  (tile 14)
--
-- Accounts : PUBLISHER  = WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW  (creates shares)
--            CONSUMER   = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW     (mounts shares, runs DSOA)
--
-- How each condition is detected by DSOA
-- ---------------------------------------
-- Scenario A — UNAVAILABLE (tile 11)
--   P_LIST_INBOUND_TABLES queries <DB>.INFORMATION_SCHEMA.TABLES for the mounted
--   shared database.  If the publisher has revoked access the query raises
--   "Shared database is no longer available".  The exception handler writes
--   DETAILS:"SHARE_STATUS" = 'UNAVAILABLE' into TMP_INBOUND_SHARES, which
--   V_INBOUND_SHARE_TABLES surfaces as snowflake.share.status = 'UNAVAILABLE'.
--   Effect is IMMEDIATE — no latency after the revoke.
--
-- Scenario B — Deleted database (tile 14)
--   P_GET_SHARES checks SNOWFLAKE.ACCOUNT_USAGE.DATABASES on the CONSUMER side
--   for each mounted inbound DB:
--     SELECT count(*) > 0 ... WHERE DATABASE_NAME = :db_name AND DELETED IS NULL
--   If the count is 0 (i.e. the consumer-side DB is deleted or never existed),
--   it writes DETAILS:"HAS_DB_DELETED" = TRUE.
--
--   IMPORTANT CONSTRAINT: Snowflake will NOT let you drop a database that is
--   still backing an active share.  You MUST drop the share first, then the
--   database.  Once the share is dropped the consumer-side mounted database is
--   automatically removed, and ACCOUNT_USAGE.DATABASES will eventually reflect
--   DELETED IS NOT NULL — but with up to 3 HOURS of latency.
--
--   Because of this latency window, the real end-to-end path is hard to observe
--   interactively.  Use the DIRECT INJECTION shortcut in Step 4B instead to
--   test the dashboard tile immediately without waiting for ACCOUNT_USAGE.
--
-- Run order
-- ---------
--   Step 1  (PUBLISHER)  : Create the simulation objects.
--   Step 2  (CONSUMER)   : Mount the shares / grant privileges.
--   Step 3A (PUBLISHER)  : Trigger Scenario A — revoke access.
--   Step 3B (PUBLISHER)  : Trigger Scenario B — drop share then database.
--   Step 4A (CONSUMER)   : Verify Scenario A via P_GET_SHARES + full agent run.
--   Step 4B (CONSUMER)   : Verify Scenario B via direct injection shortcut.
--   CLEANUP (both)       : Tear down all simulation objects.
-- =============================================================================


-- =============================================================================
-- STEP 1  ·  PUBLISHER account: WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW
--            Run this block on the PUBLISHER account first.
-- =============================================================================

use role ACCOUNTADMIN;

-- ── Scenario A: share we will later REVOKE ────────────────────────────────────
create database if not exists DSOA_SIM_UNAVAILABLE_DB;
create schema if not exists DSOA_SIM_UNAVAILABLE_DB.SIM;

create or replace table DSOA_SIM_UNAVAILABLE_DB.SIM.SAMPLE_DATA (id int, val text);
insert into DSOA_SIM_UNAVAILABLE_DB.SIM.SAMPLE_DATA values (1, 'hello'), (2, 'world');

create or replace secure view DSOA_SIM_UNAVAILABLE_DB.SIM.V_SAMPLE_DATA as
    select * from DSOA_SIM_UNAVAILABLE_DB.SIM.SAMPLE_DATA;

create share if not exists DSOA_SIM_UNAVAILABLE_SHARE;
grant usage on database DSOA_SIM_UNAVAILABLE_DB to share DSOA_SIM_UNAVAILABLE_SHARE;
grant usage on schema DSOA_SIM_UNAVAILABLE_DB.SIM to share DSOA_SIM_UNAVAILABLE_SHARE;
grant select on view DSOA_SIM_UNAVAILABLE_DB.SIM.V_SAMPLE_DATA to share DSOA_SIM_UNAVAILABLE_SHARE;
alter share DSOA_SIM_UNAVAILABLE_SHARE add accounts = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW;

-- Verify: consumer account should appear
show grants to share DSOA_SIM_UNAVAILABLE_SHARE;

-- ── Scenario B: share we will later DROP entirely ─────────────────────────────
create database if not exists DSOA_SIM_DELETED_DB_DB;
create schema if not exists DSOA_SIM_DELETED_DB_DB.SIM;

create or replace table DSOA_SIM_DELETED_DB_DB.SIM.EVENTS (id int, event text);
insert into DSOA_SIM_DELETED_DB_DB.SIM.EVENTS values (1, 'tick');

create or replace secure view DSOA_SIM_DELETED_DB_DB.SIM.V_EVENTS as
    select * from DSOA_SIM_DELETED_DB_DB.SIM.EVENTS;

create share if not exists DSOA_SIM_DELETED_DB_SHARE;
grant usage on database DSOA_SIM_DELETED_DB_DB to share DSOA_SIM_DELETED_DB_SHARE;
grant usage on schema DSOA_SIM_DELETED_DB_DB.SIM to share DSOA_SIM_DELETED_DB_SHARE;
grant select on view DSOA_SIM_DELETED_DB_DB.SIM.V_EVENTS to share DSOA_SIM_DELETED_DB_SHARE;
alter share DSOA_SIM_DELETED_DB_SHARE add accounts = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW;

-- Verify: consumer account should appear
show grants to share DSOA_SIM_DELETED_DB_SHARE;


-- =============================================================================
-- STEP 2  ·  CONSUMER account: WMBJBCQ.DYNATRACEDIGITALBUSINESSDW
--            Run AFTER Step 1.
-- =============================================================================

use role ACCOUNTADMIN;

-- Mount both inbound shares as local databases
create database if not exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB
    from share WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW.DSOA_SIM_UNAVAILABLE_SHARE;

create database if not exists DSOA_SIM_DELETED_DB_CONSUMER_DB
    from share WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW.DSOA_SIM_DELETED_DB_SHARE;

-- Grant imported privileges so DTAGENT_QA_OWNER can query the shared schemas.
-- (P_LIST_INBOUND_TABLES calls P_GRANT_IMPORTED_PRIVILEGES automatically on first
--  failure, but doing it explicitly avoids the first-attempt exception path.)
grant imported privileges on database DSOA_SIM_UNAVAILABLE_CONSUMER_DB to role DTAGENT_QA_OWNER;
grant imported privileges on database DSOA_SIM_DELETED_DB_CONSUMER_DB  to role DTAGENT_QA_OWNER;

-- Verify both shares appear as INBOUND
show shares;


-- =============================================================================
-- STEP 3A  ·  PUBLISHER account — Scenario A: REVOKE consumer access
--             Immediate effect; no latency.
-- =============================================================================

use role ACCOUNTADMIN;

alter share DSOA_SIM_UNAVAILABLE_SHARE
    remove accounts = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW;

-- The consumer DB (DSOA_SIM_UNAVAILABLE_CONSUMER_DB) still appears in SHOW SHARES
-- on the consumer side, but querying it now raises:
--   "Shared database is no longer available"
-- P_LIST_INBOUND_TABLES catches this and writes SHARE_STATUS = 'UNAVAILABLE'.


-- =============================================================================
-- STEP 3B  ·  PUBLISHER account — Scenario B: DROP share then database
--
--             NOTE: Snowflake does NOT allow dropping a database that is still
--             backing an active share — you will get:
--               "Database '...' cannot be dropped. It is still shared by N shares"
--             You MUST drop the share first, THEN the database.
-- =============================================================================

use role ACCOUNTADMIN;

-- 1. Remove the share (frees the database from the sharing constraint)
drop share if exists DSOA_SIM_DELETED_DB_SHARE;

-- 2. Now the database can be dropped
drop database if exists DSOA_SIM_DELETED_DB_DB;

-- After this:
--   • The consumer-side DSOA_SIM_DELETED_DB_CONSUMER_DB is automatically removed.
--   • SNOWFLAKE.ACCOUNT_USAGE.DATABASES on the CONSUMER will eventually show
--     DELETED IS NOT NULL for that database — but with up to 3 HOURS of latency.
--   • P_GET_SHARES checks that view, so HAS_DB_DELETED fires only after the
--     latency window AND while the share still appears in SHOW SHARES on the
--     consumer (which it won't, since you just dropped the share).
--
--   In practice this makes end-to-end testing of tile 14 via real Snowflake
--   mechanics unreliable.  Use the DIRECT INJECTION shortcut in Step 4B instead.


-- =============================================================================
-- STEP 4A  ·  CONSUMER account — verify Scenario A (UNAVAILABLE)
--             Run AFTER Step 3A.
-- =============================================================================

use role DTAGENT_QA_OWNER; use database DTAGENT_QA_DB; use warehouse DTAGENT_QA_WH;

-- Refresh the temp tables — P_GET_SHARES will call P_LIST_INBOUND_TABLES for
-- DSOA_SIM_UNAVAILABLE_CONSUMER_DB, which will fail and write SHARE_STATUS=UNAVAILABLE
call DTAGENT_QA_DB.APP.P_GET_SHARES();

-- Should show: SHARE_STATUS = 'UNAVAILABLE' for DSOA_SIM_UNAVAILABLE_SHARE
select SHARE_NAME, IS_REPORTED,
       DETAILS:"SHARE_STATUS"   as SHARE_STATUS,
       DETAILS:"HAS_DB_DELETED" as HAS_DB_DELETED,
       DETAILS:"ERROR_MESSAGE"  as ERROR_MESSAGE
from DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES
where SHARE_NAME like 'DSOA_SIM_%'
order by SHARE_NAME;

-- Emit telemetry to Dynatrace and check tile 11 in the dashboard
call DTAGENT_QA_DB.APP.DTAGENT_RUN();


-- =============================================================================
-- STEP 4B  ·  CONSUMER account — verify Scenario B (Deleted Database)
--             DIRECT INJECTION shortcut — bypasses the 3-hour ACCOUNT_USAGE
--             latency and the SHOW SHARES window problem entirely.
--             Run AFTER Step 3B (or independently at any time for UI testing).
-- =============================================================================

use role DTAGENT_QA_OWNER; use database DTAGENT_QA_DB; use warehouse DTAGENT_QA_WH;

-- Inject a fake share row into TMP_SHARES so V_INBOUND_SHARE_TABLES picks it up
truncate table if exists DTAGENT_QA_DB.APP.TMP_SHARES;
insert into DTAGENT_QA_DB.APP.TMP_SHARES
    (created_on, kind, owner_account, name, database_name, given_to, owner, comment, listing_global_name, secure_objects_only)
values
    (current_timestamp(), 'INBOUND', 'WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW',
     'DSOA_SIM_DELETED_DB_SHARE', 'DSOA_SIM_DELETED_DB_CONSUMER_DB',
     null, null, 'Simulation: share whose backing database was deleted', null, null);

-- Inject the matching TMP_INBOUND_SHARES row with HAS_DB_DELETED = TRUE
truncate table if exists DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES;
insert into DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES (SHARE_NAME, IS_REPORTED, DETAILS)
values ('DSOA_SIM_DELETED_DB_SHARE', TRUE,
        OBJECT_CONSTRUCT('HAS_DB_DELETED', TRUE,
                         'DATABASE_NAME', 'DSOA_SIM_DELETED_DB_CONSUMER_DB'));

-- Verify V_INBOUND_SHARE_TABLES surfaces it correctly
-- (should show snowflake.share.has_db_deleted = true in ATTRIBUTES)
select _MESSAGE, DIMENSIONS, ATTRIBUTES
from DTAGENT_QA_DB.APP.V_INBOUND_SHARE_TABLES
where DIMENSIONS:"snowflake.share.name" = 'DSOA_SIM_DELETED_DB_SHARE';

-- Emit telemetry to Dynatrace and check tile 14 in the dashboard
call DTAGENT_QA_DB.APP.DTAGENT_RUN();


-- =============================================================================
-- CLEANUP  ·  Run on BOTH accounts when simulation is done
-- =============================================================================

-- ── On PUBLISHER account (WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW) ──────────────
use role ACCOUNTADMIN;

drop share if exists DSOA_SIM_UNAVAILABLE_SHARE;
drop share if exists DSOA_SIM_DELETED_DB_SHARE;    -- already gone after Step 3B
drop database if exists DSOA_SIM_UNAVAILABLE_DB;
drop database if exists DSOA_SIM_DELETED_DB_DB;    -- already gone after Step 3B

-- ── On CONSUMER account (WMBJBCQ.DYNATRACEDIGITALBUSINESSDW) ──────────────────
use role ACCOUNTADMIN;

drop database if exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB;
drop database if exists DSOA_SIM_DELETED_DB_CONSUMER_DB;  -- likely already gone

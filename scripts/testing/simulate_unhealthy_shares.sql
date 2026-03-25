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
-- Purpose : Exercise the two empty dashboard tiles:
--             • "UNAVAILABLE Inbound Shares"
--             • "Shares with Deleted Database"
--
-- Accounts : PUBLISHER  = WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW  (creates shares)
--            CONSUMER   = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW     (mounts shares, runs DSOA)
--
-- Overview
-- --------
-- Scenario A — UNAVAILABLE share
--   The CONSUMER account mounts a share that the PUBLISHER later REVOKES.
--   When P_LIST_INBOUND_TABLES tries to query the shared DB it receives
--   "Shared database is no longer available" and writes SHARE_STATUS=UNAVAILABLE.
--
-- Scenario B — Deleted database
--   The PUBLISHER drops the DATABASE that backs the share (which implicitly
--   drops the share too).  SHOW SHARES on the CONSUMER side still lists the
--   share for a short window, but SNOWFLAKE.ACCOUNT_USAGE.DATABASES shows
--   DELETED IS NOT NULL.  P_GET_SHARES detects this and writes HAS_DB_DELETED=TRUE.
--   NOTE: ACCOUNT_USAGE has up to 3 h latency; allow time before triggering agent.
--
-- Run order
-- ---------
--   Step 1  (PUBLISHER)  : Create the simulation objects.
--   Step 2  (CONSUMER)   : Mount the shares / grant privileges.
--   Step 3  (PUBLISHER)  : Trigger the unhealthy condition (revoke or drop DB).
--   Step 4  (CONSUMER)   : Trigger the DSOA agent and observe dashboard tiles.
--   Step 5  (both)       : Tear down — run the CLEANUP section at the bottom.
-- =============================================================================


-- =============================================================================
-- STEP 1  ·  PUBLISHER account: WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW
--            Run this block on the PUBLISHER account first.
-- =============================================================================

use role ACCOUNTADMIN;

-- ── Scenario A setup: share backed by a real database ─────────────────────────
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

-- Verify: should show the consumer account in the GRANTS list
show grants to share DSOA_SIM_UNAVAILABLE_SHARE;

-- ── Scenario B setup: share backed by a database we will later DROP ────────────
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

-- Verify: should show the consumer account
show grants to share DSOA_SIM_DELETED_DB_SHARE;


-- =============================================================================
-- STEP 2  ·  CONSUMER account: WMBJBCQ.DYNATRACEDIGITALBUSINESSDW
--            Run this block on the CONSUMER account after Step 1 completes.
-- =============================================================================

use role ACCOUNTADMIN;

-- Mount the inbound shares as local databases
create database if not exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB
    from share WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW.DSOA_SIM_UNAVAILABLE_SHARE;

create database if not exists DSOA_SIM_DELETED_DB_CONSUMER_DB
    from share WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW.DSOA_SIM_DELETED_DB_SHARE;

-- Grant imported privileges so DTAGENT_OWNER can query the shared schemas.
-- (P_LIST_INBOUND_TABLES calls P_GRANT_IMPORTED_PRIVILEGES automatically,
--  but doing it explicitly here avoids the first-attempt failure path.)
grant imported privileges on database DSOA_SIM_UNAVAILABLE_CONSUMER_DB to role DTAGENT_QA_OWNER;
grant imported privileges on database DSOA_SIM_DELETED_DB_CONSUMER_DB  to role DTAGENT_QA_OWNER;

-- Verify both shares appear in SHOW SHARES
show shares;


-- =============================================================================
-- STEP 3A  ·  PUBLISHER account — trigger Scenario A: REVOKE access (UNAVAILABLE)
--             Run AFTER Step 2.  The CONSUMER's shared DB becomes inaccessible
--             immediately; no latency.
-- =============================================================================

use role ACCOUNTADMIN;

alter share DSOA_SIM_UNAVAILABLE_SHARE
    remove accounts = WMBJBCQ.DYNATRACEDIGITALBUSINESSDW;

-- After this the CONSUMER's DSOA_SIM_UNAVAILABLE_CONSUMER_DB still exists in
-- SHOW SHARES on the consumer side, but querying it returns
-- "Shared database is no longer available".
-- P_LIST_INBOUND_TABLES catches this and writes SHARE_STATUS = 'UNAVAILABLE'.


-- =============================================================================
-- STEP 3B  ·  PUBLISHER account — trigger Scenario B: DROP the database (Deleted DB)
--             Run AFTER Step 2.  ACCOUNT_USAGE.DATABASES latency is up to 3 hours;
--             plan accordingly before expecting the dashboard tile to populate.
-- =============================================================================

use role ACCOUNTADMIN;

-- Dropping the database implicitly drops the share backing it.
drop database if exists DSOA_SIM_DELETED_DB_DB;

-- CONSUMER-side: SHOW SHARES may still list DSOA_SIM_DELETED_DB_SHARE for a
-- short window.  P_GET_SHARES checks ACCOUNT_USAGE.DATABASES for DELETED IS NOT NULL
-- and writes HAS_DB_DELETED = TRUE when it detects the deletion.
-- Tile "Shares with Deleted Database" will appear once the agent next runs
-- (after ACCOUNT_USAGE catches up, usually within 3 h).


-- =============================================================================
-- STEP 4  ·  CONSUMER account — trigger the DSOA agent manually
--            Run on the CONSUMER account after Steps 3A / 3B.
-- =============================================================================

use role DTAGENT_QA_OWNER; use database DTAGENT_QA_DB; use warehouse DTAGENT_QA_WH;

-- Trigger a single agent run so telemetry is emitted immediately
call DTAGENT_QA_DB.APP.P_GET_SHARES();

-- Verify the temp tables reflect the simulated conditions:
--   DSOA_SIM_UNAVAILABLE_SHARE  → DETAILS:"SHARE_STATUS" = 'UNAVAILABLE'
--   DSOA_SIM_DELETED_DB_SHARE   → DETAILS:"HAS_DB_DELETED" = TRUE  (only after ACU latency)
select SHARE_NAME, IS_REPORTED,
       DETAILS:"SHARE_STATUS"   as SHARE_STATUS,
       DETAILS:"HAS_DB_DELETED" as HAS_DB_DELETED,
       DETAILS:"ERROR_MESSAGE"  as ERROR_MESSAGE
from DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES
where SHARE_NAME like 'DSOA_SIM_%'
order by SHARE_NAME;

-- Then trigger the full agent to emit telemetry to Dynatrace:
-- call DTAGENT_QA_DB.APP.DTAGENT_RUN();

-- Open the dashboard and check:
--   • "UNAVAILABLE Inbound Shares"   — should show DSOA_SIM_UNAVAILABLE_SHARE
--   • "Shares with Deleted Database" — should show DSOA_SIM_DELETED_DB_SHARE
--                                      (allow up to 3 h for ACCOUNT_USAGE latency)


-- =============================================================================
-- CLEANUP  ·  Run on BOTH accounts when simulation is done
-- =============================================================================

-- ── On PUBLISHER account (WMBJBCQ.DEVDYNATRACEDIGITALBUSINESSDW) ──────────────
use role ACCOUNTADMIN;

drop share if exists DSOA_SIM_UNAVAILABLE_SHARE;
drop share if exists DSOA_SIM_DELETED_DB_SHARE;
drop database if exists DSOA_SIM_UNAVAILABLE_DB;
drop database if exists DSOA_SIM_DELETED_DB_DB;   -- may already be gone from Step 3B

-- ── On CONSUMER account (WMBJBCQ.DYNATRACEDIGITALBUSINESSDW) ──────────────────
use role ACCOUNTADMIN;

drop database if exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB;
drop database if exists DSOA_SIM_DELETED_DB_CONSUMER_DB;

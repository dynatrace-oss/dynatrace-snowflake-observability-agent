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
--             • "UNAVAILABLE Inbound Shares"  (tile 11)
--             • "Shares No Longer Observed"   (tile 14)
--
-- Accounts : PUBLISHER  = <org>.<publisher-account>   (creates shares)
--            CONSUMER   = <org>.<consumer-account>    (mounts shares, runs DSOA)
--
-- Before running, set the two variables at the top of each step block:
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
-- Scenario B — Share no longer observed (tile 14)
--   Tile 14 uses a DQL log-history approach on the Dynatrace side:
--     • Query all distinct (account, share_name, context) tuples seen in the
--       last 7 days of logs.
--     • Filter to those NOT seen in the past 2 hours.
--     • These are shares that "disappeared" from SHOW SHARES between runs.
--
--   This naturally catches revoked inbound shares, dropped outbound shares,
--   and accounts where the agent went offline — all without relying on
--   SNOWFLAKE.ACCOUNT_USAGE.DATABASES latency or SHOW SHARES edge cases.
--
--   To trigger Scenario B: let DSOA collect a share for at least one run,
--   then drop the share from the publisher side.  The share disappears from
--   SHOW SHARES on the consumer immediately; after 2+ hours without a new log
--   for that share, tile 14 will show it.
--
--   For faster testing, use the WAIT shortcut in Step 4B: inject a fake share
--   log record with a timestamp older than 2 hours (use TO_TIMESTAMP with a
--   historic time), then run a fresh agent cycle.  The share will appear in
--   the 7d window but not in the last 2h.
--
-- Run order
-- ---------
--   Step 1  (PUBLISHER)  : Create the simulation objects.
--   Step 2  (CONSUMER)   : Mount the shares / grant privileges.
--   Step 3A (PUBLISHER)  : Trigger Scenario A — revoke access.
--   Step 3B (PUBLISHER)  : Trigger Scenario B — drop share then wait.
--   Step 4A (CONSUMER)   : Verify Scenario A via P_GET_SHARES + full agent run.
--   Step 4B              : Verify Scenario B — tile 14 shows the dropped share
--                          after 2+ hours of inactivity (or use DQL fast-track).
--   CLEANUP (both)       : Tear down all simulation objects.
-- =============================================================================


-- =============================================================================
-- STEP 1  ·  PUBLISHER account
--            Run this block on the PUBLISHER account first.
--            Set CONSUMER_ACCOUNT to the full account locator of the consumer.
-- =============================================================================

-- !! Replace with your consumer account locator (e.g., ORG.MY_ACCOUNT) !!
set consumer_account = '<org>.<consumer-account>';

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
alter share DSOA_SIM_UNAVAILABLE_SHARE add accounts = ($consumer_account);

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
alter share DSOA_SIM_DELETED_DB_SHARE add accounts = ($consumer_account);

-- Verify: consumer account should appear
show grants to share DSOA_SIM_DELETED_DB_SHARE;


-- =============================================================================
-- STEP 2  ·  CONSUMER account
--            Run AFTER Step 1.
--            Set PUBLISHER_ACCOUNT to the full account locator of the publisher.
-- =============================================================================

-- !! Replace with your publisher account locator (e.g., ORG.MY_PUBLISHER) !!
set publisher_account = '<org>.<publisher-account>';

use role ACCOUNTADMIN;

-- Mount both inbound shares as local databases
create database if not exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB
    from share identifier($publisher_account || '.DSOA_SIM_UNAVAILABLE_SHARE');

create database if not exists DSOA_SIM_DELETED_DB_CONSUMER_DB
    from share identifier($publisher_account || '.DSOA_SIM_DELETED_DB_SHARE');

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

-- !! Re-set the consumer account variable if running this in a fresh session !!
-- set consumer_account = '<org>.<consumer-account>';
use role ACCOUNTADMIN;

alter share DSOA_SIM_UNAVAILABLE_SHARE
    remove accounts = ($consumer_account);

-- The consumer DB (DSOA_SIM_UNAVAILABLE_CONSUMER_DB) still appears in SHOW SHARES
-- on the consumer side, but querying it now raises:
--   "Shared database is no longer available"
-- P_LIST_INBOUND_TABLES catches this and writes SHARE_STATUS = 'UNAVAILABLE'.


-- =============================================================================
-- STEP 3B  ·  PUBLISHER account — Scenario B: DROP share
--
--             Drop the share so the consumer can no longer observe it.
--             Tile 14 will show this share once it has been absent from DSOA
--             logs for more than 2 hours (the recency window).
--
--             NOTE: If the consumer mounted the share as a database, Snowflake
--             may prevent dropping the database while the share still has
--             account grants.  Drop the share first, then the database.
-- =============================================================================

use role ACCOUNTADMIN;

-- 1. Remove the share (consumer-side mounted DB is automatically removed)
drop share if exists DSOA_SIM_DELETED_DB_SHARE;

-- 2. Now the publisher database can optionally be dropped too
drop database if exists DSOA_SIM_DELETED_DB_DB;

-- After this:
--   • The share disappears from SHOW SHARES on the consumer immediately.
--   • DSOA will stop emitting log rows for DSOA_SIM_DELETED_DB_SHARE.
--   • After 2+ hours without a new log, tile 14 will surface this share.
--
-- For faster validation, see Step 4B below.


-- =============================================================================
-- STEP 4A  ·  CONSUMER account — verify Scenario A (UNAVAILABLE, tile 11)
--             Run AFTER Step 3A.
-- =============================================================================

use role DTAGENT_QA_OWNER; use database DTAGENT_QA_DB; use warehouse DTAGENT_QA_WH;

-- Refresh: P_GET_SHARES calls P_LIST_INBOUND_TABLES for each inbound share.
-- For DSOA_SIM_UNAVAILABLE_CONSUMER_DB the query now raises
-- "Shared database is no longer available" → SHARE_STATUS = 'UNAVAILABLE' written.
call DTAGENT_QA_DB.APP.P_GET_SHARES();

-- Verify the UNAVAILABLE row is present
select SHARE_NAME, IS_REPORTED,
       DETAILS:"SHARE_STATUS"   as SHARE_STATUS,
       DETAILS:"ERROR_MESSAGE"  as ERROR_MESSAGE
from DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES
where SHARE_NAME like 'DSOA_SIM_%'
order by SHARE_NAME;

-- Emit telemetry and check tile 11 in the dashboard
call DTAGENT_QA_DB.APP.DTAGENT(['shares']);

-- ── Direct injection shortcut (no publisher account required) ─────────────────
-- NOTE: Use INSERT ... SELECT, NOT INSERT ... VALUES, because DETAILS is OBJECT
-- type and Snowflake rejects OBJECT_CONSTRUCT() inside a VALUES clause.
--
-- truncate table if exists DTAGENT_QA_DB.APP.TMP_SHARES;
-- insert into DTAGENT_QA_DB.APP.TMP_SHARES
--     (created_on, kind, owner_account, name, database_name, given_to, owner, comment, listing_global_name, secure_objects_only)
-- values (current_timestamp(), 'INBOUND', '<org>.<publisher-account>',
--         'DSOA_SIM_UNAVAILABLE_SHARE', 'DSOA_SIM_UNAVAILABLE_CONSUMER_DB',
--         null, null, 'Simulation: revoked share', null, null);
--
-- truncate table if exists DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES;
-- insert into DTAGENT_QA_DB.APP.TMP_INBOUND_SHARES (SHARE_NAME, IS_REPORTED, DETAILS)
-- select 'DSOA_SIM_UNAVAILABLE_SHARE', TRUE,
--        OBJECT_CONSTRUCT('SHARE_STATUS', 'UNAVAILABLE',
--                         'ERROR_MESSAGE', 'Shared database is no longer available');
-- call DTAGENT_QA_DB.APP.DTAGENT(['shares']);


-- =============================================================================
-- STEP 4B  ·  Verify Scenario B — "Shares No Longer Observed" (tile 14)
--
--             Tile 14 uses a DQL-only approach: shares seen in the 7-day log
--             history but absent from the last-2-hour window are surfaced.
--             No Snowflake-side procedure calls are needed.
--
--             FAST-TRACK (no 2-hour wait):
--             After Step 3B + one DSOA run, validate using this scratch DQL
--             in the Dynatrace console — narrow the recency window to confirm:
--
--               fetch logs, from: now()-7d
--               | filter db.system == "snowflake"
--               | filter dsoa.run.context == "inbound_shares"
--               | summarize
--                   firstSeen    = min(timestamp),
--                   lastSeen     = max(timestamp),
--                   seenRecently = countIf(timestamp >= now()-2h) > 0,
--                   by: {deployment.environment, dsoa.run.context, snowflake.share.name, db.namespace}
--               | filter seenRecently == false
--               | sort lastSeen desc
--
--             Adjust now()-2h to now()-30m (or shorter) to see the share before
--             the full 2-hour gap has elapsed.
--             Expected: DSOA_SIM_DELETED_DB_SHARE appears with lastSeen from
--             the run just before the share was dropped.
-- =============================================================================


-- =============================================================================
-- CLEANUP  ·  Run on BOTH accounts when simulation is done
-- =============================================================================

-- ── On PUBLISHER account ──────────────────────────────────────────────────────
use role ACCOUNTADMIN;

drop share if exists DSOA_SIM_UNAVAILABLE_SHARE;
drop share if exists DSOA_SIM_DELETED_DB_SHARE;    -- already gone after Step 3B
drop database if exists DSOA_SIM_UNAVAILABLE_DB;
drop database if exists DSOA_SIM_DELETED_DB_DB;    -- already gone after Step 3B

-- ── On CONSUMER account ───────────────────────────────────────────────────────
use role ACCOUNTADMIN;

drop database if exists DSOA_SIM_UNAVAILABLE_CONSUMER_DB;
-- DSOA_SIM_DELETED_DB_CONSUMER_DB was auto-dropped by Snowflake when the share
-- was removed in Step 3B, so no explicit drop is needed here.

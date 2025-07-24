--
--
-- These materials contain confidential information and
-- trade secrets of Dynatrace LLC.  You shall
-- maintain the materials as confidential and shall not
-- disclose its contents to any third party except as may
-- be required by law or regulation.  Use, disclosure,
-- or reproduction is prohibited without the prior express
-- written permission of Dynatrace LLC.
-- 
-- All Compuware products listed within the materials are
-- trademarks of Dynatrace LLC.  All other company
-- or product names are trademarks of their respective owners.
-- 
-- Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
--
--
--
-- This schema is intended for keeping only state, logs, etc of DT Agent.
-- Do not store configuration or any other data here.
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create schema if not exists STATUS;
grant usage on schema STATUS to role DTAGENT_VIEWER;

-- Log of for keeping track of processing various types of measurements
-- This way we can keep track when each type of measurements (like query_history, log_events, ...) took place (PROCESS_TIME), 
-- and until which moment the measurements were collected and sent to DT
-- for query_history this is purely informational (as detailed information is in PROCESSED_QUERIES_* tables)
-- but for other, like log_events, this will give last timestamp or last entry id that was processed and sent.

create table if not exists DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG (
    PROCESS_TIME        timestamp_ltz not null default current_timestamp,
    MEASUREMENTS_SOURCE text not null,
    LAST_TIMESTAMP      timestamp_ltz,
    LAST_ID             text,
    ENTRIES_COUNT       variant -- this is to replace PROCESSED_QUERIES_LOG
);

-- grants to the DTAGENT_VIEWER

grant select, insert, update, delete on table STATUS.PROCESSED_MEASUREMENTS_LOG to role DTAGENT_VIEWER;

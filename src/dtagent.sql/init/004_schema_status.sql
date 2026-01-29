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
--
-- This schema is intended for keeping only state, logs, etc of DT Agent.
-- Do not store configuration or any other data here.
--
use role ACCOUNTADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create schema if not exists STATUS;
grant ownership on schema STATUS to role DTAGENT_OWNER revoke current grants;
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

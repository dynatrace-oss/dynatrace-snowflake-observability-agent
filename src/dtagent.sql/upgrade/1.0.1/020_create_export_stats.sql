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
-- v1.0.1 Upgrade
-- Creates STATUS.EXPORT_STATS: per plugin run and signal (logs, spans, metrics, events, davis_events, biz_events) the number of
-- records the agent attempted to send to Dynatrace and the number that Dynatrace accepted.
-- Written by the agent after each run and reported by the heartbeat plugin.
-- Idempotent: safe to run against deployments that already have the table.
--
use role DTAGENT_OWNER; use database DTAGENT_DB;

create table if not exists DTAGENT_DB.STATUS.EXPORT_STATS (
    RUN_TS      timestamp_ltz not null default current_timestamp,
    RUN_ID      text,
    PLUGIN      text not null,
    SIGNAL      text not null,
    ATTEMPTED   number not null default 0,
    DELIVERED   number not null default 0
);

grant select, insert, update, delete on table STATUS.EXPORT_STATS to role DTAGENT_VIEWER;

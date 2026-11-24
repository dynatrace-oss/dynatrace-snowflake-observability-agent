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
--  Reports how many records the agent attempted to send to Dynatrace and how many Dynatrace accepted, per plugin and signal
--  (logs, spans, metrics, events, davis_events, biz_events), over the heartbeat window (plugins.heartbeat.window_hours).
--  Source: STATUS.EXPORT_STATS, which the agent fills after every run.
--  Attempted and delivered are read from the same rows, so delivered / attempted is an accurate success rate.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()
returns table (
    TIMESTAMP   timestamp_ltz,
    _MESSAGE    varchar,
    DIMENSIONS  object,
    ATTRIBUTES  object,
    METRICS     object
)
language sql
execute as caller
as
$$
declare
    WINDOW_HOURS    int;
    res             resultset;
begin
    WINDOW_HOURS := (select DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.heartbeat.window_hours', 24)::int);

    res := (
        select
            current_timestamp()                                                                 as TIMESTAMP,
            concat('Export statistics for ', s.PLUGIN, ' / ', s.SIGNAL, ': delivered ', sum(s.DELIVERED), ' of ', sum(s.ATTEMPTED),
                   ' attempted records in last ', :WINDOW_HOURS, 'h')                           as _MESSAGE,
            OBJECT_CONSTRUCT(
                'db.namespace',                         upper('DTAGENT_DB'),
                'dsoa.export.plugin',                   s.PLUGIN,
                'dsoa.export.signal',                   s.SIGNAL
            )                                                                                   as DIMENSIONS,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.window_hours',          :WINDOW_HOURS
            )                                                                                   as ATTRIBUTES,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.export.attempted',      sum(s.ATTEMPTED),
                'dsoa.heartbeat.export.delivered',      sum(s.DELIVERED)
            )                                                                                   as METRICS
        from DTAGENT_DB.STATUS.EXPORT_STATS s
        where s.RUN_TS >= dateadd(hour, -1 * :WINDOW_HOURS, current_timestamp())
        group by s.PLUGIN, s.SIGNAL
        order by s.PLUGIN, s.SIGNAL
    );

    return table(res);
exception
    when statement_error then
        -- do not return an empty table: that would look like a successful heartbeat with nothing to report
        SYSTEM$LOG_ERROR(SQLERRM);
        raise;
end;
$$
;

grant usage on procedure DTAGENT_DB.APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED() to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
call DTAGENT_DB.APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED();
*/

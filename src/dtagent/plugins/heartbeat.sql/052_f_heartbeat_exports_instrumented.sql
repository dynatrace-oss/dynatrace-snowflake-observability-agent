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
--  (logs, spans, metrics, events, davis_events, biz_events), for all rows of STATUS.EXPORT_STATS not reported yet.
--  The agent fills the table after every run; HeartbeatPlugin marks the rows it reported (REPORTED_TS) once they were delivered,
--  so a heartbeat that did not run or could not deliver is followed by one that reports the missed interval as well.
--  Attempted and delivered are read from the same rows, so delivered / attempted is an accurate success rate.
--  Every row carries dsoa.heartbeat.export.reported_until, the cut-off HeartbeatPlugin marks as reported.
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
    CUTOFF          timestamp_ltz;
    res             resultset;
begin
    -- rows of the last minute are left for the next heartbeat: an insert that is not visible yet must not be marked as reported
    CUTOFF := dateadd(minute, -1, current_timestamp());

    res := (
        with cte_stats as (
            select
                s.PLUGIN                                                                        as PLUGIN,
                s.SIGNAL                                                                        as SIGNAL,
                sum(s.ATTEMPTED)                                                                as ATTEMPTED,
                sum(s.DELIVERED)                                                                as DELIVERED,
                -- ISO 8601 with nanoseconds and offset: HeartbeatPlugin hands the cut-off back to Snowflake as it is, without losing precision
                to_varchar(min(s.RUN_TS), 'YYYY-MM-DD"T"HH24:MI:SS.FF9TZH:TZM')                 as REPORTED_FROM,
                to_varchar(:CUTOFF, 'YYYY-MM-DD"T"HH24:MI:SS.FF9TZH:TZM')                       as REPORTED_UNTIL
            from DTAGENT_DB.STATUS.EXPORT_STATS s
            where s.REPORTED_TS is null and s.RUN_TS <= :CUTOFF
            group by s.PLUGIN, s.SIGNAL
        )
        select
            current_timestamp()                                                                 as TIMESTAMP,
            concat('Export statistics for ', c.PLUGIN, ' / ', c.SIGNAL, ': delivered ', c.DELIVERED, ' of ', c.ATTEMPTED,
                   ' attempted records since ', c.REPORTED_FROM)                                as _MESSAGE,
            OBJECT_CONSTRUCT(
                'db.namespace',                         upper('DTAGENT_DB'),
                'dsoa.export.plugin',                   c.PLUGIN,
                'dsoa.export.signal',                   c.SIGNAL
            )                                                                                   as DIMENSIONS,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.export.reported_from',  c.REPORTED_FROM,
                'dsoa.heartbeat.export.reported_until', c.REPORTED_UNTIL
            )                                                                                   as ATTRIBUTES,
            OBJECT_CONSTRUCT(
                'dsoa.heartbeat.export.attempted',      c.ATTEMPTED,
                'dsoa.heartbeat.export.delivered',      c.DELIVERED
            )                                                                                   as METRICS
        from cte_stats c
        order by c.PLUGIN, c.SIGNAL
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

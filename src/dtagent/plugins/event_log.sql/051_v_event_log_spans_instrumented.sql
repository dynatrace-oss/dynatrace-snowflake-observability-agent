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
-- APP.V_EVENT_LOG_SPANS_INSTRUMENTED() is a shorthand to retrieve spans/traces from event log filtered by only new, non OTEL logs
-- https://docs.snowflake.com/en/developer-guide/logging-tracing/tracing-accessing-events
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_EVENT_LOG_SPANS_INSTRUMENTED
as
with cte_event_log as (
    select *
    from DTAGENT_DB.STATUS.EVENT_LOG l
    where RECORD_TYPE = 'SPAN'
      and (
      -- we log everything for all non-DTAGENT DBs
          nvl(l.resource_attributes['snow.database.name']::varchar, '') not like 'DTAGENT%_DB'
      -- only report metrics for DBs that are related to this particular dtagent,
       or nvl(l.resource_attributes['snow.database.name']::varchar, '') = 'DTAGENT_DB' -- DTAGENT_DB will be replaced with DTAGENT_$TAG_DB during deploy
      )
      and TIMESTAMP > GREATEST( timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('event_log_spans') )
)
, cte_span_events as (
    select
        RESOURCE_ATTRIBUTES:"snow.query.id"::varchar                                             as QUERY_ID,
        RESOURCE_ATTRIBUTES:"snow.session.id"::varchar                                           as SESSION_ID,

        -- name
        RESOURCE_ATTRIBUTES:"snow.executable.name"::varchar                                      as NAME,

        -- start_time, end_time
        extract(epoch_nanosecond from to_timestamp(l.START_TIMESTAMP))                           as START_TIME,
        extract(epoch_nanosecond from to_timestamp(l.TIMESTAMP))                                 as END_TIME,
        -- status code
        -- https://docs.snowflake.com/en/developer-guide/logging-tracing/tracing-accessing-events#view-trace-entries-in-sf-web-interface
        case
            when RECORD:stats:code::varchar = 'STATUS_CODE_ERROR'   then 'ERROR'
            when RECORD:stats:code::varchar = 'STATUS_CODE_UNSET'   then 'UNSET'
            else 'OK'
        end                                                                                      as STATUS_CODE,

    extract(epoch_nanosecond from to_timestamp(l.TIMESTAMP))                                   as TIMESTAMP,

    TRACE:span_id::varchar                                                                     as _SPAN_ID,
    TRACE:trace_id::varchar                                                                    as _TRACE_ID,
    RECORD:parent_span_id::varchar                                                             as _PARENT_SPAN_ID,
    RECORD:kind::varchar                                                                       as _SPAN_KIND,

    _PARENT_SPAN_ID is NULL                                                                    as IS_ROOT,

    RECORD                                                                                     as _RECORD,

    MAP_CAT(
        RESOURCE_ATTRIBUTES::map(varchar,variant),
        OBJECT_CONSTRUCT(
            'db.namespace',                 RESOURCE_ATTRIBUTES:"snow.database.name",
            'snowflake.schema.name',        RESOURCE_ATTRIBUTES:"snow.schema.name",
            'snowflake.role.name',          RESOURCE_ATTRIBUTES:"snow.session.role.primary.name",
            'snowflake.warehouse.name',     RESOURCE_ATTRIBUTES:"snow.warehouse.name",
            'snowflake.query.id',           RESOURCE_ATTRIBUTES:"snow.query.id"
        )::map(varchar,variant)
    )                                                                 as DIMENSIONS,

    from cte_event_log l
    order by TIMESTAMP asc
)
select *
from cte_span_events
where END_TIME is not NULL
;

grant select on table DTAGENT_DB.APP.V_EVENT_LOG_SPANS_INSTRUMENTED to role DTAGENT_VIEWER;

-- example calls
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from APP.V_EVENT_LOG_SPANS_INSTRUMENTED
limit 10;
 */

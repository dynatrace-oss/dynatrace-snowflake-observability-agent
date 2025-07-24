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
-- APP.V_EVENT_LOG_METRICS_INSTRUMENTED() is a shorthand to retrieve metrics from event log filtered by only new, non OTEL logs
-- 
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_EVENT_LOG_METRICS_INSTRUMENTED
as 
with cte_event_log as (
    select *
    from DTAGENT_DB.STATUS.EVENT_LOG l
    where RECORD_TYPE = 'METRIC'
      and (
      -- we log everything for all non-DTAGENT DBs
          nvl(l.resource_attributes['snow.database.name']::varchar, '') not like 'DTAGENT%_DB'
      -- only report metrics for DBs that are related to this particular dtagent,
       or nvl(l.resource_attributes['snow.database.name']::varchar, '') = 'DTAGENT_DB' -- DTAGENT_DB will be replaced with DTAGENT_$TAG_DB during deploy
      )
      and TIMESTAMP > DTAGENT_DB.APP.F_LAST_PROCESSED_TS('event_log_metrics')
)
select 
  extract(epoch_nanosecond from to_timestamp(l.TIMESTAMP))           as TIMESTAMP,

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
  OBJECT_AGG(
      RECORD:metric:name::varchar,
      OBJECT_CONSTRUCT(RECORD:metric_type::varchar,VALUE)
  )                                                                 as METRICS,
  -- "snowflake.acceleration.data.scanned": {
  --   "displayName": "Query Acceleration Bytes Scanned",
  --   "unit": "bytes"
  -- },
  OBJECT_AGG(
        RECORD:metric:name,
        OBJECT_CONSTRUCT(
            'displayName',  concat('Snowflake metric: ', RECORD:metric:name),
            'unit', RECORD:metric:unit
        )
  )                                                                 as _INSTRUMENTS_DEF
from cte_event_log l
group by TIMESTAMP, DIMENSIONS
order by TIMESTAMP asc
;

grant select on table DTAGENT_DB.APP.V_EVENT_LOG_METRICS_INSTRUMENTED to role DTAGENT_VIEWER;

-- example calls
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from APP.V_EVENT_LOG_METRICS_INSTRUMENTED 
limit 10;
 */

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
      and TIMESTAMP > GREATEST( timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('event_log_metrics') )
      and (RESOURCE_ATTRIBUTES:"application"::varchar is null or RESOURCE_ATTRIBUTES:"application"::varchar not in ('openflow')) -- exclude known high volume applications
    order by TIMESTAMP asc
    limit 10000 -- safety limit to avoid long running queries
)
, cte_record_attributes as (
    SELECT
        l.TIMESTAMP,
        l.RESOURCE_ATTRIBUTES,
        l.RECORD_ATTRIBUTES as snow_record_attr,
        l.RECORD,
        l.VALUE,
        OBJECT_AGG(
            CASE
                WHEN l.RESOURCE_ATTRIBUTES:"application" is NULL
                THEN r.key
                ELSE concat(l.RESOURCE_ATTRIBUTES:"application", '.', r.key)
            END,
            r.value) AS RECORD_ATTRIBUTES
    FROM cte_event_log l,
    LATERAL FLATTEN(input => l.RECORD_ATTRIBUTES) r
    WHERE l.RECORD_ATTRIBUTES is not null
    GROUP BY all
    --
    UNION ALL

    SELECT
        l.TIMESTAMP,
        l.RESOURCE_ATTRIBUTES,
        l.RECORD_ATTRIBUTES as snow_record_attr,
        l.RECORD,
        l.VALUE,
        OBJECT_CONSTRUCT() AS RECORD_ATTRIBUTES
    FROM cte_event_log l
    WHERE l.RECORD_ATTRIBUTES is null
-- ;
)
select
  extract(epoch_nanosecond from to_timestamp(l.TIMESTAMP))           as TIMESTAMP,

  MAP_CAT(
      RECORD_ATTRIBUTES::map(varchar,variant),
      MAP_CAT(
          RESOURCE_ATTRIBUTES::map(varchar,variant),
          OBJECT_CONSTRUCT(
              'db.namespace',                 RESOURCE_ATTRIBUTES:"snow.database.name",
              'snowflake.schema.name',        RESOURCE_ATTRIBUTES:"snow.schema.name",
              'snowflake.role.name',          RESOURCE_ATTRIBUTES:"snow.session.role.primary.name",
              'snowflake.warehouse.name',     RESOURCE_ATTRIBUTES:"snow.warehouse.name",
              'snowflake.query.id',           RESOURCE_ATTRIBUTES:"snow.query.id"
          )::map(varchar,variant)
        )
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
from cte_record_attributes l
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

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

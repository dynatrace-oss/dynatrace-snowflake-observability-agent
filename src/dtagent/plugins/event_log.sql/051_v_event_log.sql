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
-- APP.V_EVENT_LOG() is a shorthand to retrieve event log filtered by only new, non OTEL logs
-- 
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_EVENT_LOG
as 
select 
  extract(epoch_nanosecond from l.timestamp)                as TIMESTAMP,
  concat('New Event Log entry from ', 
        l.resource_attributes['snow.database.name'])        as _MESSAGE,
  l.record_type                                             as RECORD_TYPE,
  l.record                                                  as _RECORD,
  l.record_attributes                                       as _RECORD_ATTRIBUTES,
  l.resource_attributes                                     as _RESOURCE_ATTRIBUTES,
  
  -- logs only
  extract(epoch_nanosecond from l.observed_timestamp)       as OBSERVED_TIMESTAMP,
  l.scope                                                   as _SCOPE,
  regexp_replace(value::text, '^["]?+(.+[^"])["]?$', '\\1') as _CONTENT,
  try_parse_json(value)                                     as _VALUE_OBJECT, -- in case this could be send as separate attributes in log line
  
  -- traces only  
  extract(epoch_nanosecond from l.start_timestamp)          as START_TIME,
  l.trace:trace_id                                          as TRACE_ID,
  l.trace:span_id                                           as SPAN_ID,
  
  -- reserved for the future
  NULLIF(OBJECT_CONSTRUCT(
    'snowflake.event.resource',         l.resource,
    'snowflake.event.scope_attributes', l.scope_attributes
  ), {})                                                    as _RESERVED
from DTAGENT_DB.STATUS.EVENT_LOG l
where not regexp_like(SCOPE['name'], 'DTAGENT(_\\S*)?_OTLP')     -- we do not log what was sent via OTLP
  and VALUE not like 'Sent log%Sent log%'
  and RECORD_TYPE not in ('METRIC', 'SPAN')
  and (
   -- we log everything for all non-DTAGENT DBs
       nvl(_resource_attributes['snow.database.name']::varchar, '') not like 'DTAGENT%_DB'
   -- only report status other than DEBUG/INFO for DBs that are related to this particular dtagent,
   or (_RECORD['severity_text']::varchar not in ('DEBUG', 'INFO') and nvl(_resource_attributes['snow.database.name']::varchar, '') = 'DTAGENT_DB') -- DTAGENT_DB will be replaced with DTAGENT_$TAG_DB during deploy
  )
  and TIMESTAMP > DTAGENT_DB.APP.F_LAST_PROCESSED_TS('event_log')
order by TIMESTAMP asc
;

grant select on table DTAGENT_DB.APP.V_EVENT_LOG to role DTAGENT_VIEWER;

-- example calls
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select _RECORD:"severity_text", _SCOPE['name'], count(*)
from DTAGENT_DB.APP.V_EVENT_LOG 
group by all
limit 10;
 */

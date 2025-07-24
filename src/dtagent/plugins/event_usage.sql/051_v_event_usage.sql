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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_EVENT_USAGE_HISTORY
as
select
    'New Event Usage entry'                                                     as _MESSAGE,                                                                                                   
    extract(epoch_nanosecond from euh.start_time)                               as START_TIME,
    extract(epoch_nanosecond from euh.end_time)                                 as END_TIME,
    OBJECT_CONSTRUCT(
    )                                                                           as DIMENSIONS,
    OBJECT_CONSTRUCT(                                                 
        'snowflake.credits.used',                         euh.CREDITS_USED,       
        'snowflake.data.ingested',                        euh.BYTES_INGESTED                                      
    )                                                                           as METRICS
from 
    SNOWFLAKE.ACCOUNT_USAGE.EVENT_USAGE_HISTORY euh
where
    euh.end_time > GREATEST( timeadd(hour, -6, current_timestamp),  DTAGENT_DB.APP.F_LAST_PROCESSED_TS('event_usage'))        -- there can be 180 minutes latency
order by
    euh.end_time asc;

grant select on view DTAGENT_DB.APP.V_EVENT_USAGE_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_EVENT_USAGE_HISTORY
limit 10;
 */
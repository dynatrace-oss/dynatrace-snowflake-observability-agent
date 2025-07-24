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
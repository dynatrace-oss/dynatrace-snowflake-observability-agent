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
create or replace view DTAGENT_DB.APP.V_WAREHOUSE_LOAD_HISTORY
as
select 
    start_time                                                                  as TIMESTAMP,
    extract(epoch_nanosecond from start_time)                                   as START_TIME,
    extract(epoch_nanosecond from end_time)                                     as END_TIME,
     concat('New Warehouse Load History entry at ',
             warehouse_name)                                                    as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.name',                             WAREHOUSE_NAME
    )                                                                           as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.id',                               WAREHOUSE_ID
    )                                                                           as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.load.running',                 AVG_RUNNING,
        'snowflake.load.queued.overloaded',       AVG_QUEUED_LOAD,
        'snowflake.load.queued.provisioning',     AVG_QUEUED_PROVISIONING,
        'snowflake.load.blocked',                 AVG_BLOCKED
    )                                                                           as METRICS
from SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY wlh
where
    wlh.start_time > GREATEST(timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('warehouse_usage_load'))
order by TIMESTAMP asc;

grant select on view DTAGENT_DB.APP.V_WAREHOUSE_LOAD_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_WAREHOUSE_LOAD_HISTORY
limit 10;
*/
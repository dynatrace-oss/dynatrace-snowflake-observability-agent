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

create or replace view DTAGENT_DB.APP.V_WAREHOUSE_EVENT_HISTORY
as
select 
    timestamp                                                   as TIMESTAMP,
    concat('New Warehouse Event History entry at ',
             warehouse_name)                                    as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.name',             WAREHOUSE_NAME,
        'snowflake.warehouse.event.name',       EVENT_NAME,  
        'snowflake.warehouse.event.state',      EVENT_STATE             
    )                                                           as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'db.user',                              USER_NAME,
        'snowflake.warehouse.id',               WAREHOUSE_ID,
        'snowflake.warehouse.cluster.number',   CLUSTER_NUMBER,
        'snowflake.warehouse.event.reason',     EVENT_REASON,
        'snowflake.role.name',                  ROLE_NAME,
        'snowflake.query.id',                   QUERY_ID,
        'snowflake.warehouse.size',             SIZE,
        'snowflake.warehouse.clusters.count',   CLUSTER_COUNT
    )                                                           as ATTRIBUTES
from SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY weh
where
    weh.timestamp > GREATEST(timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('warehouse_usage'))
order by TIMESTAMP asc;

grant select on view DTAGENT_DB.APP.V_WAREHOUSE_EVENT_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_WAREHOUSE_EVENT_HISTORY
;

select count(*), max(TIMESTAMP), min(TIMESTAMP) from DTAGENT_DB.APP.V_WAREHOUSE_EVENT_HISTORY
limit 10;
*/
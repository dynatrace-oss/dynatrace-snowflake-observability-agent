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
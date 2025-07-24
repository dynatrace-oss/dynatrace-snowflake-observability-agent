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
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
create or replace view DTAGENT_DB.APP.V_SERVERLESS_TASKS
as
select 
    extract(epoch_nanosecond from sth.end_time)                                     as TIMESTAMP,
    concat('New Serverless Tasks entry for ', sth.database_name)                    as _MESSAGE,
    OBJECT_CONSTRUCT(                                                 
        'snowflake.task.name',                      sth.task_name,                                         
        'snowflake.schema.name',                    sth.schema_name,                                             
        'db.namespace',                             sth.database_name
    )                                                                               as DIMENSIONS,
    OBJECT_CONSTRUCT(                                                 
        'snowflake.task.start_time',                extract(epoch_nanosecond from sth.start_time),
        'snowflake.task.end_time',                  extract(epoch_nanosecond from sth.end_time),
        'snowflake.task.id',                        sth.task_id,                                         
        'snowflake.schema.id',                      sth.schema_id,                                 
        'snowflake.database.id',                    sth.database_id,                                              
        'snowflake.task.instance_id',               sth.instance_id                                            
    )                                                                               as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.credits.used',  sth.credits_used
    )                                                                               as METRICS
from 
    SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY sth
where
    sth.end_time > GREATEST(timeadd(hour, -4, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('serverless_tasks'))  -- max data delay is 180 min
order by
    sth.end_time asc;

grant select on view DTAGENT_DB.APP.V_SERVERLESS_TASKS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_SERVERLESS_TASKS
limit 10;
*/
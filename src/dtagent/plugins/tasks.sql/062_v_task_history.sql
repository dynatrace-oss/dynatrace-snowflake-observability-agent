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

create or replace view DTAGENT_DB.APP.V_TASK_HISTORY
as 
SELECT 
-- we must convert the null timestamps, because extracting nanoseconds converts them to nan which isn't handled by snowflake when logging
-- we should set them to some const value to show that these tasks were not yet executed and are scheduled for the future
    case 
        when th.QUERY_START_TIME is not null        then extract(epoch_nanosecond from th.QUERY_START_TIME)
                                                    else -1
    end                                                                        as TIMESTAMP,
    concat('New Tasks History entry for ', th.database_name)                  as _MESSAGE,

    OBJECT_CONSTRUCT(
        'db.namespace',                                 th.DATABASE_NAME,
        'snowflake.task.name',                          th.NAME,
        'snowflake.schema.name',                        th.SCHEMA_NAME
        
    )                                                       as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.task.graph.root_id',                 th.ROOT_TASK_ID,
        'snowflake.task.graph.version',                 th.GRAPH_VERSION,
        'snowflake.task.condition',                     th.CONDITION_TEXT,
        'snowflake.query.id',                           th.QUERY_ID,
        'snowflake.query.hash',                         th.QUERY_HASH,
        'snowflake.query.hash_version',                 th.QUERY_HASH_VERSION,
        'snowflake.query.parametrized_hash',            th.QUERY_PARAMETERIZED_HASH,
        'snowflake.query.parametrized_hash_version',    th.QUERY_PARAMETERIZED_HASH_VERSION,
        'snowflake.task.run.state',                     th.STATE,
        'snowflake.task.run.return_value',              th.RETURN_VALUE,
        'snowflake.task.run.id',                        th.RUN_ID,
        'snowflake.task.run.group_id',                  th.GRAPH_RUN_GROUP_ID,
        'snowflake.task.run.scheduled_from',             th.SCHEDULED_FROM,
        'snowflake.task.run.attempt',                   th.ATTEMPT_NUMBER,
        'snowflake.task.config',                        th.CONFIG,
        'snowflake.error.code',                         th.ERROR_CODE,
        'snowflake.error.message',                      th.ERROR_MESSAGE,
        'snowflake.task.run.scheduled_time',            th.SCHEDULED_TIME,
        'snowflake.task.run.completed_time',            th.COMPLETED_TIME
    )                                                       as ATTRIBUTES
    
FROM 
    TABLE(INFORMATION_SCHEMA.TASK_HISTORY(SCHEDULED_TIME_RANGE_START=>DATEADD(day, -1,current_timestamp()))) th
where 
    GREATEST_IGNORE_NULLS(th.QUERY_START_TIME, th.SCHEDULED_TIME, th.COMPLETED_TIME) > DTAGENT_DB.APP.F_LAST_PROCESSED_TS('task_history')
order by
    th.QUERY_START_TIME asc NULLS first;
-- query_start_time can be null if task is scheduled but not yet executed
-- sort this way to have null timestamps first, then ascending timestamps for ease of extracting last timestamp during processing
grant select on view DTAGENT_DB.APP.V_TASK_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TASK_HISTORY
limit 10;
*/
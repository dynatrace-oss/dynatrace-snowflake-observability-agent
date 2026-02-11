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
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

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
    GREATEST_IGNORE_NULLS(th.QUERY_START_TIME, th.SCHEDULED_TIME, th.COMPLETED_TIME) > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('task_history')
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
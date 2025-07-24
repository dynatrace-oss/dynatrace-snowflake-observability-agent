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
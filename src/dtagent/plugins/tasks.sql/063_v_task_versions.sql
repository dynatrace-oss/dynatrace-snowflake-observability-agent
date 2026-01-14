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
create or replace view DTAGENT_DB.APP.V_TASK_VERSIONS
as
select
    extract(epoch_nanosecond from tv.GRAPH_VERSION_CREATED_ON) as TIMESTAMP,
    concat('New Tasks Versions entry for ', tv.database_name)  as _MESSAGE,

    OBJECT_CONSTRUCT(
        'db.namespace',                             tv.DATABASE_NAME,
        'snowflake.task.name',                      tv.NAME,
        'snowflake.schema.name',                    tv.SCHEMA_NAME,
        'snowflake.warehouse.name',                 tv.WAREHOUSE_NAME
    )                                                   as DIMENSIONS,

    OBJECT_CONSTRUCT(
        'db.query.text',                            tv.DEFINITION,
        'snowflake.task.graph.root_id',             tv.ROOT_TASK_ID,
        'snowflake.task.graph.version',             tv.GRAPH_VERSION,
        'snowflake.task.id',                        tv.ID,
        'snowflake.database.id',                    tv.DATABASE_ID,
        'snowflake.schema.id',                      tv.SCHEMA_ID,
        'snowflake.task.owner',                     tv.OWNER,
        'snowflake.task.schedule',                  tv.SCHEDULE,
        'snowflake.task.predecessors',              tv.PREDECESSORS,
        'snowflake.task.condition',                 tv.CONDITION_TEXT,
        'snowflake.task.config.allow_overlap',      tv.ALLOW_OVERLAPPING_EXECUTION,
        'snowflake.task.error_integration',         tv.ERROR_INTEGRATION,
        'snowflake.task.last_committed_on',         tv.LAST_COMMITTED_ON,
        'snowflake.task.last_suspended_on',         tv.LAST_SUSPENDED_ON
    )                                                   as ATTRIBUTES,

    OBJECT_CONSTRUCT(
        'snowflake.task.graph.version.created_on',  extract(epoch_nanosecond from tv.GRAPH_VERSION_CREATED_ON)
    )                                                   as EVENT_TIMESTAMPS

from
    SNOWFLAKE.ACCOUNT_USAGE.TASK_VERSIONS tv
where
    GREATEST_IGNORE_NULLS(tv.GRAPH_VERSION_CREATED_ON, tv.LAST_COMMITTED_ON, tv.LAST_SUSPENDED_ON) > GREATEST(timeadd(month, -1, current_timestamp()), DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('task_versions'))
order by
    tv.GRAPH_VERSION_CREATED_ON asc;

grant select on view DTAGENT_DB.APP.V_TASK_VERSIONS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TASK_VERSIONS
limit 10;
*/
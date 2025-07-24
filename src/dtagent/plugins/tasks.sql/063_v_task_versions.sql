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
    GREATEST_IGNORE_NULLS(tv.GRAPH_VERSION_CREATED_ON, tv.LAST_COMMITTED_ON, tv.LAST_SUSPENDED_ON) > GREATEST(timeadd(month, -1, current_timestamp()), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('task_versions'))
order by 
    tv.GRAPH_VERSION_CREATED_ON asc;

grant select on view DTAGENT_DB.APP.V_TASK_VERSIONS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TASK_VERSIONS
limit 10;
*/
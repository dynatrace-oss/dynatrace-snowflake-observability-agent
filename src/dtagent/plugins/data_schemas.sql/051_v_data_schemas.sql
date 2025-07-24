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

-- using cases for array objects is something we should practice in order not to send empty arrays to DT
-- once an array is empty snowflake often puts and reads the row as '[]' so best to replace it with nulls
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_DATA_SCHEMAS
as
with cte_includes as (
    select ci.VALUE as object_name
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ci
    where c.PATH = 'plugins.data_schemas.include'
)
, cte_excludes as (
    select ce.VALUE as object_name
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ce
    where c.PATH = 'plugins.data_schemas.exclude'
)
, cte_all AS (
    select * from SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah
    where object_modified_by_ddl:"objectDomain" in ('Table', 'Schema', 'Database')
        and query_start_time > GREATEST(timeadd(hour, -4, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('data_schemas'))  -- max data delay is 180 min
        and object_modified_by_ddl:"objectName" LIKE ANY (select object_name from cte_includes)
        and not object_modified_by_ddl:"objectName" LIKE ANY (select object_name from cte_excludes)
)
, cte_flat AS (
    SELECT
        value:objectName::string as object_name,
        value:objectDomain::string as object_domain,
        value:columns AS columns,
        query_id
    FROM
        cte_all,
        LATERAL FLATTEN(input => OBJECTS_MODIFIED)
)
, cte_flat_obj as (
    select
        object_construct(
            object_name, object_construct('objectDomain', object_domain, 'objectColumns', listagg(value:columnName::STRING, ', '))
        ) as object_modified,
        query_id
    from 
        cte_flat,
        lateral flatten(input => columns)
    group by query_id, object_name, object_domain
)

select
    concat('Objects accessed by query ', ah.query_id, ' run by ', user_name)   as _MESSAGE,
    extract(epoch_nanosecond from query_start_time)                         as TIMESTAMP,
    OBJECT_CONSTRUCT(
        'snowflake.query.id',                                       ah.query_id,
        'db.user',                                                  user_name,
        'snowflake.query.parent_id',                                parent_query_id,
        'snowflake.query.root_id',                                  root_query_id,
        'snowflake.object.ddl.modified',                            fo.object_modified,
        'snowflake.object.type',                                    object_modified_by_ddl:"objectDomain",
        'snowflake.object.id',                                      object_modified_by_ddl:"objectId",
        'snowflake.object.name',                                    object_modified_by_ddl:"objectName",
        'snowflake.object.ddl.operation',                           object_modified_by_ddl:"operationType",
        'snowflake.object.ddl.properties',                          object_modified_by_ddl:"properties"
    )                                                                       as ATTRIBUTES
from cte_all ah
left join cte_flat_obj fo on ah.query_id = fo.query_id
order by
    query_start_time asc;

grant select on view DTAGENT_DB.APP.V_DATA_SCHEMAS to role DTAGENT_VIEWER;


-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from DTAGENT_DB.APP.V_DATA_SCHEMAS limit 10;
 */
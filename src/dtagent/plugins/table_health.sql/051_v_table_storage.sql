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
--
-- APP.V_TABLE_STORAGE() retrieves table storage metrics from SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
-- with include/exclude filtering and min/max table constraints
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_TABLE_STORAGE
as
with cte_includes as (
    select ci.VALUE as full_table_name_pattern
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ci
    where c.PATH = 'plugins.table_health.include'
)
, cte_excludes as (
    select ce.VALUE as full_table_name_pattern
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ce
    where c.PATH = 'plugins.table_health.exclude'
)
, cte_min_table_bytes as (
    select c.VALUE::number as min_bytes
    from CONFIG.CONFIGURATIONS c
    where c.PATH = 'plugins.table_health.min_table_bytes'
)
, cte_max_tables as (
    select c.VALUE::number as max_tables
    from CONFIG.CONFIGURATIONS c
    where c.PATH = 'plugins.table_health.max_tables'
)
, cte_table_storage as (
    select
        concat(tsm.TABLE_CATALOG, '.',
            tsm.TABLE_SCHEMA, '.',
            tsm.TABLE_NAME)                                                    as table_full_name,
        tsm.table_catalog,
        tsm.table_schema,
        tsm.table_name,
        tsm.active_bytes,
        tsm.time_travel_bytes,
        tsm.failsafe_bytes,
        tsm.retained_for_clone_bytes,
        coalesce(t.row_count, 0)                                               as row_count,
        coalesce(t.clustering_key, 'NONE')                                     as clustering_key,
        row_number() over (order by tsm.active_bytes desc)                     as row_num
    from SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS tsm
    left join SNOWFLAKE.ACCOUNT_USAGE.TABLES t
        on tsm.table_catalog = t.table_catalog
        and tsm.table_schema = t.table_schema
        and tsm.table_name = t.table_name
        and t.deleted is null
    where tsm.active_bytes >= (select coalesce(min_bytes, 1073741824) from cte_min_table_bytes)
    and table_full_name like any (select full_table_name_pattern from cte_includes)
    and not table_full_name like any (select full_table_name_pattern from cte_excludes)
)
select
    extract(epoch_nanosecond from current_timestamp)                                                                    as START_TIME,

    concat('Table storage metrics for ', coalesce(table_full_name, ''))                                                 as _MESSAGE,
    -- metric and span dimensions
    object_construct(
        'db.namespace',                                             table_catalog,
        'snowflake.schema.name',                                    table_schema,
        'db.collection.name',                                       table_name,
        'snowflake.table.full_name',                                table_full_name,
        'snowflake.table.clustering_key',                           clustering_key
    )                                                                                                                   as DIMENSIONS,
    object_construct(
    )                                                                                                                   as ATTRIBUTES,
    object_construct(
    )                                                                                                                   as EVENT_TIMESTAMPS,
    -- metrics
    object_construct(
        'snowflake.table.active_bytes',                             active_bytes,
        'snowflake.table.time_travel_bytes',                        time_travel_bytes,
        'snowflake.table.failsafe_bytes',                           failsafe_bytes,
        'snowflake.table.retained_for_clone_bytes',                 retained_for_clone_bytes,
        'snowflake.data.rows',                                      row_count
    )                                                                                                                   as METRICS
from cte_table_storage
where row_num <= (select coalesce(max_tables, 500) from cte_max_tables)
;

grant select on table DTAGENT_DB.APP.V_TABLE_STORAGE to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.V_TABLE_STORAGE
limit 10;
 */

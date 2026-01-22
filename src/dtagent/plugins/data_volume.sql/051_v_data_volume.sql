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
-- APP.V_DATA_VOLUME() is a shorthand to retrieve data volume information from all tables in the system
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_DATA_VOLUME
as
with cte_includes as (
    select ci.VALUE as full_table_name_pattern
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ci
    where c.PATH = 'plugins.data_volume.include'
)
, cte_excludes as (
    select ce.VALUE as full_table_name_pattern
    from CONFIG.CONFIGURATIONS c,
       table(flatten(c.VALUE)) ce
    where c.PATH = 'plugins.data_volume.exclude'
)
, cte_data_volume as (
    select
        concat(t.TABLE_CATALOG, '.',
            t.TABLE_SCHEMA, '.',
            t.TABLE_NAME)               as table_full_name,
        t.table_catalog,
        t.table_schema,
        t.table_name,
        t.table_type,
        t.row_count,
        t.bytes,
        t.last_altered,
        t.last_ddl
    from SNOWFLAKE.ACCOUNT_USAGE.TABLES t
    where t.TABLE_TYPE != 'VIEW'
    and t.DELETED is null -- when table is still present DELETE is empty as there is no deleted date
    and table_full_name LIKE ANY (select full_table_name_pattern from cte_includes)
    and not table_full_name LIKE ANY (select full_table_name_pattern from cte_excludes)
)
select
    extract(epoch_nanosecond from current_timestamp)                                                                    as START_TIME,

    concat('Events at ', coalesce(table_full_name, ''), ' for table ', coalesce(dv.table_full_name, ''))                as _MESSAGE,
    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'db.namespace',                                             dv.table_catalog,
        'db.collection.name',                                       dv.table_full_name,
        'snowflake.table.type',                                     dv.table_type
    )                                                                                                                   as DIMENSIONS,
    OBJECT_CONSTRUCT(
    )                                                                                                                   as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.table.update',                                   extract(epoch_nanosecond from dv.last_altered),
        'snowflake.table.ddl',                                      extract(epoch_nanosecond from dv.last_ddl)
    )                                                                                                                   as EVENT_TIMESTAMPS,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.table.time_since.last_update',                   timediff('minute', dv.last_altered, current_timestamp),
        'snowflake.table.time_since.last_ddl',                      timediff('minute', dv.last_ddl, current_timestamp),
        'snowflake.data.rows',                                      dv.row_count,
        'snowflake.data.size',                                      dv.bytes
    )                                                                                                                   as METRICS
from cte_data_volume dv
;

grant select on table DTAGENT_DB.APP.V_DATA_VOLUME to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.V_DATA_VOLUME
limit 10;
 */

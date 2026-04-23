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
-- APP.V_COLD_TABLES aggregates per-table access frequency and last-access timestamps
-- from SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY over a configurable lookback window.
-- Tables with no access within cold_threshold_days are flagged as "cold".
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_COLD_TABLES
as
with cte_table_access as (
    select
        f.VALUE:"objectDomain"::STRING                              as OBJECT_DOMAIN,
        f.VALUE:"objectName"::STRING                                as FULL_TABLE_NAME,
        SPLIT_PART(f.VALUE:"objectName"::STRING, '.', 1)            as TABLE_CATALOG,
        SPLIT_PART(f.VALUE:"objectName"::STRING, '.', 2)            as TABLE_SCHEMA,
        SPLIT_PART(f.VALUE:"objectName"::STRING, '.', 3)            as TABLE_NAME,
        ah.QUERY_START_TIME
    from SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
        LATERAL FLATTEN(INPUT => ah.BASE_OBJECTS_ACCESSED) f
    where ah.QUERY_START_TIME >= DATEADD(
            DAY,
            -1 * DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.cold_tables.lookback_days', 365),
            CURRENT_TIMESTAMP()
        )
      and f.VALUE:"objectDomain"::STRING = 'Table'
)
, cte_aggregated as (
    select
        TABLE_CATALOG,
        TABLE_SCHEMA,
        TABLE_NAME,
        FULL_TABLE_NAME,
        COUNT(*)                                                    as ACCESS_COUNT,
        MAX(QUERY_START_TIME)                                       as LAST_ACCESSED_AT,
        DATEDIFF(DAY, MAX(QUERY_START_TIME), CURRENT_TIMESTAMP())   as DAYS_SINCE_LAST_ACCESS,
        CASE
            WHEN DATEDIFF(DAY, MAX(QUERY_START_TIME), CURRENT_TIMESTAMP())
                > DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.cold_tables.cold_threshold_days', 90)
            THEN 'cold'
            ELSE 'warm'
        END                                                         as COLD_STATUS
    from cte_table_access
    group by TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, FULL_TABLE_NAME
)
select
    current_timestamp()                                                                                                 as TIMESTAMP,

    concat('Table ', FULL_TABLE_NAME, ' accessed ', ACCESS_COUNT, ' times, last access ',
           DAYS_SINCE_LAST_ACCESS, ' days ago [', COLD_STATUS, ']')                                                     as _MESSAGE,

    OBJECT_CONSTRUCT(
        'db.namespace',                                             TABLE_CATALOG,
        'snowflake.schema.name',                                    TABLE_SCHEMA,
        'db.collection.name',                                       TABLE_NAME,
        'snowflake.table.full_name',                                FULL_TABLE_NAME,
        'snowflake.table.cold_status',                              COLD_STATUS
    )                                                                                                                   as DIMENSIONS,

    OBJECT_CONSTRUCT(
        'snowflake.table.last_accessed_at',                         TO_VARCHAR(CONVERT_TIMEZONE('UTC', LAST_ACCESSED_AT), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
    )                                                                                                                   as ATTRIBUTES,

    OBJECT_CONSTRUCT(
        'snowflake.table.access.count',                             ACCESS_COUNT,
        'snowflake.table.days_since_last_access',                   DAYS_SINCE_LAST_ACCESS
    )                                                                                                                   as METRICS
from cte_aggregated;

grant select on view DTAGENT_DB.APP.V_COLD_TABLES to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select *
from DTAGENT_DB.APP.V_COLD_TABLES
limit 10;
 */

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
-- APP.P_SNAPSHOT_TABLE_HEALTH() inserts one row per table into TABLE_HEALTH_HISTORY
-- by joining V_TABLE_STORAGE with TABLE_CLUSTERING_RESULTS, then prunes rows older
-- than plugins.table_health.history_retention_days.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH()
    returns varchar
    language sql
    execute as caller
as
$$
declare
    v_retention_days    integer default 30;
    v_inserted          integer default 0;
    v_pruned            integer default 0;
begin
    -- read retention from config (default 30 days)
    v_retention_days := coalesce(
        (
            select max(VALUE::integer)
            from DTAGENT_DB.CONFIG.CONFIGURATIONS
            where PATH = 'plugins.table_health.history_retention_days'
        ),
        v_retention_days
    );

    -- insert snapshot: join raw storage data with latest clustering results
    -- NOTE: V_TABLE_STORAGE exposes OTEL-shaped columns only; read from
    --       SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS directly here,
    --       applying the same include/exclude/min_bytes filters as the view.
    insert into DTAGENT_DB.APP.TABLE_HEALTH_HISTORY (
        TABLE_FULL_NAME,
        TABLE_CATALOG,
        TABLE_SCHEMA,
        TABLE_NAME,
        ACTIVE_BYTES,
        ROW_COUNT,
        TIME_TRAVEL_BYTES,
        FAILSAFE_BYTES,
        RETAINED_FOR_CLONE_BYTES,
        AVERAGE_DEPTH,
        AVERAGE_OVERLAPS,
        SNAPSHOTTED_AT
    )
    with cte_includes as (
        select ci.VALUE::text as full_table_name_pattern
        from DTAGENT_DB.CONFIG.CONFIGURATIONS cfg,
             table(flatten(cfg.VALUE)) ci
        where cfg.PATH = 'plugins.table_health.include'
    )
    , cte_excludes as (
        select ce.VALUE::text as full_table_name_pattern
        from DTAGENT_DB.CONFIG.CONFIGURATIONS cfg,
             table(flatten(cfg.VALUE)) ce
        where cfg.PATH = 'plugins.table_health.exclude'
    )
    , cte_min_bytes as (
        select coalesce(max(cfg.VALUE::number), 1073741824) as min_bytes
        from DTAGENT_DB.CONFIG.CONFIGURATIONS cfg
        where cfg.PATH = 'plugins.table_health.min_table_bytes'
    )
    , cte_max_tables as (
        select coalesce(max(cfg.VALUE::number), 500) as max_tables
        from DTAGENT_DB.CONFIG.CONFIGURATIONS cfg
        where cfg.PATH = 'plugins.table_health.max_tables'
    )
    , cte_storage as (
        select
            concat(tsm.TABLE_CATALOG, '.', tsm.TABLE_SCHEMA, '.', tsm.TABLE_NAME) as table_full_name,
            tsm.TABLE_CATALOG                                                       as table_catalog,
            tsm.TABLE_SCHEMA                                                        as table_schema,
            tsm.TABLE_NAME                                                          as table_name,
            tsm.ACTIVE_BYTES                                                        as active_bytes,
            coalesce(t.ROW_COUNT, 0)                                               as row_count,
            tsm.TIME_TRAVEL_BYTES                                                   as time_travel_bytes,
            tsm.FAILSAFE_BYTES                                                      as failsafe_bytes,
            tsm.RETAINED_FOR_CLONE_BYTES                                           as retained_for_clone_bytes,
            row_number() over (order by tsm.ACTIVE_BYTES desc)                     as row_num
        from SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS tsm
        left join SNOWFLAKE.ACCOUNT_USAGE.TABLES t
            on tsm.TABLE_CATALOG = t.TABLE_CATALOG
            and tsm.TABLE_SCHEMA = t.TABLE_SCHEMA
            and tsm.TABLE_NAME = t.TABLE_NAME
            and t.DELETED is null
        where tsm.ACTIVE_BYTES >= (select min_bytes from cte_min_bytes)
        and concat(tsm.TABLE_CATALOG, '.', tsm.TABLE_SCHEMA, '.', tsm.TABLE_NAME)
            like any (select full_table_name_pattern from cte_includes)
        and not concat(tsm.TABLE_CATALOG, '.', tsm.TABLE_SCHEMA, '.', tsm.TABLE_NAME)
            like any (select full_table_name_pattern from cte_excludes)
    )
    select
        s.table_full_name,
        s.table_catalog,
        s.table_schema,
        s.table_name,
        s.active_bytes,
        s.row_count,
        s.time_travel_bytes,
        s.failsafe_bytes,
        s.retained_for_clone_bytes,
        c.AVERAGE_DEPTH,
        c.AVERAGE_OVERLAPS,
        current_timestamp()
    from cte_storage AS s
    left join DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS AS c
        on c.TABLE_FULL_NAME = s.table_full_name
    where s.row_num <= (select max_tables from cte_max_tables);

    v_inserted := sqlrowcount;

    -- prune old rows (capture variable into LET before use in SQL per $$-block anti-pattern)
    LET l_retention_days INTEGER := v_retention_days;
    delete from DTAGENT_DB.APP.TABLE_HEALTH_HISTORY
    where SNAPSHOTTED_AT < dateadd('day', -:l_retention_days, current_timestamp());

    v_pruned := sqlrowcount;

    return 'inserted=' || v_inserted::varchar || ' pruned=' || v_pruned::varchar;
end;
$$;

grant usage on procedure DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH() to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_OWNER;
call DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH();
 */

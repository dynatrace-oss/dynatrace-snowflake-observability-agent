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
-- APP.P_COLLECT_CLUSTERING_INFO() iterates over clustered tables visible in
-- SNOWFLAKE.ACCOUNT_USAGE.TABLES, calls SYSTEM$CLUSTERING_INFORMATION() per table,
-- and upserts results into APP.TABLE_CLUSTERING_RESULTS.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_COLLECT_CLUSTERING_INFO()
returns text
language SQL
execute as caller
as
$$
declare
    v_table_full_name   text;
    v_table_catalog     text;
    v_table_schema      text;
    v_table_name        text;
    v_clustering_key    text;
    v_clust_json        variant;
    v_avg_depth         float;
    v_avg_overlaps      float;
    v_total_partitions  number;
    v_const_partitions  number;
    v_processed         number default 0;
    v_errors            number default 0;
    v_max_tables        number;
    c_clustered_tables  cursor for
        select
            concat(t.TABLE_CATALOG, '.', t.TABLE_SCHEMA, '.', t.TABLE_NAME) as table_full_name,
            t.TABLE_CATALOG                                                  as table_catalog,
            t.TABLE_SCHEMA                                                   as table_schema,
            t.TABLE_NAME                                                     as table_name,
            t.CLUSTERING_KEY                                                 as clustering_key
        from SNOWFLAKE.ACCOUNT_USAGE.TABLES t
        inner join (
            select ci.VALUE::text as full_table_name_pattern
            from DTAGENT_DB.CONFIG.CONFIGURATIONS c,
               table(flatten(c.VALUE)) ci
            where c.PATH = 'plugins.table_health.include'
        ) inc
            on concat(t.TABLE_CATALOG, '.', t.TABLE_SCHEMA, '.', t.TABLE_NAME)
               like inc.full_table_name_pattern
        where t.CLUSTERING_KEY is not null
        and t.DELETED is null
        and not concat(t.TABLE_CATALOG, '.', t.TABLE_SCHEMA, '.', t.TABLE_NAME) like any (
            select ce.VALUE::text as full_table_name_pattern
            from DTAGENT_DB.CONFIG.CONFIGURATIONS c,
               table(flatten(c.VALUE)) ce
            where c.PATH = 'plugins.table_health.exclude'
        )
        order by t.TABLE_CATALOG, t.TABLE_SCHEMA, t.TABLE_NAME;
begin
    select coalesce(c.VALUE::number, 100)
    into :v_max_tables
    from DTAGENT_DB.CONFIG.CONFIGURATIONS c
    where c.PATH = 'plugins.table_health.max_clustered_tables';

    open c_clustered_tables;

    for r_table in c_clustered_tables do
        if (v_processed >= v_max_tables) then
            break;
        end if;

        LET v_full_name TEXT := r_table.table_full_name;
        LET v_cat TEXT       := r_table.table_catalog;
        LET v_sch TEXT       := r_table.table_schema;
        LET v_tbl TEXT       := r_table.table_name;
        LET v_key TEXT       := r_table.clustering_key;

        begin
            select parse_json(SYSTEM$CLUSTERING_INFORMATION(:v_full_name))
            into :v_clust_json;

            v_avg_depth        := v_clust_json:average_depth::float;
            v_avg_overlaps     := v_clust_json:average_overlaps::float;
            v_total_partitions := v_clust_json:total_partition_count::number;
            v_const_partitions := v_clust_json:total_constant_partition_count::number;

            merge into DTAGENT_DB.APP.TABLE_CLUSTERING_RESULTS tgt
            using (
                select
                    :v_full_name                as TABLE_FULL_NAME,
                    :v_cat                      as TABLE_CATALOG,
                    :v_sch                      as TABLE_SCHEMA,
                    :v_tbl                      as TABLE_NAME,
                    :v_key                      as CLUSTERING_KEY,
                    :v_avg_depth                as AVERAGE_DEPTH,
                    :v_avg_overlaps             as AVERAGE_OVERLAPS,
                    :v_total_partitions         as TOTAL_PARTITION_COUNT,
                    :v_const_partitions         as TOTAL_CONSTANT_PARTITION_COUNT,
                    current_timestamp           as COLLECTED_AT
            ) src
            on tgt.TABLE_FULL_NAME = src.TABLE_FULL_NAME
            when matched then update set
                TABLE_CATALOG                  = src.TABLE_CATALOG,
                TABLE_SCHEMA                   = src.TABLE_SCHEMA,
                TABLE_NAME                     = src.TABLE_NAME,
                CLUSTERING_KEY                 = src.CLUSTERING_KEY,
                AVERAGE_DEPTH                  = src.AVERAGE_DEPTH,
                AVERAGE_OVERLAPS               = src.AVERAGE_OVERLAPS,
                TOTAL_PARTITION_COUNT          = src.TOTAL_PARTITION_COUNT,
                TOTAL_CONSTANT_PARTITION_COUNT = src.TOTAL_CONSTANT_PARTITION_COUNT,
                COLLECTED_AT                   = src.COLLECTED_AT
            when not matched then insert (
                TABLE_FULL_NAME, TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, CLUSTERING_KEY,
                AVERAGE_DEPTH, AVERAGE_OVERLAPS, TOTAL_PARTITION_COUNT,
                TOTAL_CONSTANT_PARTITION_COUNT, COLLECTED_AT
            ) values (
                src.TABLE_FULL_NAME, src.TABLE_CATALOG, src.TABLE_SCHEMA, src.TABLE_NAME,
                src.CLUSTERING_KEY, src.AVERAGE_DEPTH, src.AVERAGE_OVERLAPS,
                src.TOTAL_PARTITION_COUNT, src.TOTAL_CONSTANT_PARTITION_COUNT, src.COLLECTED_AT
            );

            v_processed := v_processed + 1;
        exception
            when statement_error then
                SYSTEM$LOG_WARN('P_COLLECT_CLUSTERING_INFO: skipping ' || :v_full_name || ' — ' || SQLERRM);
                v_errors := v_errors + 1;
        end;
    end for;

    close c_clustered_tables;

    return 'Collected clustering info: processed=' || v_processed || ', errors=' || v_errors;
exception
    when statement_error then
        SYSTEM$LOG_WARN('P_COLLECT_CLUSTERING_INFO: ' || SQLERRM);
        return sqlerrm;
end;
$$
;


-- call DTAGENT_DB.APP.P_COLLECT_CLUSTERING_INFO();

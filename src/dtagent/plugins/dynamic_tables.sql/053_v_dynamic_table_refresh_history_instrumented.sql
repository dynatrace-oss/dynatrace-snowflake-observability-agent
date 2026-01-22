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
-- APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED() returns metadata for all dynamic table refresh history
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED
as
with cte_includes as (
    select distinct ci.VALUE as db_pattern
    from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
    where c.PATH = 'plugins.dynamic_tables.include'
)
, cte_excludes as (
    select distinct ce.VALUE as db_pattern
    from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
    where c.PATH = 'plugins.dynamic_tables.exclude'
)
, cte_dynamic_tables_refresh_history as (
    select
        DATA_TIMESTAMP                            as TIMESTAMP,

        NAME,
        SCHEMA_NAME,
        DATABASE_NAME,
        QUALIFIED_NAME,
        DATA_TIMESTAMP,
        STATE,
        STATE_CODE,
        STATE_MESSAGE,
        QUERY_ID,
        GRAPH_HISTORY_VALID_FROM,
        REFRESH_START_TIME,
        REFRESH_END_TIME,
        COMPLETION_TARGET,
        TARGET_LAG_SEC,
        LAST_COMPLETED_DEPENDENCY:qualified_name    as LAST_COMPLETED_DEPENDENCY_NAME,
        LAST_COMPLETED_DEPENDENCY:data_timestamp    as LAST_COMPLETED_DEPENDENCY_TIMESTAMP,
        STATISTICS:numInsertedRows                  as STATISTICS_NUM_INSERTED_ROWS,
        STATISTICS:numDeletedRows                   as STATISTICS_NUM_DELETED_ROWS,
        STATISTICS:numCopiedRows                    as STATISTICS_NUM_COPIED_ROWS,
        STATISTICS:numAddedPartitions               as STATISTICS_NUM_ADDED_PARTITIONS,
        STATISTICS:numRemovedPartitions             as STATISTICS_NUM_REMOVED_PARTITIONS,
        REFRESH_ACTION,
        REFRESH_TRIGGER
    from
        table(INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY(
                DATA_TIMESTAMP_START => timeadd(hour,-2,current_timestamp()),
                RESULT_LIMIT => 10000
        ))
    where QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
    and DATA_TIMESTAMP > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('dynamic_table_refresh_history')
    and QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
    and not QUALIFIED_NAME LIKE ANY (select db_pattern from cte_excludes)
)
select
    extract(epoch_nanosecond from to_timestamp(qh.TIMESTAMP))                                                           as TIMESTAMP,
    qh.REFRESH_START_TIME                                                                                               as START_TIME,
    qh.REFRESH_END_TIME                                                                                                 as END_TIME,
    concat('Dynamic table (', coalesce(qh.QUALIFIED_NAME, '') ,') refresh history at ', coalesce(qh.DATABASE_NAME, '')) as _MESSAGE,

    qh.QUALIFIED_NAME                                                                                                   as NAME,

    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'db.collection.name',                                           qh.NAME,
        'snowflake.schema.name',                                        qh.SCHEMA_NAME,
        'db.namespace',                                                 qh.DATABASE_NAME,
        'snowflake.table.full_name',                                    qh.QUALIFIED_NAME
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.refresh.data_timestamp',               qh.DATA_TIMESTAMP,
        'snowflake.table.dynamic.refresh.state',                        qh.STATE,
        'snowflake.table.dynamic.refresh.code',                         qh.STATE_CODE,
        'snowflake.table.dynamic.refresh.message',                      qh.STATE_MESSAGE,
        'snowflake.query.id',                                           qh.QUERY_ID,
        'snowflake.table.dynamic.graph.valid_from',                     qh.GRAPH_HISTORY_VALID_FROM,
        'snowflake.table.dynamic.refresh.start',                        qh.REFRESH_START_TIME,
        'snowflake.table.dynamic.refresh.end',                          qh.REFRESH_END_TIME,
        'snowflake.table.dynamic.refresh.completion_target',            qh.COMPLETION_TARGET,
        'snowflake.table.dynamic.latest.dependency.name',               qh.LAST_COMPLETED_DEPENDENCY_NAME,
        'snowflake.table.dynamic.latest.dependency.data_timestamp',     qh.LAST_COMPLETED_DEPENDENCY_TIMESTAMP,
        'snowflake.table.dynamic.refresh.action',                       qh.REFRESH_ACTION,
        'snowflake.table.dynamic.refresh.trigger',                      qh.REFRESH_TRIGGER
    )                                                                                                                   as ATTRIBUTES,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.lag.target.value',                     qh.TARGET_LAG_SEC,
        'snowflake.rows.inserted',                                      qh.STATISTICS_NUM_INSERTED_ROWS,
        'snowflake.rows.deleted',                                       qh.STATISTICS_NUM_DELETED_ROWS,
        'snowflake.rows.copied',                                        qh.STATISTICS_NUM_COPIED_ROWS,
        'snowflake.partitions.added',                                   qh.STATISTICS_NUM_ADDED_PARTITIONS,
        'snowflake.partitions.removed',                                 qh.STATISTICS_NUM_REMOVED_PARTITIONS
    )                                                                                                                   as METRICS,
    OBJECT_CONSTRUCT(
    )                                                                                                                   as EVENT_TIMESTAMPS

from
    cte_dynamic_tables_refresh_history qh
order by
    TIMESTAMP asc
;
grant select on table APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED
limit 10;
 */
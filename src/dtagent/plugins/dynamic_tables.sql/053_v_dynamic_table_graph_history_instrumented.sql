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
-- APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED() returns metadata for all dynamic table refresh history
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED
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
        current_timestamp                   as TIMESTAMP,

        NAME,
        SCHEMA_NAME,
        DATABASE_NAME,
        QUALIFIED_NAME,
        INPUTS,
        TARGET_LAG_TYPE,
        TARGET_LAG_SEC,
        QUERY_TEXT,
        VALID_FROM,
        VALID_TO,
        SCHEDULING_STATE:state              as SCHEDULING_STATE_STATE,
        SCHEDULING_STATE:reason_code        as SCHEDULING_STATE_REASON_CODE,
        SCHEDULING_STATE:reason_message     as SCHEDULING_STATE_REASON_MESSAGE,
        SCHEDULING_STATE:suspended_on       as SCHEDULING_STATE_SUSPENDED_ON,
        SCHEDULING_STATE:resumed_on         as SCHEDULING_STATE_RESUMED_ON,
        ALTER_TRIGGER
    from
        table(INFORMATION_SCHEMA.DYNAMIC_TABLE_GRAPH_HISTORY(
                HISTORY_START => timeadd(hour,-2,current_timestamp())
        ))
    where QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
    and (VALID_TO is null or VALID_TO > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('dynamic_table_graph_history'))
    and QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
    and not QUALIFIED_NAME LIKE ANY (select db_pattern from cte_excludes)
)
select
    extract(epoch_nanosecond from to_timestamp(qh.TIMESTAMP))                                                           as TIMESTAMP,

    qh.QUALIFIED_NAME                                                                                                   as NAME,
    concat('Dynamic table (', coalesce(qh.QUALIFIED_NAME, '') ,') graph history at ', coalesce(qh.DATABASE_NAME, ''))   as _MESSAGE,

    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'db.collection.name',                                           qh.NAME,
        'snowflake.schema.name',                                        qh.SCHEMA_NAME,
        'db.namespace',                                                 qh.DATABASE_NAME,
        'snowflake.table.full_name',                                    qh.QUALIFIED_NAME
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'db.query.text',                                                qh.QUERY_TEXT,
        'snowflake.table.dynamic.graph.inputs',                         qh.INPUTS,
        'snowflake.table.dynamic.graph.valid_to',                       qh.VALID_TO,
        'snowflake.table.dynamic.lag.target.type',                      qh.TARGET_LAG_TYPE,
        'snowflake.table.dynamic.scheduling.state',                     qh.SCHEDULING_STATE_STATE,
        'snowflake.table.dynamic.scheduling.reason.code',               qh.SCHEDULING_STATE_REASON_CODE,
        'snowflake.table.dynamic.scheduling.reason.message',            qh.SCHEDULING_STATE_REASON_MESSAGE,
        'snowflake.table.dynamic.graph.alter_trigger',                  qh.ALTER_TRIGGER

    )                                                                                                                   as ATTRIBUTES,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.lag.target.value',                     qh.TARGET_LAG_SEC
    )                                                                                                                   as METRICS,
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.scheduling.suspended_on',              extract(epoch_nanosecond from to_timestamp(qh.SCHEDULING_STATE_SUSPENDED_ON)),
        'snowflake.table.dynamic.scheduling.resumed_on',                extract(epoch_nanosecond from to_timestamp(qh.SCHEDULING_STATE_RESUMED_ON)),
        'snowflake.table.dynamic.graph.valid_from',                     extract(epoch_nanosecond from to_timestamp(qh.VALID_FROM))
    )                                                                                                                   as EVENT_TIMESTAMPS

from
    cte_dynamic_tables_refresh_history qh
order by
    TIMESTAMP asc
;
grant select on table APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select *
from APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED
limit 10;
 */
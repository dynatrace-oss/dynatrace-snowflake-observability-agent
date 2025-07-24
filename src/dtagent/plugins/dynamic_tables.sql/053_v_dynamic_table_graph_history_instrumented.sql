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
    and (VALID_TO is null or VALID_TO > DTAGENT_DB.APP.F_LAST_PROCESSED_TS('dynamic_table_graph_history'))
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
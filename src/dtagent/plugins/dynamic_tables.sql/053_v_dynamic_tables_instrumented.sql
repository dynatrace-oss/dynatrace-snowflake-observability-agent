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
-- APP.V_DYNAMIC_TABLES_INSTRUMENTED() returns metadata for all dynamic tables defined in Snowflake.
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_DYNAMIC_TABLES_INSTRUMENTED
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
, cte_dynamic_tables as (
    select 
        current_timestamp                   as TIMESTAMP,

        NAME,
        SCHEMA_NAME,
        DATABASE_NAME,
        QUALIFIED_NAME,
        TARGET_LAG_SEC,
        TARGET_LAG_TYPE,
        MEAN_LAG_SEC,
        MAXIMUM_LAG_SEC,
        TIME_ABOVE_TARGET_LAG_SEC,
        TIME_WITHIN_TARGET_LAG_RATIO,
        LATEST_DATA_TIMESTAMP,
        LAST_COMPLETED_REFRESH_STATE,
        LAST_COMPLETED_REFRESH_STATE_CODE,
        LAST_COMPLETED_REFRESH_STATE_MESSAGE,
        EXECUTING_REFRESH_QUERY_ID,
        SCHEDULING_STATE:state              as SCHEDULING_STATE_STATE,
        SCHEDULING_STATE:reason_code        as SCHEDULING_STATE_REASON_CODE,
        SCHEDULING_STATE:reason_message     as SCHEDULING_STATE_REASON_MESSAGE,
        SCHEDULING_STATE:suspended_on       as SCHEDULING_STATE_SUSPENDED_ON,
        SCHEDULING_STATE:resumed_on         as SCHEDULING_STATE_RESUMED_ON
    from 
        table(INFORMATION_SCHEMA.DYNAMIC_TABLES())
    where
            QUALIFIED_NAME LIKE ANY (select db_pattern from cte_includes)
    and not QUALIFIED_NAME LIKE ANY (select db_pattern from cte_excludes)
)
select 
    extract(epoch_nanosecond from to_timestamp(qh.TIMESTAMP))                                                           as TIMESTAMP,

    qh.QUALIFIED_NAME                                                                                                   as NAME,
    concat('Dynamic table (', coalesce(qh.QUALIFIED_NAME, '') ,') details at ', coalesce(qh.DATABASE_NAME, ''))         as _MESSAGE,

    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'db.collection.name',                                       qh.NAME,
        'snowflake.schema.name',                                    qh.SCHEMA_NAME,
        'db.namespace',                                             qh.DATABASE_NAME,
        'snowflake.table.full_name',                                qh.QUALIFIED_NAME
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.lag.target.type',                  qh.TARGET_LAG_TYPE,
        'snowflake.table.dynamic.latest.data_timestamp',            qh.LATEST_DATA_TIMESTAMP,
        'snowflake.table.dynamic.latest.state',                     qh.LAST_COMPLETED_REFRESH_STATE,
        'snowflake.table.dynamic.latest.code',                      qh.LAST_COMPLETED_REFRESH_STATE_CODE,
        'snowflake.table.dynamic.latest.message',                   qh.LAST_COMPLETED_REFRESH_STATE_MESSAGE,
        'snowflake.query.id',                                       qh.EXECUTING_REFRESH_QUERY_ID,
        'snowflake.table.dynamic.scheduling.state',                 qh.SCHEDULING_STATE_STATE,
        'snowflake.table.dynamic.scheduling.reason.code',           qh.SCHEDULING_STATE_REASON_CODE,
        'snowflake.table.dynamic.scheduling.reason.message',        qh.SCHEDULING_STATE_REASON_MESSAGE
    )                                                                                                                   as ATTRIBUTES,
    -- metrics
    OBJECT_CONSTRUCT(
	    'snowflake.table.dynamic.lag.mean',                         qh.MEAN_LAG_SEC,
	    'snowflake.table.dynamic.lag.max',                          qh.MAXIMUM_LAG_SEC,
	    'snowflake.table.dynamic.lag.target.value',                       qh.TARGET_LAG_SEC,
	    'snowflake.table.dynamic.lag.target.time_above',            qh.TIME_ABOVE_TARGET_LAG_SEC,
	    'snowflake.table.dynamic.lag.target.within_ratio',          qh.TIME_WITHIN_TARGET_LAG_RATIO
    )                                                                                                                   as METRICS,
    OBJECT_CONSTRUCT(
        'snowflake.table.dynamic.scheduling.suspended_on',          extract(epoch_nanosecond from to_timestamp(qh.SCHEDULING_STATE_SUSPENDED_ON)),
        'snowflake.table.dynamic.scheduling.resumed_on',            extract(epoch_nanosecond from to_timestamp(qh.SCHEDULING_STATE_RESUMED_ON))
    )                                                                                                                   as EVENT_TIMESTAMPS

from 
    cte_dynamic_tables qh
order by 
    TIMESTAMP asc
;
grant select on table APP.V_DYNAMIC_TABLES_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * 
from APP.V_DYNAMIC_TABLES_INSTRUMENTED 
limit 10;
 */
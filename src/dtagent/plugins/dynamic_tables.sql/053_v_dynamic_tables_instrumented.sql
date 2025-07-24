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
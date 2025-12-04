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
-- APP.P_REFRESH_RECENT_QUERIES() will recreate two transient tables:
-- * APP.TMP_RECENT_QUERIES materializing current data in the APP.V_QUERY_HISTORY_INSTRUMENTED view
-- * APP.TMP_QUERY_OPERATOR_STATS where results from calling GET_QUERY_OPERATOR_STATS() per each query are kept
-- both tables are created to have a cached data which Dynatrace Snowflake Observability Agent can send, especially when recursively sending query log as spans
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- initializing TMP_RECENT_QUERIES so that we don't have to call this procedure during the deploy time
-- FIXME in DP-11368
EXECUTE IMMEDIATE $$
BEGIN
if ( not exists (
    select 1
    from INFORMATION_SCHEMA.COLUMNS
    where TABLE_CATALOG = 'DTAGENT_DB'
    and TABLE_SCHEMA = 'APP'
    and TABLE_NAME = 'TMP_RECENT_QUERIES'
    and COLUMN_NAME = 'TIMESTAMP'
))
then
    -- Add the column
    drop table if exists DTAGENT_DB.APP.TMP_RECENT_QUERIES;
    return 'Old version of TMP_RECENT_QUERIES dropped';
else
    return 'Already on new version of TMP_RECENT_QUERIES';
end if;
EXCEPTION
when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    return SQLERRM;
END;
$$
;

create or replace transient table DTAGENT_DB.APP.TMP_RECENT_QUERIES DATA_RETENTION_TIME_IN_DAYS = 0 as select *, false as IS_PARENT, false as IS_ROOT from APP.V_QUERY_HISTORY_INSTRUMENTED limit 0;
grant select on table DTAGENT_DB.APP.TMP_RECENT_QUERIES to role DTAGENT_VIEWER;

-- initializing TMP_QUERY_OPERATOR_STATS so that we don't have to call this procedure during the deploy time
create or replace transient table DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS (QUERY_ID varchar, QUERY_OPERATOR_STATS array) DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS to role DTAGENT_VIEWER;


create or replace procedure DTAGENT_DB.APP.P_REFRESH_RECENT_QUERIES()
returns text
language sql
execute as owner
as
$$
DECLARE
    in_tmp_table_reset      TEXT DEFAULT 'insert into DTAGENT_DB.APP.TMP_RECENT_QUERIES select *, false as IS_PARENT, false as IS_ROOT from DTAGENT_DB.APP.V_QUERY_HISTORY_INSTRUMENTED;';
    up_tmp_table_is_parent  TEXT DEFAULT 'update DTAGENT_DB.APP.TMP_RECENT_QUERIES set IS_PARENT = TRUE where QUERY_ID in (select distinct PARENT_QUERY_ID from DTAGENT_DB.APP.TMP_RECENT_QUERIES);';
    up_tmp_table_is_root    TEXT DEFAULT 'update DTAGENT_DB.APP.TMP_RECENT_QUERIES set IS_ROOT = TRUE where PARENT_QUERY_ID is null or PARENT_QUERY_ID not in (select distinct QUERY_ID from DTAGENT_DB.APP.TMP_RECENT_QUERIES);';

    tr_tmp_op_stats         TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS;';
    tr_tmp_table_recent     TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_RECENT_QUERIES;';

    c_queries_to_analyze    CURSOR FOR select
                                             QUERY_ID,
                                             METRICS['snowflake.time.execution'] as execution_time
                                       from  APP.TMP_RECENT_QUERIES t
                                       where DIMENSIONS['db.operation.name'] in ( 'SELECT', 'INSERT', 'UPDATE')
                                         and DIMENSIONS['db.user'] not in ('SYSTEM')
                                        -- only affected queries should be analyzed
                                         and (
                                                (
                                                METRICS['snowflake.data.spilled.local'] > 0 or
                                                METRICS['snowflake.data.spilled.remote'] > 0 or
                                                METRICS['snowflake.time.queued.overload'] > 0 or
                                                METRICS['snowflake.time.queued.provisioning'] > 0 or
                                                METRICS['snowflake.partitions.scanned'] > 0.9*METRICS['snowflake.partitions.total'] or
                                                METRICS['snowflake.time.transaction_blocked'] > 0 or
                                                METRICS['snowflake.time.repair'] > 0
                                                )
                                            or execution_time > APP.F_GET_CONFIG_VALUE('plugins.query_history.slow_queries_threshold', 10000)::int
                                            )
                                       qualify ROW_NUMBER() OVER (order by execution_time desc) < APP.F_GET_CONFIG_VALUE('plugins.query_history.slow_queries_to_analyze_limit', 100)::int
                                       order by execution_time desc
                                       ;
    c_query_operator_stats  CURSOR FOR WITH
                                          cte_operator_stats AS (
                                            SELECT
                                                query_id,
                                                step_id,
                                                operator_id,
                                                parent_operators,
                                                operator_type,
                                                operator_statistics,
                                                execution_time_breakdown,
                                                operator_attributes
                                            FROM TABLE( GET_QUERY_OPERATOR_STATS(?))
                                        )
                                        , cte_operator_stat_metrics AS (
                                            SELECT
                                                t.query_id                                                   AS query_id,
                                                t.step_id                                                    AS step_id,
                                                t.operator_id                                                AS operator_id,
                                                10000*t.step_id + t.operator_id                              AS operator_number,
                                                t.execution_time_breakdown:"overall_percentage"::float       AS time_perc,
                                                time_perc * qh.METRICS['snowflake.time.execution']           AS step_exec_time,
                                                sum(step_exec_time) OVER (ORDER BY operator_number desc)     AS time_since_start,
                                                to_timestamp((qh.START_TIME/1000000000
                                                            + time_since_start
                                                            - step_exec_time)::int)                          AS event_start_time,
                                                to_varchar(t.parent_operators)                               AS parent_operators,
                                                t.operator_type                                              AS operator_type,
                                                t.operator_statistics                                        AS operator_statistics,
                                                t.execution_time_breakdown                                   AS execution_time_breakdown,
                                                t.operator_attributes                                        AS operator_attributes
                                            FROM cte_operator_stats t
                                            INNER JOIN DTAGENT_DB.APP.TMP_RECENT_QUERIES qh
                                                    ON qh.query_id = t.query_id
                                        )
                                        SELECT
                                        array_agg(
                                            object_construct_keep_null(
                                            'timestamp',                           extract(epoch_nanosecond from event_start_time),
                                            'snowflake.query.id',                  query_id,
                                            'snowflake.query.step.id',             step_id,
                                            'snowflake.query.operator.id',         operator_id,
                                            'snowflake.query.operator.parent_ids', to_varchar(parent_operators),
                                            'snowflake.query.operator.type',       to_varchar(operator_type),
                                            'snowflake.query.operator.stats',      operator_statistics,
                                            'snowflake.query.operator.attributes', operator_attributes,
                                            'snowflake.query.operator.time',       execution_time_breakdown
                                            )
                                        ) AS metrics
                                        FROM cte_operator_stat_metrics
                                        GROUP BY query_id
                                        ;
    query_id                VARCHAR DEFAULT '';
    query_operator_stats    ARRAY;

BEGIN
    EXECUTE IMMEDIATE :tr_tmp_table_recent;
    EXECUTE IMMEDIATE :tr_tmp_op_stats;

    -- initializing and populating TMP_RECENT_QUERIES
    EXECUTE IMMEDIATE :in_tmp_table_reset;
    EXECUTE IMMEDIATE :up_tmp_table_is_parent;
    EXECUTE IMMEDIATE :up_tmp_table_is_root;

    -- populating TMP_QUERY_OPERATOR_STATS
    FOR query IN c_queries_to_analyze DO
        query_id := query."QUERY_ID";
        OPEN c_query_operator_stats USING (query_id);
            FETCH c_query_operator_stats INTO query_operator_stats;
            IF (query_operator_stats IS NOT NULL) THEN
                INSERT INTO APP.TMP_QUERY_OPERATOR_STATS(query_id, query_operator_stats) SELECT :query_id, :query_operator_stats;
                UPDATE APP.TMP_RECENT_QUERIES SET
                    ATTRIBUTES = OBJECT_INSERT(ATTRIBUTES, 'snowflake.query.with_operator_stats', TRUE, TRUE)
                WHERE QUERY_ID = :query_id;
            END IF;
        CLOSE c_query_operator_stats;
    END FOR;

    RETURN 'tables APP.TMP_RECENT_QUERIES, APP.TMP_QUERY_OPERATOR_STATS updated';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return sqlerrm;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_REFRESH_RECENT_QUERIES() to role DTAGENT_VIEWER;
alter procedure DTAGENT_DB.APP.P_REFRESH_RECENT_QUERIES() set LOG_LEVEL = WARN;

-- enabling to see redacted queries

use role ACCOUNTADMIN;
alter ACCOUNT set ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR=TRUE;

/*

use role accountadmin;
select *
from DTAGENT_DB.STATUS.EVENT_LOG
-- where
--   SCOPE['name'] = 'DTAGENT'
--   and RECORD['severity_text'] = 'DEBUG'
--   and RECORD_TYPE = 'LOG'
order by timestamp desc
limit 10;

 */


use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_RECENT_QUERIES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS to role DTAGENT_ADMIN copy current grants;

-- call DTAGENT_DB.APP.P_REFRESH_RECENT_QUERIES();


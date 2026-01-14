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
-- APP.V_ACTIVE_QUERIES_INSTRUMENTED() takes list of  queries and all their information from APP.V_ACTIVE_QUERIES()
-- and translates into actual semantics expected by our metrics, spans, etc.
-- It delivers information ready to be consumed and sent over by DTAGENT_DB.APP.DTAGENT()
-- !!!
-- WARNING: ensure you keep instruments-def.yml and this function in sync !!!
-- !!!
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED()
returns table (
    TIMESTAMP TIMESTAMP_LTZ,
    query_id VARCHAR,
    session_id NUMBER,
    name VARCHAR,
    _message VARCHAR,
    start_time NUMBER,
    end_time NUMBER,
    dimensions object,
    attributes object,
    metrics object
)
language sql
execute as caller
AS
$$
DECLARE
    c_active_queries_instrumented CURSOR FOR
        with cte_all_queries as (
            (
                select * from TABLE(DTAGENT_DB.APP.F_GET_RUNNING_QUERIES())
            )
            union all
            (
                select * from TABLE(DTAGENT_DB.APP.F_GET_FINISHED_QUERIES())
            )
        )
        , cte_active_queries as (
            select
                START_TIME,
                END_TIME,

                QUERY_ID,
                SESSION_ID,
                DATABASE_NAME,
                SCHEMA_NAME,

                QUERY_TEXT,
                QUERY_TYPE,
                QUERY_TAG,
                QUERY_HASH,
                QUERY_HASH_VERSION,
                QUERY_PARAMETERIZED_HASH,
                QUERY_PARAMETERIZED_HASH_VERSION,

                USER_NAME,
                ROLE_NAME,

                WAREHOUSE_NAME,
                WAREHOUSE_TYPE,

                EXECUTION_STATUS,
                ERROR_CODE,
                ERROR_MESSAGE,

                // metrics
                RUNNING_TIME,
                EXECUTION_TIME,
                COMPILATION_TIME,
                TOTAL_ELAPSED_TIME,
                BYTES_WRITTEN_TO_RESULT,
                ROWS_WRITTEN_TO_RESULT,
            from cte_all_queries aq
            where
                ( array_size(DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.active_queries.report_execution_status', [])) = 0
            or array_contains(EXECUTION_STATUS::variant, DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.active_queries.report_execution_status', [])::array) )
        )
        select
            qh.END_TIME::timestamp_ltz                                                                                          as TIMESTAMP,

            qh.query_id                                                                                                         as QUERY_ID,
            qh.session_id                                                                                                       as SESSION_ID,

            CONCAT(
                'SQL query ',
                qh.execution_status,
                ' at ',
                COALESCE(qh.database_name, '')
            )                                                                                                                   as NAME,
            NAME                                                                                                                as _MESSAGE,

            -- start_time, end_time
            extract(epoch_nanosecond from qh.start_time)                                                                        as START_TIME,
            extract(epoch_nanosecond from qh.end_time)                                                                          as END_TIME,

            -- metric and span dimensions
            OBJECT_CONSTRUCT(
                'db.namespace',                                             qh.database_name,
                'snowflake.warehouse.name',                                 qh.warehouse_name,
                'db.user',                                                  qh.user_name,
                'snowflake.role.name',                                      qh.role_name,
                'snowflake.query.execution_status',                         qh.execution_status
            )                                                                                                                   as DIMENSIONS,
            -- other attributes
            OBJECT_CONSTRUCT(
                'db.query.text',                                            qh.query_text,
                'db.operation.name',                                        qh.query_type,
                'session.id',                                               qh.session_id,
                'snowflake.query.id',                                       qh.query_id,
                'snowflake.query.tag',                                      qh.query_tag,
                'snowflake.query.hash',                                     qh.query_hash,
                'snowflake.query.hash_version',                             qh.query_hash_version,
                'snowflake.query.parametrized_hash',                        qh.query_parameterized_hash,
                'snowflake.query.parametrized_hash_version',                qh.query_parameterized_hash_version,
                'snowflake.error.code',                                     qh.error_code,
                'snowflake.error.message',                                  qh.error_message,
                'snowflake.warehouse.type',                                 qh.warehouse_type,
                'snowflake.schema.name',                                    qh.schema_name
            )                                                                                                                   as ATTRIBUTES,
            -- metrics
            OBJECT_CONSTRUCT(
                'snowflake.time.running',                                   qh.running_time,
                'snowflake.time.execution',                                 qh.execution_time,
                'snowflake.time.compilation',                               qh.compilation_time,
                'snowflake.time.total_elapsed',                             qh.total_elapsed_time,
                'snowflake.data.written_to_result',                         qh.bytes_written_to_result,
                'snowflake.rows.written_to_result',                         qh.rows_written_to_result
            )                                                                                                                   as METRICS
        from
            cte_active_queries qh
        order by
            TIMESTAMP asc;

BEGIN
    OPEN c_active_queries_instrumented;

    RETURN TABLE(RESULTSET_FROM_CURSOR(c_active_queries_instrumented));
END;
$$
;
grant usage on procedure DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED() to role DTAGENT_VIEWER;


/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from TABLE(DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED())
limit 10;
 */
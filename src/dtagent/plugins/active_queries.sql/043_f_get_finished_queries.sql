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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.F_GET_FINISHED_QUERIES()
returns table (
    start_time TIMESTAMP_LTZ,
    end_time TIMESTAMP_LTZ,
    query_id VARCHAR,
    session_id NUMBER,
    database_name VARCHAR,
    schema_name VARCHAR,
    query_text VARCHAR,
    query_type VARCHAR,
    query_tag VARCHAR,
    query_hash VARCHAR,
    query_hash_version NUMBER,
    query_parameterized_hash VARCHAR,
    query_parameterized_hash_version NUMBER,
    user_name VARCHAR,
    role_name VARCHAR,
    warehouse_name VARCHAR,
    warehouse_type VARCHAR,
    execution_status VARCHAR,
    error_code NUMBER,
    error_message VARCHAR,
    compilation_time NUMBER,
    total_elapsed_time NUMBER,
    execution_time NUMBER,
    running_time NUMBER,
    bytes_written_to_result NUMBER,
    rows_written_to_result NUMBER
)
language sql
execute as caller
AS
$$
DECLARE
    cfg CURSOR  FOR SELECT not fast_mode,
                            greatest(
                                  timeadd(minute, -1, DTAGENT_DB.APP.F_LAST_PROCESSED_TS('active_queries'))
                                , timeadd(hour, -1, current_timestamp()))                         AS end_time_start_range
                   FROM (SELECT
                        DTAGENT_DB.APP.F_GET_CONFIG_VALUE('plugins.active_queries.fast_mode', true::variant)::boolean AS fast_mode);
    res         RESULTSET;
    run_query   BOOLEAN;
    ts_end_time TIMESTAMP_LTZ;
BEGIN
    OPEN cfg;
    FETCH cfg INTO run_query, ts_end_time;
    CLOSE cfg;

    res := (
        SELECT
            start_time::timestamp_ltz,
            end_time::timestamp_ltz,
            query_id::varchar,
            session_id::number,
            database_name::varchar,
            schema_name::varchar,
            query_text::varchar,
            query_type::varchar,
            query_tag::varchar,
            query_hash::varchar,
            query_hash_version::number,
            query_parameterized_hash::varchar,
            query_parameterized_hash_version::number,
            user_name::varchar,
            role_name::varchar,
            warehouse_name::varchar,
            warehouse_type::varchar,
            execution_status::varchar,
            error_code::number,
            error_message::varchar,
            compilation_time::number,
            IFF(execution_status in ('RUNNING', 'QUEUED', 'RESUMING_WAREHOUSE') or 
                coalesce(total_elapsed_time, -1) < 0, 
                null, 
                total_elapsed_time)::number                                             as total_elapsed_time,
            IFF(execution_status in ('RUNNING', 'QUEUED', 'RESUMING_WAREHOUSE') or 
                coalesce(execution_time, -1) < 0, 
                null, 
                execution_time)::number                                                 as execution_time,
            null::number as running_time,
            bytes_written_to_result::number,
            rows_written_to_result::number
        FROM TABLE (INFORMATION_SCHEMA.QUERY_HISTORY(
                    END_TIME_RANGE_START => :ts_end_time, 
                    INCLUDE_CLIENT_GENERATED_STATEMENT => true,
                    RESULT_LIMIT => 10000)) 
        WHERE :run_query
    );


    RETURN TABLE(res);
END;
$$;

grant usage on procedure DTAGENT_DB.APP.F_GET_FINISHED_QUERIES() to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER; use schema DTAGENT_DB.APP; use warehouse DTAGENT_WH;
SELECT * FROM TABLE(DTAGENT_DB.APP.F_GET_FINISHED_QUERIES());
*/


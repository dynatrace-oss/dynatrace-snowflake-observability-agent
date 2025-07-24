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
-- APP.UPDATE_PROCESSED_QUERIES() will update cache with analyzed queries in STATUS.PROCESSED_QUERIES_CACHE 
-- and will log number of successfully analyzed and problematic ones in STATUS.PROCESSED_MEASUREMENTS_LOG 
-- 
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace procedure DTAGENT_DB.STATUS.UPDATE_PROCESSED_QUERIES(query_ids text, processing_errors_count int, span_events_added int)
returns int
language sql
as
$$
declare
    inserted_queries    int;
    last_timestamp      timestamp_ltz;
    c_last_timestamp    CURSOR FOR select max(start_time) as last_timestamp from STATUS.PROCESSED_QUERIES_CACHE;
begin
    insert into STATUS.PROCESSED_QUERIES_CACHE (
        start_time,
        query_id,
        session_id,
        processed_time
    )
    WITH cte_query_ids AS (
        select 
            t.value as query_id
        from 
            table(split_to_table(:query_ids, '|')) as t
    )
    select 
        qh.start_time,
        qh.query_id,
        qh.session_id,
        current_timestamp
    from
        SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh
    where
        qh.query_id in (select query_id from cte_query_ids)
    and qh.query_id not in (select query_id from STATUS.PROCESSED_QUERIES_CACHE)
    and qh.start_time > timeadd(hour, -2, current_timestamp)
    ;

    inserted_queries := SQLROWCOUNT;
    
    open c_last_timestamp;
    fetch c_last_timestamp into last_timestamp;
    close c_last_timestamp;

    call STATUS.LOG_PROCESSED_MEASUREMENTS(
        'query_history',
        :last_timestamp,
        NULL,
        object_construct(
            'queries',      :inserted_queries,
            'errors',       :processing_errors_count,
            'span_events',  :span_events_added 
        )::text
    );

    delete
    from STATUS.PROCESSED_QUERIES_CACHE
    where start_time < timeadd(hour, -4, current_timestamp);

    return inserted_queries;
end;
$$
;
grant usage on procedure DTAGENT_DB.STATUS.UPDATE_PROCESSED_QUERIES(text, int, int) to role DTAGENT_VIEWER;
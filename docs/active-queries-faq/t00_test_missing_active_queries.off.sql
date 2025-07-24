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
-- Copyright (c) 2025 Dynatrace LLC.  All rights reserved.

-- This is a script for testing if given query_id is present in the query history reported via information schema function, and eventually through active_queries plugin.
use role DTAGENT_ADMIN; use warehouse DTAGENT_WH; use schema DTAGENT_DB.PUBLIC;

-- 
-- definition of helper function for checking if query_id is present in the query history
-- and if so, return the query_id and the time range of the query
-- and the warehouse name
-- and the query text
-- 
create or replace procedure PUBLIC.P_FIND_QUERY(query_id varchar)
returns table (
  query_id VARCHAR,
  start_time TIMESTAMP_LTZ,
  end_time TIMESTAMP_LTZ,
  warehouse_name VARCHAR,
  query_text VARCHAR,
  query_found BOOLEAN,
  queries_count NUMBER,
  min_end_time TIMESTAMP_LTZ,
  max_end_time TIMESTAMP_LTZ    
)
language sql
execute as caller
as
--$$
DECLARE
    c_query_info        CURSOR FOR select query_id, start_time, end_time, warehouse_name, query_text
                                     from snowflake.account_usage.query_history
                                    where query_id = ?;

    res                 RESULTSET;
    s_query_id          VARCHAR;
    t_start_time        TIMESTAMP_LTZ;
    t_end_time          TIMESTAMP_LTZ;
    s_warehouse_name    VARCHAR;
    s_query_text        VARCHAR;
BEGIN

    OPEN c_query_info USING (query_id);
    FETCH c_query_info INTO s_query_id, t_start_time, t_end_time, s_warehouse_name, s_query_text;
    CLOSE c_query_info;

    res := (
        SELECT 
            :s_query_id                         as query_id,                    
            :t_start_time                       as start_time,
            :t_end_time                         as end_time,
            :s_warehouse_name                   as warehouse_name,
            :s_query_text                       as query_text,
            BOOLOR_AGG(query_id  = :s_query_id) as query_found,
            count(*)::NUMBER                    as queries_count,
            min(end_time)::TIMESTAMP_LTZ        as min_end_time,
            max(end_time)::TIMESTAMP_LTZ        as max_end_time
         FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
                        END_TIME_RANGE_START => TIMEADD(minute, -2, :t_end_time), 
                        END_TIME_RANGE_END   => TIMEADD(minute,  2, :t_end_time),
                        INCLUDE_CLIENT_GENERATED_STATEMENT => true,
                        RESULT_LIMIT => 10000))
        GROUP BY ALL    
    );
    RETURN TABLE(res);
;
END
--$$
;


grant usage on procedure PUBLIC.P_FIND_QUERY(varchar) to role DTAGENT_VIEWER;

-----------------------------------------------------------------------------------------
-- This is a test which uses the helper function to check if given QUERY_IDs are present
-----------------------------------------------------------------------------------------

/* HINT If running this test does not return results, i.e., query_found is FALSE, then try to re-run this test as ACCOUNTADMIN */
-- truncate TMP_QUERY_FIND_RESULTS;
-- use role ACCOUNTADMIN;

DECLARE
    cur CURSOR FOR SELECT * FROM TABLE(FLATTEN(ARRAY_CONSTRUCT(
        /* HINT list your query ids for checking here */
        '01bc0159-0414-ee68-0047-e38331519c8e',
        '01bc0159-0414-ee68-0047-e38331519c82',
        ''
    )));
    s_sth varchar default '';
    res RESULTSET;
BEGIN
    
    CREATE TEMP TABLE if not exists TMP_QUERY_FIND_RESULTS (
      query_id VARCHAR,
      start_time TIMESTAMP_LTZ,
      end_time TIMESTAMP_LTZ,
      warehouse_name VARCHAR,
      query_text VARCHAR,
      query_found BOOLEAN,
      queries_count NUMBER,
      min_end_time TIMESTAMP_LTZ,
      max_end_time TIMESTAMP_LTZ      
    );

    FOR v IN cur DO 
        s_sth := v.value;
        call public.p_find_query(:s_sth);
        
        INSERT INTO TMP_QUERY_FIND_RESULTS SELECT * FROM TABLE(result_scan(last_query_id()));
    END FOR;

    return s_sth;
END;

select * from TMP_QUERY_FIND_RESULTS;

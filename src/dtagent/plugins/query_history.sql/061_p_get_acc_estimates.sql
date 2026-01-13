use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- creating table  DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES to ensure it exists when deploying fresh
create or replace transient table DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES (QUERY_ID varchar, ATTRIBUTES object) DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES to role DTAGENT_VIEWER;


create or replace procedure DTAGENT_DB.APP.P_GET_ACCELERATION_ESTIMATES()
returns text
language sql
execute as owner
as
$$
DECLARE
    truncate_tmp            TEXT DEFAULT 'truncate table DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES;';

    select_for_res_set      TEXT;
    c_queries_to_analyze    CURSOR FOR select query_id,
                                              METRICS['snowflake.time.execution']::int as execution_time,
                                       from APP.TMP_RECENT_QUERIES
                                       where execution_time > APP.F_GET_CONFIG_VALUE('plugins.query_history.slow_queries_threshold', 10000)::int
                                         and METRICS['snowflake.data.spilled.local'] = 0
                                         and METRICS['snowflake.data.spilled.remote'] = 0
                                         and METRICS['snowflake.partitions.scanned'] < 0.9*METRICS['snowflake.partitions.total']
                                       qualify ROW_NUMBER() OVER (order by execution_time desc) < APP.F_GET_CONFIG_VALUE('plugins.query_history.slow_queries_to_analyze_limit', 100)::int
                                       order by execution_time desc;

    query_id                VARCHAR DEFAULT '';
BEGIN
    -- initializing TMP_QUERY_ACCELERATION_ESTIMATES
    EXECUTE IMMEDIATE :truncate_tmp;

    FOR query IN c_queries_to_analyze DO
        query_id := query.query_id;
        EXECUTE IMMEDIATE 'select PARSE_JSON(SYSTEM$ESTIMATE_QUERY_ACCELERATION(''' || :query_id || ''')) as json;';
        INSERT INTO DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES(QUERY_ID, ATTRIBUTES)
            select
                t.json:"queryUUID"::varchar,
                OBJECT_CONSTRUCT (
                    'snowflake.query.accel_est.estimated_query_times', t.json:"estimatedQueryTimes",
                    'snowflake.query.accel_est.status', t.json:"status"::varchar,
                    'snowflake.query.accel_est.upper_limit_scale_factor', t.json:"upperLimitScaleFactor"::number
                )
            from table(result_scan(last_query_id())) t;
    END FOR;

    RETURN 'table APP.TMP_QUERY_ACCELERATION_ESTIMATES updated';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GET_ACCELERATION_ESTIMATES() to role DTAGENT_VIEWER;

-- call DTAGENT_DB.APP.P_GET_ACCELERATION_ESTIMATES(1000, 50);

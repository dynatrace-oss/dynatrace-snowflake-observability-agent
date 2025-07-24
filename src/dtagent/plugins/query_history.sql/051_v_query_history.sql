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
-- APP.V_QUERY_HISTORY() looks up for new queries that were not processed yet but finished within last 75 minutes
-- It delivered all information we could get from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY and ACCESS_HISTORY
-- 
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_QUERY_HISTORY
as 
with cte_queries_to_check as (
    select 
        qh.query_id,
        qh.start_time,
        qh.end_time,
        qh.session_id
    from 
        SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh
    where 
        qh.end_time >= timeadd(minute, -120, current_timestamp)
    and qh.query_text is not null
    and qh.query_id not in (
            select query_id 
            from STATUS.PROCESSED_QUERIES_CACHE 
            where processed_time is not null
        )
)
, cte_access_history as (
    select 
        ah.query_id                                                             as query_id,
        ah.query_start_time                                                     as start_time,
        ah.parent_query_id,
        array_distinct(array_agg(CASE WHEN t.VALUE:objectDomain = 'Table' THEN t.VALUE:objectName::varchar ELSE NULL END))
                                                                                as query_tables,
        array_distinct(array_cat(
            array_agg(CASE WHEN t.VALUE:objectDomain = 'View'  THEN t.VALUE:objectName::varchar ELSE NULL END),
            array_agg(CASE WHEN v.VALUE:objectDomain = 'View'  THEN v.VALUE:objectName::varchar ELSE NULL END)
        ))                                                                      as query_views,
        array_distinct(
            array_cat(
                array_agg(
                    split_part(t.VALUE:objectName::varchar, '.', 1)::variant),
                array_agg(
                    split_part(v.VALUE:objectName::varchar, '.', 1)::variant) 
            )
        )                                                                       as query_dbs
    from 
        SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY      ah
    inner join 
        cte_queries_to_check                        cqc
    on cqc.query_id = ah.query_id
    and cqc.start_time = ah.query_start_time,
        TABLE(flatten(ah.base_objects_accessed))    t,
        TABLE(flatten(ah.direct_objects_accessed))  v
    group by all
)
select 
    qh.start_time,
    qh.end_time,

    l.trace,

    qh.query_id,
    ah.parent_query_id,
    qh.session_id,
    qh.database_id,
    qh.schema_id,
    qh.schema_name,

    qh.is_client_generated_statement,
    qh.transaction_id,
    qh.query_hash_version,
    qh.query_parameterized_hash_version,
    qh.role_type,
    qh.secondary_role_stats,

    qh.query_text,
    qh.query_type,
    qh.query_tag,
    qh.query_hash,
    qh.query_parameterized_hash,
    qh.user_name,
    qh.role_name,
    qh.release_version,

    case
        when ah.query_tables is not null and ARRAY_SIZE(ah.query_tables) > 0 
        then GET(ah.query_tables, 0)
        else NULL                -- we use database_name provided by snowflake as the worst case scenario as it can be wrong at times
    end as table_name,           -- this is a primary database name

    case
        when table_name is not null 
        then split_part(table_name, '.', 1)
        else qh.database_name       -- we use database_name provided by snowflake as the worst case scenario as it can be wrong at times
    end as database_name,           -- this is a primary database name

    ah.query_dbs,
    ah.query_tables,
    ah.query_views,
    qh.query_retry_cause,

    qh.warehouse_id,    
    qh.warehouse_type,
    qh.warehouse_size,

    qh.warehouse_name,
    qh.cluster_number,

    qh.execution_status,
    qh.error_code,
    qh.error_message,

    // session

    s.created_on,
    s.authentication_method,
    s.login_event_id,
    s.client_application_id,
    s.client_application_version,
    s.client_environment,
    s.client_build_id,
    s.client_version,
    s.closed_reason,
    
    // metrics

    qh.query_load_percent,

    qh.credits_used_cloud_services,

    qh.total_elapsed_time,
    qh.execution_time,
    qh.child_queries_wait_time,
    qh.compilation_time,
    qh.transaction_blocked_time,
    qh.list_external_files_time,
    qh.queued_overload_time,
    qh.queued_provisioning_time,
    qh.queued_repair_time,
    
    qh.bytes_spilled_to_local_storage,
    qh.bytes_spilled_to_remote_storage,
    qh.bytes_sent_over_the_network,
    qh.inbound_data_transfer_bytes,
    qh.inbound_data_transfer_cloud,
    qh.inbound_data_transfer_region,
    qh.outbound_data_transfer_bytes,
    qh.outbound_data_transfer_cloud,
    qh.outbound_data_transfer_region,
    
    qh.bytes_read_from_result,
    qh.bytes_scanned,
    qh.bytes_written,
    qh.bytes_written_to_result,
    qh.bytes_deleted,
    
    qh.partitions_scanned,
    qh.partitions_total,
    qh.percentage_scanned_from_cache,
    
    qh.query_acceleration_bytes_scanned,
    qh.query_acceleration_partitions_scanned,
    qh.query_acceleration_upper_limit_scale_factor,

    qh.external_function_total_invocations,
    qh.external_function_total_received_bytes,
    qh.external_function_total_received_rows,

    qh.rows_inserted,
    qh.rows_updated,
    qh.rows_deleted,
    qh.rows_unloaded,

    qh.rows_written_to_result,
    qh.query_retry_time,
    
    qh.external_function_total_sent_rows,
    qh.external_function_total_sent_bytes,

    qh.fault_handling_time
from 
    SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY           qh
inner join
    cte_queries_to_check                            cqc
 on  cqc.query_id = qh.query_id
 and cqc.start_time = qh.start_time
left join
    cte_access_history                              ah 
 on  ah.query_id = qh.query_id
 and ah.start_time = qh.start_time
left join
    SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
 on  s.session_id = qh.session_id
 and s.created_on >= timeadd(hour, -24, current_timestamp)
 and ah.parent_query_id is null
left join
    STATUS.EVENT_LOG l
 on l.RECORD_TYPE = 'SPAN'
 and l.RESOURCE_ATTRIBUTES:"snow.query.id"::varchar = qh.query_id
where 
    qh.end_time >= timeadd(minute, -120, current_timestamp)
-- this will ensure we do not report some strange Snowflake-internal queries
and not (qh.QUERY_TEXT = '' and 
         qh.USER_NAME = 'SYSTEM' and
         qh.ROLE_NAME is null and 
         qh.DATABASE_NAME is null and 
         qh.SCHEMA_NAME is null)
;
grant select on table APP.V_QUERY_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * 
from DTAGENT_DB.APP.V_QUERY_HISTORY 
where parent_query_id is not null
limit 10;
 */
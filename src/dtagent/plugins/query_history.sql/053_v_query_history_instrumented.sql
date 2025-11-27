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
-- APP.V_QUERY_HISTORY_INSTRUMENTED() takes list of queries and all their information from APP.V_QUERY_HISTORY()
-- and translates into actual semantics expected by our metrics, spans, etc. 
-- It delivers information ready to be consumed and sent over by DTAGENT_DB.APP.DTAGENT()
-- !!!
-- WARNING: ensure you keep instruments-def.yml and this function in sync !!!
-- !!!
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view APP.V_QUERY_HISTORY_INSTRUMENTED
as
select 
    extract(epoch_nanosecond from qh.start_time)                                                                        as TIMESTAMP,
    qh.query_id                                                                                                         as QUERY_ID,
    qh.parent_query_id                                                                                                  as PARENT_QUERY_ID,
    qh.session_id                                                                                                       as SESSION_ID,
    -- https://opentelemetry.io/docs/concepts/signals/traces/
    -- name
    CONCAT(
        LOWER(qh.query_type),
        ' ',
        COALESCE(qh.database_name, '')
    )                                                                                                                   as NAME,

    CONCAT('New SQL Query at ', coalesce(qh.database_name, ''))                                                         as _MESSAGE,
    -- start_time, end_time
    extract(epoch_nanosecond from qh.start_time)                                                                        as START_TIME,
    extract(epoch_nanosecond from qh.end_time)                                                                          as END_TIME,
    -- status code
    case 
        when qh.execution_status = 'SUCCESS'          then 'OK' 
        when LENGTH(NVL(qh.execution_status, '')) > 0 then 'ERROR'
                                                      else 'UNSET' 
    end                                                                                                                 as STATUS_CODE,
    -- trace and span ids
    qh.trace:span_id::varchar                                                                                           as _SPAN_ID,
    qh.trace:trace_id::varchar                                                                                          as _TRACE_ID,
    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'db.namespace',                                             qh.database_name,
        'db.collection.name',                                       qh.table_name,
        'db.operation.name',                                        qh.query_type,
        'db.snowflake.dbs',                                         qh.query_dbs,
        'db.user',                                                  qh.user_name,
        'snowflake.role.name',                                      qh.role_name,
        'snowflake.warehouse.name',                                 qh.warehouse_name,
        'snowflake.query.execution_status',                         qh.execution_status
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'db.query.text',                                            qh.query_text,
        'db.snowflake.tables',                                      qh.query_tables,
        'db.snowflake.views',                                       qh.query_views,
        'session.id',                                               qh.session_id,
        'event.id',                                                 qh.login_event_id,
        'authentication.type',                                      qh.authentication_method,
        'client.application.id',                                    qh.client_application_id,
        'client.application.version',                               qh.client_application_version,
        'client.environment',                                       qh.client_environment,
        'client.build_id',                                          qh.client_build_id,
        'client.version',                                           qh.client_version,
        'snowflake.cluster_number',                                 qh.cluster_number,
        'snowflake.query.id',                                       qh.query_id,
        'snowflake.query.parent_id',                                qh.parent_query_id,
        'snowflake.query.tag',                                      qh.query_tag,
        'snowflake.query.hash',                                     qh.query_hash,
        'snowflake.query.hash_version',                             qh.query_hash_version,
        'snowflake.query.parametrized_hash',                        qh.query_parameterized_hash,
        'snowflake.query.parametrized_hash_version',                qh.query_parameterized_hash_version,
        'snowflake.error.code',                                     qh.error_code,
        'snowflake.error.message',                                  qh.error_message,
        'snowflake.session.start',                                  qh.created_on,
        'snowflake.session.closed_reason',                          qh.closed_reason,
        'snowflake.query.retry_cause',                              qh.query_retry_cause,
        'snowflake.secondary_role_stats',                           qh.secondary_role_stats,
        'snowflake.role.type',                                      qh.role_type,
        'snowflake.query.transaction_id',                           qh.transaction_id,
        'snowflake.query.is_client_generated',                      qh.is_client_generated_statement,
        'snowflake.release_version',                                qh.release_version,
        'snowflake.query.data_transfer.inbound.region',             qh.inbound_data_transfer_region,
        'snowflake.query.data_transfer.inbound.cloud',              qh.inbound_data_transfer_cloud,
        'snowflake.query.data_transfer.outbound.cloud',             qh.outbound_data_transfer_cloud,
        'snowflake.query.data_transfer.outbound.region',            qh.outbound_data_transfer_region,
        'snowflake.warehouse.cluster.number',                       qh.cluster_number,
        'snowflake.warehouse.type',                                 qh.warehouse_type,
        'snowflake.warehouse.size',                                 qh.warehouse_size,
        'snowflake.warehouse.id',                                   qh.warehouse_id,
        'snowflake.schema.name',                                    qh.schema_name,
        'snowflake.schema.id',                                      qh.schema_id,
        'snowflake.database.id',                                    qh.database_id,
    -- will be filled in in spans
        'dsoa.debug.span.events.added',                        NULL,
        'dsoa.debug.span.events.failed',                       NULL,
    -- will be reported when query acceleration is calculated
        'snowflake.query.accel_est.estimated_query_times',          NULL,
        'snowflake.query.accel_est.status',                         NULL,
        'snowflake.query.accel_est.upper_limit_scale_factor',       NULL,
    -- are reported in logs for query operator stats calculated
        'snowflake.query.operator.id',                              NULL,
        'snowflake.query.step.id',                                  NULL,
        'snowflake.query.operator.type',                            NULL,
        'snowflake.query.operator.parent_ids',                      NULL,
        'snowflake.query.operator.attributes',                      NULL,
        'snowflake.query.operator.stats',                           NULL,
        'snowflake.query.operator.time',                            NULL,
        'snowflake.query.with_operator_stats',                      FALSE
    )                                                                                                                   as ATTRIBUTES,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.data.scanned_from_cache',                        qh.percentage_scanned_from_cache,                
        'snowflake.load.used',                                      qh.query_load_percent,                              
        'snowflake.acceleration.scale_factor.max',                  qh.query_acceleration_upper_limit_scale_factor,     
        'snowflake.time.queued.overload',                           qh.queued_overload_time,                            
        'snowflake.time.queued.provisioning',                       qh.queued_provisioning_time,                        
        'snowflake.time.repair',                                    qh.queued_repair_time,                              
        'snowflake.time.total_elapsed',                             qh.total_elapsed_time,                              
        'snowflake.time.execution',                                 qh.execution_time,                                  
        'snowflake.time.child_queries_wait',                        qh.child_queries_wait_time,                         
        'snowflake.time.compilation',                               qh.compilation_time,                                
        'snowflake.time.transaction_blocked',                       qh.transaction_blocked_time,                        
        'snowflake.time.list_external_files',                       qh.list_external_files_time,
        'snowflake.time.fault_handling',                            qh.fault_handling_time,
        'snowflake.time.retry',                                     qh.query_retry_time,
        'snowflake.credits.cloud_services',                         qh.credits_used_cloud_services,                     
        'snowflake.data.spilled.local',                             qh.bytes_spilled_to_local_storage,                  
        'snowflake.data.spilled.remote',                            qh.bytes_spilled_to_remote_storage,                 
        'snowflake.data.sent_over_the_network',                     qh.bytes_sent_over_the_network,                     
        'snowflake.data.transferred.inbound',                       qh.inbound_data_transfer_bytes,                     
        'snowflake.data.transferred.outbound',                      qh.outbound_data_transfer_bytes,                    
        'snowflake.data.read.from_result',                          qh.bytes_read_from_result,                          
        'snowflake.data.scanned',                                   qh.bytes_scanned,
        'snowflake.data.deleted',                                   qh.bytes_deleted,
        'snowflake.data.written',                                   qh.bytes_written,
        'snowflake.data.written_to_result',                         qh.bytes_written_to_result,                                   
        'snowflake.partitions.scanned',                             qh.partitions_scanned,                              
        'snowflake.partitions.total',                               qh.partitions_total,                                
        'snowflake.acceleration.data.scanned',                      qh.query_acceleration_bytes_scanned,                
        'snowflake.acceleration.partitions.scanned',                qh.query_acceleration_partitions_scanned,           
        'snowflake.external_functions.invocations',                 qh.external_function_total_invocations,             
        'snowflake.external_functions.data.received',               qh.external_function_total_received_bytes,          
        'snowflake.external_functions.rows.received',               qh.external_function_total_received_rows,
        'snowflake.rows.written_to_result',                         qh.rows_written_to_result,
        'snowflake.external_functions.data.sent',                   qh.external_function_total_sent_bytes,
        'snowflake.external_functions.rows.sent',                   qh.external_function_total_sent_rows,
        'snowflake.rows.inserted',                                  qh.rows_inserted,
        'snowflake.rows.updated',                                   qh.rows_updated,
        'snowflake.rows.deleted',                                   qh.rows_deleted,
        'snowflake.rows.unloaded',                                  qh.rows_unloaded
    )                                                                                                                   as METRICS
from 
    APP.V_QUERY_HISTORY qh
;
grant select on table APP.V_QUERY_HISTORY_INSTRUMENTED to role DTAGENT_VIEWER;

/*
use role DTAGENT_VIEWER;
select * 
from APP.V_QUERY_HISTORY_INSTRUMENTED 
where parent_query_id is not null
limit 10;
 */
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
-- APP.F_GET_QUERY_HISTORY() fuses the logic of the former V_QUERY_HISTORY and
-- V_QUERY_HISTORY_INSTRUMENTED views into a single stored procedure callable
-- as a table function: SELECT * FROM TABLE(APP.F_GET_QUERY_HISTORY()).
--
-- Key performance fix (BDX-1965): cutoff_time and max_entries are resolved as
-- scripting-block scalar variables BEFORE the ACCOUNT_USAGE.QUERY_HISTORY scan.
-- When a UDF (F_GET_CONFIG_VALUE) appeared directly in the WHERE clause of a
-- view, Snowflake classified the boundary as non-deterministic at compile time
-- and disabled micro-partition pruning — causing full historical scans that
-- timed out on busy accounts.  With bound scripting variables Snowflake treats
-- the value as a constant and prunes micro-partitions correctly (~3-6 s vs
-- 25+ min).
--
-- max_entries = 0 (default): no LIMIT — return all qualifying rows.
-- max_entries > 0:           ORDER BY execution_time DESC LIMIT :v_max_entries.
--                            QUALIFY / ROW_NUMBER is intentionally avoided as it
--                            forces a full-scan rank before truncation.
--
-- !!!
-- WARNING: keep instruments-def.yml and this procedure in sync !!!
-- !!!
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure APP.F_GET_QUERY_HISTORY()
returns table (
    timestamp                           NUMBER,
    query_id                            VARCHAR,
    parent_query_id                     VARCHAR,
    session_id                          NUMBER,
    name                                VARCHAR,
    _message                            VARCHAR,
    start_time                          NUMBER,
    end_time                            NUMBER,
    status_code                         VARCHAR,
--%PLUGIN:event_log:
    _span_id                            VARCHAR,
    _trace_id                           VARCHAR,
--%:PLUGIN:event_log
    dimensions                          OBJECT,
    attributes                          OBJECT,
    metrics                             OBJECT,
    _total_available                    NUMBER
)
language sql
execute as caller
as
$$
DECLARE
    v_max_entries    INT           DEFAULT CONFIG.F_GET_CONFIG_VALUE('plugins.query_history.max_entries', 0)::int;
    v_max_lookback   INT           DEFAULT CONFIG.F_GET_CONFIG_VALUE('plugins.query_history.max_lookback_minutes', 120)::int;
    v_cutoff         TIMESTAMP_LTZ;
    rs               RESULTSET;
BEGIN
    -- Resolve cutoff: watermark wins if available; fall back to max_lookback.
    -- greatest() ensures we never exceed max_lookback even after a long outage.
    v_cutoff := greatest(
        coalesce(
            (select max(LAST_TIMESTAMP)
             from   STATUS.PROCESSED_MEASUREMENTS_LOG
             where  MEASUREMENTS_SOURCE = 'query_history'),
            dateadd('minute', -v_max_lookback, current_timestamp())
        ),
        dateadd('minute', -v_max_lookback, current_timestamp())
    );

    IF (v_max_entries = 0) THEN
        rs := (
            with cte_access_history as (
                select
                    ah.query_id                                                                 as query_id,
                    ah.query_start_time                                                         as start_time,
                    ah.parent_query_id,
                    array_distinct(array_agg(
                        case when t.value:objectdomain = 'Table'
                             then t.value:objectname::varchar else null end))                   as query_tables,
                    array_distinct(array_cat(
                        array_agg(case when t.value:objectdomain = 'View'
                                       then t.value:objectname::varchar else null end),
                        array_agg(case when v.value:objectdomain = 'View'
                                       then v.value:objectname::varchar else null end)))        as query_views,
                    array_distinct(array_cat(
                        array_agg(split_part(t.value:objectname::varchar, '.', 1)::variant),
                        array_agg(split_part(v.value:objectname::varchar, '.', 1)::variant)))  as query_dbs,
                    any_value(ah.object_modified_by_ddl:"objectDomain"::varchar)               as ddl_target_domain,
                    any_value(ah.object_modified_by_ddl:"objectId"::varchar)                   as ddl_target_id,
                    any_value(ah.object_modified_by_ddl:"objectName"::varchar)                 as ddl_target_name,
                    any_value(ah.object_modified_by_ddl:"operationType"::varchar)              as ddl_operation,
                    any_value(ah.object_modified_by_ddl:"properties")                          as ddl_properties
                from
                    SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY              ah,
                    table(flatten(ah.base_objects_accessed))            t,
                    table(flatten(ah.direct_objects_accessed))          v
                where ah.query_start_time >= :v_cutoff
                group by all
            )
            select
                extract(epoch_nanosecond from qh.start_time)                                   as timestamp,
                qh.query_id                                                                     as query_id,
                ah.parent_query_id                                                              as parent_query_id,
                qh.session_id                                                                   as session_id,
                concat(lower(qh.query_type), ' ', coalesce(
                    case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                         then split_part(get(ah.query_tables, 0)::varchar, '.', 1)
                         else qh.database_name end, ''))                                       as name,
                concat('New SQL Query at ', coalesce(
                    case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                         then split_part(get(ah.query_tables, 0)::varchar, '.', 1)
                         else qh.database_name end, ''))                                       as _message,
                extract(epoch_nanosecond from qh.start_time)                                   as start_time,
                extract(epoch_nanosecond from qh.end_time)                                     as end_time,
                case
                    when qh.execution_status = 'SUCCESS'          then 'OK'
                    when length(nvl(qh.execution_status, '')) > 0 then 'ERROR'
                                                                  else 'UNSET'
                end                                                                            as status_code,
--%PLUGIN:event_log:
                l.trace:span_id::varchar                                                       as _span_id,
                l.trace:trace_id::varchar                                                      as _trace_id,
--%:PLUGIN:event_log
                OBJECT_CONSTRUCT(
                    'db.namespace',                    qh.database_name,
                    'db.collection.name',              split_part(
                        case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                             then get(ah.query_tables, 0)::varchar else null end, '.', -1),
                    'snowflake.table.full_name',       case when ah.query_tables is not null
                                                            and array_size(ah.query_tables) > 0
                                                       then get(ah.query_tables, 0)::varchar else null end,
                    'db.operation.name',               qh.query_type,
                    'db.snowflake.dbs',                ah.query_dbs,
                    'db.user',                         qh.user_name,
                    'snowflake.role.name',             qh.role_name,
                    'snowflake.warehouse.name',        qh.warehouse_name,
                    'snowflake.query.execution_status', qh.execution_status,
                    'snowflake.user.type',             qh.user_type
                )                                                                              as DIMENSIONS,
                OBJECT_CONSTRUCT(
                    'db.query.text',                   app.f_obfuscate_query_text(
                                                           qh.query_text,
                                                           config.f_get_config_value(
                                                               'dsoa.plugins.query_history.obfuscation_mode',
                                                               to_variant('off'))),
                    'db.snowflake.tables',             ah.query_tables,
                    'db.snowflake.views',              ah.query_views,
                    'snowflake.session.id',            qh.session_id,
                    'event.id',                        s.login_event_id,
                    'authentication.type',             s.authentication_method,
                    'client.application.id',           s.client_application_id,
                    'client.application.version',      s.client_application_version,
                    'client.environment',              s.client_environment,
                    'client.build_id',                 s.client_build_id,
                    'client.version',                  s.client_version,
                    'snowflake.cluster_number',        qh.cluster_number,
                    'snowflake.query.id',              qh.query_id,
                    'snowflake.query.parent_id',       ah.parent_query_id,
                    'snowflake.query.tag',             qh.query_tag,
                    'snowflake.query.hash',            qh.query_hash,
                    'snowflake.query.hash_version',    qh.query_hash_version,
                    'snowflake.query.parametrized_hash', qh.query_parameterized_hash,
                    'snowflake.query.parametrized_hash_version', qh.query_parameterized_hash_version,
                    'snowflake.error.code',            qh.error_code,
                    'snowflake.error.message',         app.f_obfuscate_query_text(
                                                           qh.error_message,
                                                           config.f_get_config_value(
                                                               'dsoa.plugins.query_history.obfuscation_mode',
                                                               to_variant('off'))),
                    'snowflake.session.start',         s.created_on,
                    'snowflake.session.closed_reason', s.closed_reason,
                    'snowflake.query.retry_cause',     qh.query_retry_cause,
                    'snowflake.secondary_role_stats',  qh.secondary_role_stats,
                    'snowflake.role.type',             qh.role_type,
                    'snowflake.query.transaction_id',  qh.transaction_id,
                    'snowflake.query.is_client_generated', qh.is_client_generated_statement,
                    'snowflake.release_version',       qh.release_version,
                    'snowflake.query.data_transfer.inbound.region',  qh.inbound_data_transfer_region,
                    'snowflake.query.data_transfer.inbound.cloud',   qh.inbound_data_transfer_cloud,
                    'snowflake.query.data_transfer.outbound.cloud',  qh.outbound_data_transfer_cloud,
                    'snowflake.query.data_transfer.outbound.region', qh.outbound_data_transfer_region,
                    'snowflake.warehouse.cluster.number', qh.cluster_number,
                    'snowflake.warehouse.type',        qh.warehouse_type,
                    'snowflake.warehouse.size',        qh.warehouse_size,
                    'snowflake.warehouse.id',          qh.warehouse_id,
                    'snowflake.schema.name',           qh.schema_name,
                    'snowflake.schema.id',             qh.schema_id,
                    'snowflake.database.id',           qh.database_id,
                    'snowflake.object.type',           ah.ddl_target_domain,
                    'snowflake.object.id',             ah.ddl_target_id,
                    'snowflake.object.name',           ah.ddl_target_name,
                    'snowflake.object.ddl.operation',  ah.ddl_operation,
                    'snowflake.object.ddl.properties', ah.ddl_properties,
                    'dsoa.debug.span.events.added',    null,
                    'dsoa.debug.span.events.failed',   null,
                    'snowflake.query.accel_est.estimated_query_times', null,
                    'snowflake.query.accel_est.status', null,
                    'snowflake.query.accel_est.upper_limit_scale_factor', null,
                    'snowflake.query.step.operator.id',     null,
                    'snowflake.query.step.id',              null,
                    'snowflake.query.step.operator.type',   null,
                    'snowflake.query.step.operator.parent_ids', null,
                    'snowflake.query.step.operator.attributes', null,
                    'snowflake.query.step.operator.stats',  null,
                    'snowflake.query.step.operator.time_breakdown', null,
                    'snowflake.query.with_operator_stats', false
                )                                                                              as ATTRIBUTES,
                OBJECT_CONSTRUCT(
                    'snowflake.data.scanned_from_cache',           qh.percentage_scanned_from_cache,
                    'snowflake.load.used',                         qh.query_load_percent,
                    'snowflake.acceleration.scale_factor.max',     qh.query_acceleration_upper_limit_scale_factor,
                    'snowflake.time.queued.overload',              qh.queued_overload_time,
                    'snowflake.time.queued.provisioning',          qh.queued_provisioning_time,
                    'snowflake.time.repair',                       qh.queued_repair_time,
                    'snowflake.time.total_elapsed',                qh.total_elapsed_time,
                    'snowflake.time.execution',                    qh.execution_time,
                    'snowflake.time.child_queries_wait',           qh.child_queries_wait_time,
                    'snowflake.time.compilation',                  qh.compilation_time,
                    'snowflake.time.transaction_blocked',          qh.transaction_blocked_time,
                    'snowflake.time.list_external_files',          qh.list_external_files_time,
                    'snowflake.time.fault_handling',               qh.fault_handling_time,
                    'snowflake.time.retry',                        qh.query_retry_time,
                    'snowflake.credits.cloud_services',            qh.credits_used_cloud_services,
--%OPTION:query_cost_attribution:
                    'snowflake.credits.attributed_compute',        qah.credits_attributed_compute,
                    'snowflake.credits.query_acceleration',        qah.credits_used_query_acceleration,
--%:OPTION:query_cost_attribution
                    'snowflake.data.spilled.local',                qh.bytes_spilled_to_local_storage,
                    'snowflake.data.spilled.remote',               qh.bytes_spilled_to_remote_storage,
                    'snowflake.data.sent_over_the_network',        qh.bytes_sent_over_the_network,
                    'snowflake.data.transferred.inbound',          qh.inbound_data_transfer_bytes,
                    'snowflake.data.transferred.outbound',         qh.outbound_data_transfer_bytes,
                    'snowflake.data.read.from_result',             qh.bytes_read_from_result,
                    'snowflake.data.scanned',                      qh.bytes_scanned,
                    'snowflake.data.deleted',                      qh.bytes_deleted,
                    'snowflake.data.written',                      qh.bytes_written,
                    'snowflake.data.written_to_result',            qh.bytes_written_to_result,
                    'snowflake.partitions.scanned',                qh.partitions_scanned,
                    'snowflake.partitions.total',                  qh.partitions_total,
                    'snowflake.acceleration.data.scanned',         qh.query_acceleration_bytes_scanned,
                    'snowflake.acceleration.partitions.scanned',   qh.query_acceleration_partitions_scanned,
                    'snowflake.external_functions.invocations',    qh.external_function_total_invocations,
                    'snowflake.external_functions.data.received',  qh.external_function_total_received_bytes,
                    'snowflake.external_functions.rows.received',  qh.external_function_total_received_rows,
                    'snowflake.rows.written_to_result',            qh.rows_written_to_result,
                    'snowflake.external_functions.data.sent',      qh.external_function_total_sent_bytes,
                    'snowflake.external_functions.rows.sent',      qh.external_function_total_sent_rows,
                    'snowflake.rows.inserted',                     qh.rows_inserted,
                    'snowflake.rows.updated',                      qh.rows_updated,
                    'snowflake.rows.deleted',                      qh.rows_deleted,
                    'snowflake.rows.unloaded',                     qh.rows_unloaded
                )                                                                              as METRICS,
                count(*) over ()                                                               as _total_available
            from
                SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY                  qh
            left join
                cte_access_history                                      ah
              on  ah.query_id    = qh.query_id
              and ah.start_time  = qh.start_time
            left join
                SNOWFLAKE.ACCOUNT_USAGE.SESSIONS                        s
              on  s.session_id   = qh.session_id
              and s.created_on  >= timeadd(hour, -24, current_timestamp())
              and ah.parent_query_id is null
--%PLUGIN:event_log:
            left join
                STATUS.EVENT_LOG                                        l
              on  l.record_type  = 'SPAN'
              and l.resource_attributes:"snow.query.id"::varchar = qh.query_id
--%:PLUGIN:event_log
--%OPTION:query_cost_attribution:
            left join
                SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY       qah
              on  qah.query_id   = qh.query_id
--%:OPTION:query_cost_attribution
            where qh.end_time >= :v_cutoff
              and qh.query_text is not null
              and qh.query_id not in (
                      select query_id
                      from   STATUS.PROCESSED_QUERIES_CACHE
                      where  processed_time is not null
                  )
              -- exclude internal Snowflake system queries
              and not (    qh.query_text  = ''
                       and qh.user_name   = 'SYSTEM'
                       and qh.role_name   is null
                       and qh.database_name is null
                       and qh.schema_name  is null)
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_warehouses')) = 0
                      or qh.warehouse_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_warehouses')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_warehouses')) = 0
                      or not qh.warehouse_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_warehouses')
                  )
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_databases')) = 0
                      or qh.database_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_databases')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_databases')) = 0
                      or not qh.database_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_databases')
                  )
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_users')) = 0
                      or qh.user_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_users')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_users')) = 0
                      or not qh.user_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_users')
                  )
        );
    ELSE
        rs := (
            with cte_access_history as (
                select
                    ah.query_id                                                                 as query_id,
                    ah.query_start_time                                                         as start_time,
                    ah.parent_query_id,
                    array_distinct(array_agg(
                        case when t.value:objectdomain = 'Table'
                             then t.value:objectname::varchar else null end))                   as query_tables,
                    array_distinct(array_cat(
                        array_agg(case when t.value:objectdomain = 'View'
                                       then t.value:objectname::varchar else null end),
                        array_agg(case when v.value:objectdomain = 'View'
                                       then v.value:objectname::varchar else null end)))        as query_views,
                    array_distinct(array_cat(
                        array_agg(split_part(t.value:objectname::varchar, '.', 1)::variant),
                        array_agg(split_part(v.value:objectname::varchar, '.', 1)::variant)))  as query_dbs,
                    any_value(ah.object_modified_by_ddl:"objectDomain"::varchar)               as ddl_target_domain,
                    any_value(ah.object_modified_by_ddl:"objectId"::varchar)                   as ddl_target_id,
                    any_value(ah.object_modified_by_ddl:"objectName"::varchar)                 as ddl_target_name,
                    any_value(ah.object_modified_by_ddl:"operationType"::varchar)              as ddl_operation,
                    any_value(ah.object_modified_by_ddl:"properties")                          as ddl_properties
                from
                    SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY              ah,
                    table(flatten(ah.base_objects_accessed))            t,
                    table(flatten(ah.direct_objects_accessed))          v
                where ah.query_start_time >= :v_cutoff
                group by all
            )
            select
                extract(epoch_nanosecond from qh.start_time)                                   as timestamp,
                qh.query_id                                                                     as query_id,
                ah.parent_query_id                                                              as parent_query_id,
                qh.session_id                                                                   as session_id,
                concat(lower(qh.query_type), ' ', coalesce(
                    case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                         then split_part(get(ah.query_tables, 0)::varchar, '.', 1)
                         else qh.database_name end, ''))                                       as name,
                concat('New SQL Query at ', coalesce(
                    case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                         then split_part(get(ah.query_tables, 0)::varchar, '.', 1)
                         else qh.database_name end, ''))                                       as _message,
                extract(epoch_nanosecond from qh.start_time)                                   as start_time,
                extract(epoch_nanosecond from qh.end_time)                                     as end_time,
                case
                    when qh.execution_status = 'SUCCESS'          then 'OK'
                    when length(nvl(qh.execution_status, '')) > 0 then 'ERROR'
                                                                  else 'UNSET'
                end                                                                            as status_code,
--%PLUGIN:event_log:
                l.trace:span_id::varchar                                                       as _span_id,
                l.trace:trace_id::varchar                                                      as _trace_id,
--%:PLUGIN:event_log
                object_construct(
                    'db.namespace',                    qh.database_name,
                    'db.collection.name',              split_part(
                        case when ah.query_tables is not null and array_size(ah.query_tables) > 0
                             then get(ah.query_tables, 0)::varchar else null end, '.', -1),
                    'snowflake.table.full_name',       case when ah.query_tables is not null
                                                            and array_size(ah.query_tables) > 0
                                                       then get(ah.query_tables, 0)::varchar else null end,
                    'db.operation.name',               qh.query_type,
                    'db.snowflake.dbs',                ah.query_dbs,
                    'db.user',                         qh.user_name,
                    'snowflake.role.name',             qh.role_name,
                    'snowflake.warehouse.name',        qh.warehouse_name,
                    'snowflake.query.execution_status', qh.execution_status,
                    'snowflake.user.type',             qh.user_type
                )                                                                              as dimensions,
                object_construct(
                    'db.query.text',                   app.f_obfuscate_query_text(
                                                           qh.query_text,
                                                           config.f_get_config_value(
                                                               'dsoa.plugins.query_history.obfuscation_mode',
                                                               to_variant('off'))),
                    'db.snowflake.tables',             ah.query_tables,
                    'db.snowflake.views',              ah.query_views,
                    'snowflake.session.id',            qh.session_id,
                    'event.id',                        s.login_event_id,
                    'authentication.type',             s.authentication_method,
                    'client.application.id',           s.client_application_id,
                    'client.application.version',      s.client_application_version,
                    'client.environment',              s.client_environment,
                    'client.build_id',                 s.client_build_id,
                    'client.version',                  s.client_version,
                    'snowflake.cluster_number',        qh.cluster_number,
                    'snowflake.query.id',              qh.query_id,
                    'snowflake.query.parent_id',       ah.parent_query_id,
                    'snowflake.query.tag',             qh.query_tag,
                    'snowflake.query.hash',            qh.query_hash,
                    'snowflake.query.hash_version',    qh.query_hash_version,
                    'snowflake.query.parametrized_hash', qh.query_parameterized_hash,
                    'snowflake.query.parametrized_hash_version', qh.query_parameterized_hash_version,
                    'snowflake.error.code',            qh.error_code,
                    'snowflake.error.message',         app.f_obfuscate_query_text(
                                                           qh.error_message,
                                                           config.f_get_config_value(
                                                               'dsoa.plugins.query_history.obfuscation_mode',
                                                               to_variant('off'))),
                    'snowflake.session.start',         s.created_on,
                    'snowflake.session.closed_reason', s.closed_reason,
                    'snowflake.query.retry_cause',     qh.query_retry_cause,
                    'snowflake.secondary_role_stats',  qh.secondary_role_stats,
                    'snowflake.role.type',             qh.role_type,
                    'snowflake.query.transaction_id',  qh.transaction_id,
                    'snowflake.query.is_client_generated', qh.is_client_generated_statement,
                    'snowflake.release_version',       qh.release_version,
                    'snowflake.query.data_transfer.inbound.region',  qh.inbound_data_transfer_region,
                    'snowflake.query.data_transfer.inbound.cloud',   qh.inbound_data_transfer_cloud,
                    'snowflake.query.data_transfer.outbound.cloud',  qh.outbound_data_transfer_cloud,
                    'snowflake.query.data_transfer.outbound.region', qh.outbound_data_transfer_region,
                    'snowflake.warehouse.cluster.number', qh.cluster_number,
                    'snowflake.warehouse.type',        qh.warehouse_type,
                    'snowflake.warehouse.size',        qh.warehouse_size,
                    'snowflake.warehouse.id',          qh.warehouse_id,
                    'snowflake.schema.name',           qh.schema_name,
                    'snowflake.schema.id',             qh.schema_id,
                    'snowflake.database.id',           qh.database_id,
                    'snowflake.object.type',           ah.ddl_target_domain,
                    'snowflake.object.id',             ah.ddl_target_id,
                    'snowflake.object.name',           ah.ddl_target_name,
                    'snowflake.object.ddl.operation',  ah.ddl_operation,
                    'snowflake.object.ddl.properties', ah.ddl_properties,
                    'dsoa.debug.span.events.added',    null,
                    'dsoa.debug.span.events.failed',   null,
                    'snowflake.query.accel_est.estimated_query_times', null,
                    'snowflake.query.accel_est.status', null,
                    'snowflake.query.accel_est.upper_limit_scale_factor', null,
                    'snowflake.query.step.operator.id',     null,
                    'snowflake.query.step.id',              null,
                    'snowflake.query.step.operator.type',   null,
                    'snowflake.query.step.operator.parent_ids', null,
                    'snowflake.query.step.operator.attributes', null,
                    'snowflake.query.step.operator.stats',  null,
                    'snowflake.query.step.operator.time_breakdown', null,
                    'snowflake.query.with_operator_stats', false
                )                                                                              as attributes,
                object_construct(
                    'snowflake.data.scanned_from_cache',           qh.percentage_scanned_from_cache,
                    'snowflake.load.used',                         qh.query_load_percent,
                    'snowflake.acceleration.scale_factor.max',     qh.query_acceleration_upper_limit_scale_factor,
                    'snowflake.time.queued.overload',              qh.queued_overload_time,
                    'snowflake.time.queued.provisioning',          qh.queued_provisioning_time,
                    'snowflake.time.repair',                       qh.queued_repair_time,
                    'snowflake.time.total_elapsed',                qh.total_elapsed_time,
                    'snowflake.time.execution',                    qh.execution_time,
                    'snowflake.time.child_queries_wait',           qh.child_queries_wait_time,
                    'snowflake.time.compilation',                  qh.compilation_time,
                    'snowflake.time.transaction_blocked',          qh.transaction_blocked_time,
                    'snowflake.time.list_external_files',          qh.list_external_files_time,
                    'snowflake.time.fault_handling',               qh.fault_handling_time,
                    'snowflake.time.retry',                        qh.query_retry_time,
                    'snowflake.credits.cloud_services',            qh.credits_used_cloud_services,
--%OPTION:query_cost_attribution:
                    'snowflake.credits.attributed_compute',        qah.credits_attributed_compute,
                    'snowflake.credits.query_acceleration',        qah.credits_used_query_acceleration,
--%:OPTION:query_cost_attribution
                    'snowflake.data.spilled.local',                qh.bytes_spilled_to_local_storage,
                    'snowflake.data.spilled.remote',               qh.bytes_spilled_to_remote_storage,
                    'snowflake.data.sent_over_the_network',        qh.bytes_sent_over_the_network,
                    'snowflake.data.transferred.inbound',          qh.inbound_data_transfer_bytes,
                    'snowflake.data.transferred.outbound',         qh.outbound_data_transfer_bytes,
                    'snowflake.data.read.from_result',             qh.bytes_read_from_result,
                    'snowflake.data.scanned',                      qh.bytes_scanned,
                    'snowflake.data.deleted',                      qh.bytes_deleted,
                    'snowflake.data.written',                      qh.bytes_written,
                    'snowflake.data.written_to_result',            qh.bytes_written_to_result,
                    'snowflake.partitions.scanned',                qh.partitions_scanned,
                    'snowflake.partitions.total',                  qh.partitions_total,
                    'snowflake.acceleration.data.scanned',         qh.query_acceleration_bytes_scanned,
                    'snowflake.acceleration.partitions.scanned',   qh.query_acceleration_partitions_scanned,
                    'snowflake.external_functions.invocations',    qh.external_function_total_invocations,
                    'snowflake.external_functions.data.received',  qh.external_function_total_received_bytes,
                    'snowflake.external_functions.rows.received',  qh.external_function_total_received_rows,
                    'snowflake.rows.written_to_result',            qh.rows_written_to_result,
                    'snowflake.external_functions.data.sent',      qh.external_function_total_sent_bytes,
                    'snowflake.external_functions.rows.sent',      qh.external_function_total_sent_rows,
                    'snowflake.rows.inserted',                     qh.rows_inserted,
                    'snowflake.rows.updated',                      qh.rows_updated,
                    'snowflake.rows.deleted',                      qh.rows_deleted,
                    'snowflake.rows.unloaded',                     qh.rows_unloaded
                )                                                                              as metrics,
                count(*) over ()                                                               as _total_available
            from
                SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY                  qh
            left join
                cte_access_history                                      ah
              on  ah.query_id    = qh.query_id
              and ah.start_time  = qh.start_time
            left join
                SNOWFLAKE.ACCOUNT_USAGE.SESSIONS                        s
              on  s.session_id   = qh.session_id
              and s.created_on  >= timeadd(hour, -24, current_timestamp())
              and ah.parent_query_id is null
--%PLUGIN:event_log:
            left join
                STATUS.EVENT_LOG                                        l
              on  l.record_type  = 'SPAN'
              and l.resource_attributes:"snow.query.id"::varchar = qh.query_id
--%:PLUGIN:event_log
--%OPTION:query_cost_attribution:
            left join
                SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY       qah
              on  qah.query_id   = qh.query_id
--%:OPTION:query_cost_attribution
            where qh.end_time >= :v_cutoff
              and qh.query_text is not null
              and qh.query_id not in (
                      select query_id
                      from   STATUS.PROCESSED_QUERIES_CACHE
                      where  processed_time is not null
                  )
              and not (    qh.query_text  = ''
                       and qh.user_name   = 'SYSTEM'
                       and qh.role_name   is null
                       and qh.database_name is null
                       and qh.schema_name  is null)
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_warehouses')) = 0
                      or qh.warehouse_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_warehouses')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_warehouses')) = 0
                      or not qh.warehouse_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_warehouses')
                  )
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_databases')) = 0
                      or qh.database_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_databases')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_databases')) = 0
                      or not qh.database_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_databases')
                  )
              and (
                      (select count(*) from (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_users')) = 0
                      or qh.user_name like any (
                           select distinct ci.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ci
                           where  c.path = 'plugins.query_history.include_users')
                  )
              and (
                      (select count(*) from (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_users')) = 0
                      or not qh.user_name like any (
                           select distinct ce.value::varchar
                           from   config.configurations c,
                                  table(flatten(c.value)) ce
                           where  c.path = 'plugins.query_history.exclude_users')
                  )
            order by qh.execution_time desc nulls last
            limit :v_max_entries
        );
    END IF;

    RETURN TABLE(rs);
END;
$$
;

grant usage on procedure APP.F_GET_QUERY_HISTORY() to role DTAGENT_VIEWER;

-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from table(DTAGENT_DB.APP.F_GET_QUERY_HISTORY());
*/

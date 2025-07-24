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
-- Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
--
--
--
-- APP.V_WAREHOUSES() joins two transient tables: APP.TMP_RESOURCE_MONITORS and APP.TMP_WAREHOUSES to analyze warehouses
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_WAREHOUSES
as
select
    extract(epoch_nanosecond from current_timestamp)                                                                    as START_TIME,
    (wh.resource_monitor is null or wh.resource_monitor = 'null')                                                       as IS_UNMONITORED,
    concat('Warehouse details for ', wh.name)                                                                           as _MESSAGE,
    -- dimensions
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.name',                                 wh.name,
        'snowflake.resource_monitor.name',                          rm.name
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.execution_state',                      wh.state,
        'snowflake.warehouse.type',                                 wh.type,
        'snowflake.warehouse.size',                                 wh.size,
        'snowflake.warehouse.owner',                                wh.owner,
        'snowflake.warehouse.is_default',                           wh.is_default,
        'snowflake.warehouse.is_current',                           wh.is_current,
        'snowflake.warehouse.is_auto_suspend',                      wh.auto_suspend,
        'snowflake.warehouse.is_auto_resume',                       wh.auto_resume,
        'snowflake.warehouse.is_unmonitored',                       IS_UNMONITORED,

        'snowflake.warehouse.has_query_acceleration_enabled',       wh.enable_query_acceleration,
        'snowflake.warehouse.scaling_policy',                       wh.scaling_policy,
        'snowflake.warehouse.owner.role_type',                      wh.owner_role_type,

        'snowflake.resource_monitor.level',                         rm.level,
        'snowflake.resource_monitor.frequency',                     rm.frequency,

        'snowflake.budget.name',                                    wh.budget,

        -- this cannot be reported as metrics as then someone could accidently aggregate it incorrectly
        'snowflake.credits.quota',                                  rm.credit_quota,
        'snowflake.credits.quota.used',                             rm.used_credits,
        'snowflake.credits.quota.remaining',                        rm.remaining_credits
    )                                                                                                                   as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.warehouse.created_on',                           extract(epoch_nanosecond from wh.created_on),
        'snowflake.warehouse.resumed_on',                           extract(epoch_nanosecond from wh.resumed_on),
        'snowflake.warehouse.updated_on',                           extract(epoch_nanosecond from wh.updated_on)
    )                                                                                                                   as EVENT_TIMESTAMPS,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.compute.available',                              wh.available,
        'snowflake.compute.provisioning',                           wh.provisioning,
        'snowflake.compute.quiescing',                              wh.quiescing,
        'snowflake.compute.other',                                  wh.other,
        'snowflake.warehouse.clusters.min',                         wh.min_cluster_count,
        'snowflake.warehouse.clusters.max',                         wh.max_cluster_count,
        'snowflake.acceleration.scale_factor.max',                  wh.query_acceleration_max_scale_factor,
        'snowflake.warehouse.clusters.started',                     wh.started_clusters,
        'snowflake.queries.running',                                wh.running,
        'snowflake.queries.queued',                                 wh.queued
    )                                                                                                                   as METRICS
from APP.TMP_WAREHOUSES wh
left join APP.TMP_RESOURCE_MONITORS rm
        on wh.resource_monitor = rm.name
        or IS_UNMONITORED and rm.level = 'ACCOUNT'
;


grant select on view DTAGENT_DB.APP.V_WAREHOUSES to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_WAREHOUSES;
 */

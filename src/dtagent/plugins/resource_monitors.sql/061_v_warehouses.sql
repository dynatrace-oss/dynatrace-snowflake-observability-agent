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
-- APP.V_WAREHOUSES() joins two transient tables: APP.TMP_RESOURCE_MONITORS and APP.TMP_WAREHOUSES to analyze warehouses
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
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
        'snowflake.warehouse.owner.name',                           wh.owner,
        'snowflake.warehouse.owner.role_type',                      wh.owner_role_type,
        'snowflake.warehouse.is_default',                           TRY_TO_BOOLEAN(wh.is_default),
        'snowflake.warehouse.is_current',                           TRY_TO_BOOLEAN(wh.is_current),
        'snowflake.warehouse.is_auto_resume',                       wh.auto_resume,
        'snowflake.warehouse.is_unmonitored',                       IS_UNMONITORED,

        'snowflake.warehouse.has_query_acceleration_enabled',       wh.enable_query_acceleration,
        'snowflake.warehouse.scaling_policy',                       wh.scaling_policy,

        'snowflake.resource_monitor.level',                         rm.level,
        'snowflake.resource_monitor.frequency',                     rm.frequency,

        'snowflake.budget.name',                                    wh.budget,

        -- this cannot be reported as metrics as then someone could accidently aggregate it incorrectly
        'snowflake.credits.quota.value',                            rm.credit_quota,
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
        'snowflake.compute.available',                              TRY_TO_DOUBLE(wh.available),
        'snowflake.compute.provisioning',                           TRY_TO_DOUBLE(wh.provisioning),
        'snowflake.compute.quiescing',                              TRY_TO_DOUBLE(wh.quiescing),
        'snowflake.compute.other',                                  TRY_TO_DOUBLE(wh.other),
        'snowflake.warehouse.clusters.min',                         wh.min_cluster_count,
        'snowflake.warehouse.clusters.max',                         wh.max_cluster_count,
        'snowflake.acceleration.scale_factor.max',                  wh.query_acceleration_max_scale_factor,
        'snowflake.warehouse.clusters.started',                     wh.started_clusters,
        'snowflake.queries.running',                                wh.running,
        'snowflake.queries.queued',                                 wh.queued,
        'snowflake.warehouse.auto_suspend',                         wh.auto_suspend
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

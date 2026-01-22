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
-- APP.V_RESOURCE_MONITORS() joins two transient tables: APP.TMP_RESOURCE_MONITORS and APP.TMP_WAREHOUSES to analyze resource monitors
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_RESOURCE_MONITORS
as
with cte_by_resource_monitor as (
    select
        rm.name               as resource_monitor,

        array_agg(wh.name)    as warehouses,
        rm.level              as monitoring_level,
        rm.frequency          as reset_frequency,

        rm.credit_quota       as credits_quota,
        rm.used_credits       as credits_used,
        rm.remaining_credits  as credits_remaining,

        rm.start_time         as start_time,
        rm.end_time           as end_time,
        rm.created_on         as created_on
    from APP.TMP_RESOURCE_MONITORS rm
    full join APP.TMP_WAREHOUSES wh
    on ( wh.resource_monitor = rm.name)
    or ((wh.resource_monitor is null or wh.resource_monitor = 'null') and rm.level = 'ACCOUNT')
    group by all
)
--
select
    extract(epoch_nanosecond from current_timestamp)                                                                    as START_TIME,
    monitoring_level is not null and monitoring_level = 'ACCOUNT'                                                       as IS_ACCOUNT_LEVEL,
    IS_ACCOUNT_LEVEL or array_size(dv.warehouses) > 0                                                                   as IS_ACTIVE,
    concat('Resource Monitor details for ', dv.resource_monitor)                                                        as _MESSAGE,
    -- dimensions
    OBJECT_CONSTRUCT(
        'snowflake.resource_monitor.name',                          dv.resource_monitor
    )                                                                                                                   as DIMENSIONS,
    -- other attributes
    OBJECT_CONSTRUCT(
        'snowflake.resource_monitor.level',                         dv.monitoring_level,
        'snowflake.resource_monitor.frequency',                     dv.reset_frequency,
        'snowflake.resource_monitor.is_active',                     IS_ACTIVE,
        'snowflake.warehouses.names',                               CASE
                                                                     WHEN IS_ACTIVE
                                                                     THEN dv.warehouses
                                                                     ELSE null
                                                                     END
    )                                                                                                                   as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.resource_monitor.start_time',                    extract(epoch_nanosecond from dv.start_time),
        'snowflake.resource_monitor.end_time',                      extract(epoch_nanosecond from dv.end_time),
        'snowflake.resource_monitor.created_on',                    extract(epoch_nanosecond from dv.created_on)
    )                                                                                                                   as EVENT_TIMESTAMPS,
    -- metrics
    OBJECT_CONSTRUCT(
        'snowflake.credits.quota.used_pct',CASE
                                                  WHEN credits_quota > 0
                                                  THEN 100.0 * credits_used / credits_quota
                                                  ELSE 0
                                                  END,
        'snowflake.credits.quota',                           dv.credits_quota,
        'snowflake.credits.quota.used',                      dv.credits_used,
        'snowflake.credits.quota.remaining',                 dv.credits_remaining,
        'snowflake.resource_monitor.warehouses',             array_size(dv.warehouses)
    )                                                                                                                   as METRICS
from cte_by_resource_monitor dv
;


grant select on view DTAGENT_DB.APP.V_RESOURCE_MONITORS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from APP.V_RESOURCE_MONITORS;
 */

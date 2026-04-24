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
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_METERING_HISTORY
as
select
    'Metering entry'                                                            as _MESSAGE,
    extract(epoch_nanosecond from mh.START_TIME)                                as START_TIME,
    extract(epoch_nanosecond from mh.END_TIME)                                  as END_TIME,
    OBJECT_CONSTRUCT(
        'snowflake.service.type',                             mh.SERVICE_TYPE,
        'snowflake.service.name',                             mh.NAME
    )                                                                           as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.service.entity_id',                        mh.ENTITY_ID
    )                                                                           as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.credits.used',                             mh.CREDITS_USED,
        'snowflake.credits.used.compute',                     mh.CREDITS_USED_COMPUTE,
        'snowflake.credits.used.cloud_services',              mh.CREDITS_USED_CLOUD_SERVICES,
        'snowflake.metering.data.size',                       mh.BYTES,
        'snowflake.metering.data.rows',                       mh.ROWS,
        'snowflake.data.files',                               mh.FILES
    )                                                                           as METRICS
from
    SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY mh
where
    mh.SERVICE_TYPE != 'WAREHOUSE_METERING'
    and mh.END_TIME > GREATEST(
        timeadd(
            hour,
            -1 * DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.metering.lookback_hours', 6),
            current_timestamp
        ),
        DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('metering')
    )
order by
    mh.END_TIME asc;

grant select on view DTAGENT_DB.APP.V_METERING_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_METERING_HISTORY
limit 10;
 */

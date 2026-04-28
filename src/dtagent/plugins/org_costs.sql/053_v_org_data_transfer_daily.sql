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
--%PLUGIN:org_costs:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_ORG_DATA_TRANSFER_DAILY
as
select
    USAGE_DATE                                                                      as TIMESTAMP,
    concat(
        'New Org Data Transfer Daily entry for ',
        ACCOUNT_NAME
    )                                                                               as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.account.name',               ACCOUNT_NAME,
        'snowflake.account.locator',            ACCOUNT_LOCATOR,
        'snowflake.transfer.source.cloud',      SOURCE_CLOUD,
        'snowflake.transfer.source.region',     SOURCE_REGION,
        'snowflake.transfer.target.cloud',      TARGET_CLOUD,
        'snowflake.transfer.target.region',     TARGET_REGION,
        'snowflake.transfer.type',              TRANSFER_TYPE
    )                                                                               as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.organization.name',          ORGANIZATION_NAME
    )                                                                               as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.org.data.transferred',       BYTES_TRANSFERRED
    )                                                                               as METRICS
from SNOWFLAKE.ORGANIZATION_USAGE.DATA_TRANSFER_DAILY_HISTORY
where
    USAGE_DATE >= DATEADD(
        HOUR,
        -1 * DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.org_costs.lookback_hours', 48),
        CURRENT_TIMESTAMP()
    )
order by USAGE_DATE asc;

grant select on view DTAGENT_DB.APP.V_ORG_DATA_TRANSFER_DAILY to role DTAGENT_VIEWER;
--%:PLUGIN:org_costs

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_ORG_DATA_TRANSFER_DAILY
limit 10;
*/

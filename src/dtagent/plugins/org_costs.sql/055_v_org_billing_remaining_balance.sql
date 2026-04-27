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

create or replace view DTAGENT_DB.APP.V_ORG_BILLING_REMAINING_BALANCE
as
select
    BALANCE_DATE                                                                    as TIMESTAMP,
    concat(
        'New Org Billing Remaining Balance entry for ',
        ACCOUNT_NAME
    )                                                                               as _MESSAGE,
    OBJECT_CONSTRUCT(
        'snowflake.account.name',           ACCOUNT_NAME,
        'snowflake.account.locator',        ACCOUNT_LOCATOR
    )                                                                               as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.organization.name',      ORGANIZATION_NAME,
        'snowflake.org.billing.contract_number', CONTRACT_NUMBER
    )                                                                               as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.org.billing.capacity_balance',       CAPACITY,
        'snowflake.org.billing.rollover_balance',        ROLLOVER,
        'snowflake.org.billing.free_usage_balance',      FREE_USAGE,
        'snowflake.org.billing.on_demand_consumption',   ON_DEMAND_CONSUMPTION,
        'snowflake.org.billing.overage',                 OVERAGE
    )                                                                               as METRICS
from SNOWFLAKE.ORGANIZATION_USAGE.REMAINING_BALANCE_DAILY
where
    BALANCE_DATE >= DATEADD(
        HOUR,
        -1 * DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.org_costs.lookback_hours', 48),
        CURRENT_TIMESTAMP()
    )
order by BALANCE_DATE asc;

grant select on view DTAGENT_DB.APP.V_ORG_BILLING_REMAINING_BALANCE to role DTAGENT_VIEWER;
--%:PLUGIN:org_costs

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_ORG_BILLING_REMAINING_BALANCE
limit 10;
*/

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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_BUDGET_SPENDINGS
as
select  
    concat('Budget spending for ', b.name)                              as _MESSAGE,
    extract(epoch_nanosecond from to_timestamp(bs.MEASUREMENT_DATE))    as TIMESTAMP,
    OBJECT_CONSTRUCT(
        'snowflake.service.type',                   bs.service_type,
        'snowflake.budget.name',                    bs.budget_name,
        'snowflake.schema.name',                    b.schema_name,
        'db.namespace',                             b.database_name
    )                                                                   as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.credits.spent',                  bs.credits_spent
    )                                                                   as METRICS
from DTAGENT_DB.APP.TMP_BUDGET_SPENDING bs
    join DTAGENT_DB.APP.TMP_BUDGETS b on bs.budget_name = b.name
where
    to_timestamp(bs.MEASUREMENT_DATE) > GREATEST(timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('budgets'))
order by
    bs.MEASUREMENT_DATE asc;

grant select on view DTAGENT_DB.APP.V_BUDGET_SPENDINGS to role DTAGENT_VIEWER;

-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from DTAGENT_DB.APP.V_BUDGET_SPENDINGS limit 10;
 */
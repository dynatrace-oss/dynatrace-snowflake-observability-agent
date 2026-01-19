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
    to_timestamp(bs.MEASUREMENT_DATE) > GREATEST(timeadd(hour, -24, current_timestamp), DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('budgets'))
order by
    bs.MEASUREMENT_DATE asc;

grant select on view DTAGENT_DB.APP.V_BUDGET_SPENDINGS to role DTAGENT_VIEWER;

-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from DTAGENT_DB.APP.V_BUDGET_SPENDINGS limit 10;
 */
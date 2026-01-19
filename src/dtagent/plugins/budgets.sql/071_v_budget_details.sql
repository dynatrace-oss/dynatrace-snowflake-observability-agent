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
create or replace view DTAGENT_DB.APP.V_BUDGET_DETAILS
as
select
    concat('Budget details for ', b.name)                                                           as _MESSAGE,
    extract(epoch_nanosecond from b.created_on)                                                     as TIMESTAMP,
    OBJECT_CONSTRUCT(
        'snowflake.budget.created_on',              extract(epoch_nanosecond from b.created_on)
    )                                                                                               as EVENT_TIMESTAMPS,

    OBJECT_CONSTRUCT(
        'snowflake.budget.name',                    b.name,
        'db.namespace',                             b.database_name,
        'snowflake.schema.name',                    b.schema_name
    )                                                                                               as DIMENSIONS,

    OBJECT_CONSTRUCT(
        'snowflake.budget.owner',                   b.owner,
        'snowflake.budget.owner.role_type',         b.owner_role_type,
        'snowflake.budget.resource',                br.linked_resources
    )                                                                                               as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.credits.limit',                  bl.limit
    )                                                                                               as METRICS

from DTAGENT_DB.APP.TMP_BUDGETS b
left join DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES br on b.name = br.budget_name
left join DTAGENT_DB.APP.TMP_BUDGETS_LIMITS bl on b.name = bl.budget_name;

grant select on view DTAGENT_DB.APP.V_BUDGET_DETAILS to role DTAGENT_VIEWER;


-- example call
/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
select * from DTAGENT_DB.APP.V_BUDGET_DETAILS limit 10;
 */
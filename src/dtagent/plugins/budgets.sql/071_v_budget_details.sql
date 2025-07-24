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
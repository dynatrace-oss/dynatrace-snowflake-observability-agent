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

-- this view should only be reported to dt tenant if plugins.users.roles_monitoring_mode is set to direct_roles
-- all current roles, only added since last execution if looking for changes
create or replace view DTAGENT_DB.APP.V_USERS_DIRECT_ROLES_INSTRUMENTED
as
select
  current_timestamp                                     as TIMESTAMP,
  OBJECT_CONSTRUCT(
    'db.user',                                    grantee_name
  )                                                     as DIMENSIONS,
  OBJECT_CONSTRUCT(
    'snowflake.user.roles.direct',                array_agg(role),
    'snowflake.user.roles.granted_by',            array_agg(granted_by),
    'snowflake.user.roles.last_altered',          extract(epoch_nanosecond from max(created_on)) -- not reported as EVENT_TIMESTAMPS as we do not want to send events, and it would mess up documentation test
  )                                                     as ATTRIBUTES
from snowflake.account_usage.grants_to_users
where deleted_on is null and ((DATE(DTAGENT_DB.APP.F_LAST_PROCESSED_TS('users')) != CURRENT_DATE()) or created_on > DTAGENT_DB.APP.F_LAST_PROCESSED_TS('users'))
group by grantee_name;
grant select on table DTAGENT_DB.APP.V_USERS_DIRECT_ROLES_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_USERS_DIRECT_ROLES_INSTRUMENTED
limit 10;
*/
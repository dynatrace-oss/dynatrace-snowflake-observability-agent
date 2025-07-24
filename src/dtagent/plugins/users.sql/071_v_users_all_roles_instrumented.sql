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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- this view should only be reported to dt tenant if plugins.users.roles_monitoring_mode is set to all_roles
create or replace view DTAGENT_DB.APP.V_USERS_ALL_ROLES_INSTRUMENTED
as
with directRolesMapping AS (
  SELECT grantee_name as parent, name as child, 1 AS depth
    FROM SNOWFLAKE.account_usage.grants_to_roles
    WHERE deleted_on IS NULL
      AND grant_option = false
      AND granted_on = 'ROLE' AND granted_to = 'ROLE'
)
, rolesMapping AS (
  SELECT parent, child, depth FROM directRolesMapping
    UNION ALL
  SELECT st.parent, m.child, st.depth + m.depth
    FROM directRolesMapping m, rolesMapping st
    WHERE m.parent = st.child
)
, allRoles AS (
  SELECT parent as parent_role, child as child_role, min(depth) AS depth FROM rolesMapping
    GROUP BY 1,2
  UNION
  SELECT name, name, 0 FROM SNOWFLAKE.account_usage.roles
    WHERE deleted_on IS NULL
) 
select
  current_timestamp                                     as TIMESTAMP,
  OBJECT_CONSTRUCT(
    'db.user',                              grantee_name
  )                                                 as DIMENSIONS,
  OBJECT_CONSTRUCT(
    'snowflake.user.roles.all',             listagg(distinct ar.child_role, ','),
    'snowflake.user.roles.granted_by',      array_agg(distinct granted_by),
    'snowflake.user.roles.last_altered',    extract(epoch_nanosecond from max(created_on)) -- not reported as EVENT_TIMESTAMPS as we do not want to send events, and it would mess up documentation test
  )                                                 as ATTRIBUTES
from SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS gtu
left join allRoles ar
      on ar.parent_role = gtu.role
where gtu.deleted_on is null
group by grantee_name;

grant select on table DTAGENT_DB.APP.V_USERS_ALL_ROLES_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_USERS_ALL_ROLES_INSTRUMENTED
limit 10;
*/

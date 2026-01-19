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

-- this view should only be reported to dt tenant if plugins.users.roles_monitoring_mode is set to all_privileges
create or replace view DTAGENT_DB.APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED
as
WITH directRolesMapping AS (
  SELECT grantee_name as parent, privilege, granted_on, name as child, 1 AS depth
    FROM SNOWFLAKE.account_usage.grants_to_roles
    WHERE deleted_on IS NULL
      AND grant_option = false
      AND granted_to = 'ROLE'
  )
, rolesMapping AS (
  SELECT parent, privilege, granted_on, child, depth FROM directRolesMapping
    UNION ALL
  SELECT st.parent, m.privilege, m.granted_on, m.child, st.depth + m.depth as depth
    FROM directRolesMapping m
    INNER JOIN rolesMapping st ON m.parent = st.child
    WHERE m.granted_on = 'ROLE'
  )
, allRoles AS (
  SELECT parent as parent_role, privilege, granted_on, child as child_role, min(depth) AS depth
    FROM rolesMapping
    GROUP BY all
  UNION
  SELECT name, 'USAGE', 'ROLE', name, 0
    FROM SNOWFLAKE.account_usage.roles
    WHERE deleted_on IS NULL
  )
select
  current_timestamp                                   as TIMESTAMP,
  OBJECT_CONSTRUCT(
    'db.user',                                    grantee_name
  )                                                   as DIMENSIONS,
  OBJECT_CONSTRUCT(
    'snowflake.user.privilege',                   concat(ar.privilege, ':', ar.granted_on),
    'snowflake.user.privilege.grants_on',         listagg(distinct ar.child_role, ','),
    'snowflake.user.privilege.granted_by',        array_agg(distinct granted_by)
  )                                                   as ATTRIBUTES,
  OBJECT_CONSTRUCT(
    'snowflake.user.privilege.last_altered',      extract(epoch_nanosecond from max(created_on))
  )                                                   as EVENT_TIMESTAMPS
from SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS gtu
left join allRoles ar
      on ar.parent_role = gtu.role
where gtu.deleted_on is null
group by grantee_name, ar.privilege, ar.granted_on;
grant select on table DTAGENT_DB.APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED
limit 10;
*/

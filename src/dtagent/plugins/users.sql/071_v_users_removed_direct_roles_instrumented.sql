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

-- this view should only be reported to dt tenant if plugins.users.roles_monitoring_mode is set to direct_roles
-- always roles deleted since last execution
create or replace view DTAGENT_DB.APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED
as
select
  current_timestamp                                     as TIMESTAMP,
  'User direct roles removed since ' || DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('users') as _MESSAGE,
  OBJECT_CONSTRUCT(
    'db.user',                                  grantee_name
  )                                                     as DIMENSIONS,
  OBJECT_CONSTRUCT(
    'snowflake.user.roles.direct.removed',      listagg(role)
  )                                                     as ATTRIBUTES,
  OBJECT_CONSTRUCT(
    'snowflake.user.roles.direct.removed_on',   extract(epoch_nanosecond from date_trunc(hour, deleted_on))
  )                                                     as EVENT_TIMESTAMPS
from snowflake.account_usage.grants_to_users where deleted_on > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('users')
group by date_trunc(hour, deleted_on), grantee_name;

grant select on table DTAGENT_DB.APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED
limit 10;
*/
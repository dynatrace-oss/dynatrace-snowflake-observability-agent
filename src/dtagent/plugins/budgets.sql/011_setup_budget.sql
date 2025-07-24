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
use role ACCOUNTADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- setting core budget roles according to https://docs.snowflake.com/en/user-guide/tutorials/budgets#create-a-database-schema-and-custom-roles
create role if not exists ACCOUNT_BUDGET_ADMIN;
grant application role SNOWFLAKE.BUDGET_ADMIN to role ACCOUNT_BUDGET_ADMIN;
grant imported privileges on database SNOWFLAKE to role ACCOUNT_BUDGET_ADMIN;

create role if not exists ACCOUNT_BUDGET_MONITOR;
grant application role SNOWFLAKE.BUDGET_VIEWER to role ACCOUNT_BUDGET_MONITOR;
grant imported privileges on database SNOWFLAKE to role ACCOUNT_BUDGET_MONITOR;

create role if not exists BUDGET_OWNER;
grant database role SNOWFLAKE.BUDGET_CREATOR to role BUDGET_OWNER;

-- setting up Dynatrace Snowflake Observability Agent part

grant role ACCOUNT_BUDGET_ADMIN to role DTAGENT_ADMIN;
grant role ACCOUNT_BUDGET_MONITOR to role DTAGENT_VIEWER;
grant role BUDGET_OWNER to role DTAGENT_ADMIN;

use role DTAGENT_ADMIN;                                            
create SNOWFLAKE.CORE.BUDGET if not exists APP.DTAGENT_BUDGET();
CALL DTAGENT_DB.APP.DTAGENT_BUDGET!ADD_RESOURCE(select SYSTEM$REFERENCE('DATABASE', 'DTAGENT_DB', 'SESSION', 'APPLYBUDGET'));
CALL DTAGENT_DB.APP.DTAGENT_BUDGET!ADD_RESOURCE(select SYSTEM$REFERENCE('WAREHOUSE', 'DTAGENT_WH', 'SESSION', 'APPLYBUDGET'));

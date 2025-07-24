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

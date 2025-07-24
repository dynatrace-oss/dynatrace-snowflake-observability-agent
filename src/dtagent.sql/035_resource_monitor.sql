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
--
-- We need resource monitor setup for Dynatrace Snowflake Observability Agent to ensure we don't spent too much credits
-- This is a procedure that allows to set correct values based on the value provided
-- It is called initially with just one credit, and later it is called by CONFIG.UPDATE_FROM_CONFIGURATIONS() 
--
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.SET_RESOURCE_MONITOR(SNOWFLAKE_CREDIT_QUOTA int)
returns int
language SQL
execute as caller
as
$$
begin
  execute immediate 'create or replace resource monitor DTAGENT_RS with' || 
                    ' credit_quota = ' || SNOWFLAKE_CREDIT_QUOTA ||
                    ' frequency = DAILY' || 
                    ' start_timestamp = IMMEDIATELY' || 
                    ' notify_users = ("' || current_user() || '")' ||
                    ' triggers' ||
                        ' on  50 percent do notify' || 
                        ' on 100 percent do suspend' || 
                        ' on 110 percent do suspend_immediate';
  execute immediate 'alter warehouse if exists DTAGENT_WH set resource_monitor = DTAGENT_RS';
  return 0;
exception
  when statement_error then
    execute immediate 'create or replace resource monitor DTAGENT_RS with' || 
                      ' credit_quota = ' || SNOWFLAKE_CREDIT_QUOTA ||
                      ' frequency = DAILY' || 
                      ' start_timestamp = IMMEDIATELY' || 
                      ' triggers' ||
                          ' on  50 percent do notify' || 
                          ' on 100 percent do suspend' || 
                          ' on 110 percent do suspend_immediate';
    execute immediate 'alter warehouse if exists DTAGENT_WH set resource_monitor = DTAGENT_RS';
  return 1;  
end;
$$
;

use role ACCOUNTADMIN; -- Only the ACCOUNTADMIN role can assign warehouses to resource monitors.
call DTAGENT_DB.CONFIG.SET_RESOURCE_MONITOR(1);
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
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
-- We need resource monitor setup for Dynatrace Snowflake Observability Agent to ensure we don't spend too much credits
-- This procedure allows updating the credit quota dynamically based on configuration values
-- It is called by CONFIG.UPDATE_FROM_CONFIGURATIONS() to apply credit_quota changes from the config
--
-- Note: DTAGENT_OWNER has OWNERSHIP and MODIFY privileges on DTAGENT_RS resource monitor,
-- which allows this procedure to execute as caller without requiring ACCOUNTADMIN privileges
--
--%OPTION:resource_monitor:
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.P_UPDATE_RESOURCE_MONITOR(SNOWFLAKE_CREDIT_QUOTA int)
returns int
language SQL
execute as caller
as
$$
begin
  execute immediate 'alter resource monitor DTAGENT_RS set credit_quota = ' || SNOWFLAKE_CREDIT_QUOTA;
  return 0;
end;
$$
;
--%:OPTION:resource_monitor
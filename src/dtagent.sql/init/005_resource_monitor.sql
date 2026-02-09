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
-- The resource monitor is created with ownership granted to DTAGENT_OWNER along with MODIFY privileges
-- This allows DTAGENT_OWNER to update the credit_quota via P_UPDATE_RESOURCE_MONITOR() without ACCOUNTADMIN
--
--%OPTION:resource_monitor:
use role ACCOUNTADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

EXECUTE IMMEDIATE $$
declare
    the_user varchar default current_user();
begin
  create or replace resource monitor DTAGENT_RS with
    credit_quota = 1
    frequency = DAILY
    start_timestamp = IMMEDIATELY
    notify_users = (:the_user)
    triggers
      on  50 percent do notify
      on 100 percent do suspend
      on 110 percent do suspend_immediate;

  return 0;
exception
  when statement_error then
    create or replace resource monitor DTAGENT_RS with
      credit_quota = 1
      frequency = DAILY
      start_timestamp = IMMEDIATELY
      triggers
        on  50 percent do notify
        on 100 percent do suspend
        on 110 percent do suspend_immediate;
  return 1;
end;
$$
;

grant ownership on resource monitor DTAGENT_RS to role DTAGENT_OWNER revoke current grants;
grant modify on resource monitor DTAGENT_RS to role DTAGENT_OWNER;
alter warehouse if exists DTAGENT_WH set resource_monitor = DTAGENT_RS;
--%:OPTION:resource_monitor

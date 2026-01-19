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
-- APP.P_CLEANUP_EVENT_LOG(INT) will remove old event_log entries, with number of hours to retain
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

drop procedure if exists DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG(INT);

create or replace procedure DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG()
returns text
language SQL
execute as owner
as
$$
DECLARE
  is_event_log_table  BOOLEAN  DEFAULT FALSE;
BEGIN
  -- Check if the EVENT_LOG table exists in the STATUS schema in the DTAGENT_DB database, i.e., if it is owned by this particular Dynatrace Snowflake Observability Agent instance
  select TABLE_TYPE like '%TABLE'
    into is_event_log_table
    from DTAGENT_DB.INFORMATION_SCHEMA.TABLES
    where TABLE_SCHEMA = 'STATUS'
      and TABLE_NAME = 'EVENT_LOG';

  -- If this Dynatrace Snowflake Observability Agent instance owns this EVENT_LOG table, delete entries older than the configured retention period
  IF (:is_event_log_table) THEN
    delete from DTAGENT_DB.STATUS.EVENT_LOG
    where TIMESTAMP < timeadd(HOUR, -1*DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.event_log.retention_hours', 24), CURRENT_TIMESTAMP);
    RETURN 'old event_log entries removed from STATUS.EVENT_LOG';
  END IF;

  RETURN 'no event log table found';
EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;
grant usage on procedure DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG() to role DTAGENT_VIEWER;
alter procedure DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG() set LOG_LEVEL = WARN;

/*
use role DTAGENT_VIEWER;
call DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG();
*/

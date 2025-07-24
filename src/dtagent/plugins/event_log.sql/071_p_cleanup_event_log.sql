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
-- APP.P_CLEANUP_EVENT_LOG(INT) will remove old event_log entries, with number of hours to retain
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

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
    where TIMESTAMP < timeadd(HOUR, -1*DTAGENT_DB.APP.F_GET_CONFIG_VALUE('plugins.event_log.retention_hours', 24), CURRENT_TIMESTAMP);
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

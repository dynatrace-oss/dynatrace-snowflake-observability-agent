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
-- Configuring event logs table 
-- and enable logs collection on the account level
--
use role ACCOUNTADMIN; use database DTAGENT_DB; use schema STATUS; use warehouse DTAGENT_WH;  

create or replace procedure DTAGENT_DB.APP.SETUP_EVENT_TABLE()
returns TEXT
language SQL
execute as CALLER
as
$$
DECLARE
    s_event_table_name  TEXT    DEFAULT '';
    a_no_custom_event_t ARRAY   DEFAULT ARRAY_CONSTRUCT('', 'snowflake.telemetry.events', 'DTAGENT_DB.STATUS.EVENT_LOG');
    is_event_log_table  BOOLEAN DEFAULT FALSE;
BEGIN
  show PARAMETERS like 'EVENT_TABLE' in ACCOUNT;
  select "value" into s_event_table_name from TABLE(result_scan(last_query_id()));
  select TABLE_TYPE like '%TABLE' into is_event_log_table from DTAGENT_DB.INFORMATION_SCHEMA.TABLES where TABLE_SCHEMA = 'STATUS' and TABLE_NAME = 'EVENT_LOG';

  IF (ARRAY_CONTAINS(:s_event_table_name::variant, :a_no_custom_event_t)) THEN
    -- there is an event table defined or there is Dynatrace Snowflake Observability Agent one present
    IF (NOT :is_event_log_table) THEN
      drop view if exists DTAGENT_DB.STATUS.EVENT_LOG;
    END IF;

    create event table if not exists DTAGENT_DB.STATUS.EVENT_LOG;
    alter account set event_table = DTAGENT_DB.STATUS.EVENT_LOG;
    
    grant ownership on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_ADMIN revoke current grants;
    grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;
    
    grant modify log level on account to role DTAGENT_ADMIN;
    grant modify session log level on account to role DTAGENT_VIEWER;
    alter account set log_level = WARN;

    RETURN 'Dynatrace Snowflake Observability Agent has setup own Event table';
  ELSE
    -- there is a an event table defined already, not by this Dynatrace Snowflake Observability Agent
    IF (:is_event_log_table) THEN
      drop table if exists DTAGENT_DB.STATUS.EVENT_LOG;
    END IF;

    EXECUTE IMMEDIATE concat('create view if not exists DTAGENT_DB.STATUS.EVENT_LOG as select * from ', :s_event_table_name);
    EXECUTE IMMEDIATE concat('grant select on table ', :s_event_table_name, ' to role DTAGENT_VIEWER');

    grant ownership on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_ADMIN revoke current grants;
    grant select on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;

    RETURN 'Dynatrace Snowflake Observability Agent will use predefined Event table';
  END IF;
END;
$$
;

call DTAGENT_DB.APP.SETUP_EVENT_TABLE();


--
-- EXAMPLE CALL:
/*
select * 
from DTAGENT_DB.STATUS.EVENT_LOG 
-- where
--   SCOPE['name'] = 'DTAGENT'
--   and RECORD['severity_text'] = 'DEBUG'
--   and RECORD_TYPE = 'LOG'
order by timestamp desc
limit 10;
 */

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

    grant modify log level on account to role DTAGENT_ADMIN; -- FIXME: should be granted to DTAGENT_VIEWER?
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

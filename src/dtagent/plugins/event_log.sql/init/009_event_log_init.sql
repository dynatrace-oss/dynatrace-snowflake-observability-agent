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
    s_event_table_name    TEXT    DEFAULT '';
    -- names of event log tables which would mean we deal with one created by this DSOA instance or there is no custom event table at all
    a_no_custom_event_t   ARRAY   DEFAULT ARRAY_CONSTRUCT('', 'DTAGENT_DB.STATUS.EVENT_LOG');
    is_event_log_table    BOOLEAN DEFAULT FALSE;
    b_has_log_event_level BOOLEAN DEFAULT FALSE;
    n_param_rows          INTEGER DEFAULT 0;
BEGIN
  show PARAMETERS like 'EVENT_TABLE' in ACCOUNT;
  select "value" into s_event_table_name from TABLE(result_scan(last_query_id()));

  -- Detect whether LOG_EVENT_LEVEL parameter is supported (Snowflake BCR Bundle 2026_02+).
  -- This parameter decouples event table ingestion control from LOG_LEVEL.
  BEGIN
    show PARAMETERS like 'LOG_EVENT_LEVEL' in ACCOUNT;
    select count(*) into n_param_rows from TABLE(result_scan(last_query_id()));
    b_has_log_event_level := (n_param_rows > 0);
  EXCEPTION
    WHEN OTHER THEN
      b_has_log_event_level := FALSE;
  END;
  select TABLE_TYPE like '%TABLE' into is_event_log_table from DTAGENT_DB.INFORMATION_SCHEMA.TABLES where TABLE_SCHEMA = 'STATUS' and TABLE_NAME = 'EVENT_LOG';

  IF (ARRAY_CONTAINS(:s_event_table_name::variant, :a_no_custom_event_t)) THEN
    -- there is NO event table defined or there is Dynatrace Snowflake Observability Agent one present
    IF (NOT :is_event_log_table) THEN
      -- in case there is a view we need to get rid of it before creating the event table
      drop view if exists DTAGENT_DB.STATUS.EVENT_LOG;
    END IF;

    create event table if not exists DTAGENT_DB.STATUS.EVENT_LOG;
    alter account set event_table = DTAGENT_DB.STATUS.EVENT_LOG;

    grant ownership on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
    grant select, delete on table DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_VIEWER;

    grant modify session LOG LEVEL on account to role DTAGENT_VIEWER;
    alter account set log_level = WARN;

    -- Set LOG_EVENT_LEVEL = INFO on accounts that support BCR Bundle 2026_02+.
    -- This ensures events emitted at INFO+ severity are ingested into the event table.
    -- On pre-BCR accounts the parameter does not exist so we skip it gracefully.
    IF (:b_has_log_event_level) THEN
      alter account set LOG_EVENT_LEVEL = INFO;
      grant modify LOG EVENT LEVEL on account to role DTAGENT_VIEWER;
    END IF;

    RETURN 'Dynatrace Snowflake Observability Agent has setup own Event table';
  ELSE
    -- there is an event table defined already, not by this Dynatrace Snowflake Observability Agent
    -- (including SNOWFLAKE.TELEMETRY.EVENTS — the Snowflake-managed shared event table)
    IF (:is_event_log_table) THEN
      -- in case there is a table with this name we need to get rid of it before creating the view on top of the custom event table
      drop table if exists DTAGENT_DB.STATUS.EVENT_LOG;
    END IF;

    -- attempt to grant select on the source table; ignore failures for read-only or Snowflake-managed tables
    BEGIN
      EXECUTE IMMEDIATE concat('grant select on table ', :s_event_table_name, ' to role DTAGENT_VIEWER');
    EXCEPTION
      WHEN OTHER THEN
        -- ignore failures for read-only or Snowflake-managed event tables
        -- leaves warning in the logs
        SYSTEM$LOG_WARN(concat('Could not grant select on table ', :s_event_table_name, ' to role DTAGENT_VIEWER: ', SQLERRM));
    END;

    -- create a view on top of the existing event table, so we can use it in the event_log plugin
    EXECUTE IMMEDIATE concat('create view if not exists DTAGENT_DB.STATUS.EVENT_LOG as select * from ', :s_event_table_name);
    grant ownership on view DTAGENT_DB.STATUS.EVENT_LOG to role DTAGENT_OWNER revoke current grants;
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

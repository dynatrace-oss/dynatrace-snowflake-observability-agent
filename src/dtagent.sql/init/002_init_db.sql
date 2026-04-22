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
-- Initializing Dynatrace Snowflake Observability Agent by creating: DB
--
use role ACCOUNTADMIN;
create database if not exists DTAGENT_DB;

-- Set default LOG_LEVEL for all procedures in this database to INFO to enable sending logs to Dynatrace with at least INFO level,
--  which is the default level for the agent
alter database DTAGENT_DB set LOG_LEVEL = INFO;

-- Set LOG_EVENT_LEVEL = INFO on accounts that support BCR Bundle 2026_02+.
-- LOG_EVENT_LEVEL decouples event table ingestion control from LOG_LEVEL.
-- On pre-BCR accounts the parameter does not exist so we skip it gracefully.
BEGIN
  LET n_rows INTEGER DEFAULT 0;
  show PARAMETERS like 'LOG_EVENT_LEVEL' in DATABASE DTAGENT_DB;
  select count(*) into n_rows from TABLE(result_scan(last_query_id()));
  IF (:n_rows > 0) THEN
    alter database DTAGENT_DB set LOG_EVENT_LEVEL = INFO;
  END IF;
EXCEPTION
  WHEN OTHER THEN
    NULL; -- pre-BCR account: LOG_EVENT_LEVEL parameter not available, skip gracefully
END;

-- Set default DATA_RETENTION_TIME_IN_DAYS for all non-transient tables in this database
-- This will be overridden by the configured value in the config table after deployment
alter database DTAGENT_DB set DATA_RETENTION_TIME_IN_DAYS = 1;

grant ownership on database DTAGENT_DB to role DTAGENT_OWNER revoke current grants;
grant usage on database DTAGENT_DB to role DTAGENT_VIEWER;

grant OPERATE on all tasks in database DTAGENT_DB to role DTAGENT_VIEWER;
grant OPERATE on future tasks in database DTAGENT_DB to role DTAGENT_VIEWER;


create schema if not exists DTAGENT_DB.PUBLIC;
grant ownership on schema DTAGENT_DB.PUBLIC to role DTAGENT_OWNER revoke current grants;
grant usage on schema DTAGENT_DB.PUBLIC to role DTAGENT_VIEWER;


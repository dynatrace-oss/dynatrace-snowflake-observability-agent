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

-- Set default LOG_LEVEL for all procedures in this database
alter database DTAGENT_DB set LOG_LEVEL = WARN;

grant ownership on database DTAGENT_DB to role DTAGENT_OWNER;
grant usage on database DTAGENT_DB to role DTAGENT_VIEWER;

grant OPERATE on all tasks in database DTAGENT_DB to role DTAGENT_VIEWER;
grant OPERATE on future tasks in database DTAGENT_DB to role DTAGENT_VIEWER;


create schema if not exists DTAGENT_DB.PUBLIC;
grant ownership on schema DTAGENT_DB.PUBLIC to role DTAGENT_OWNER;
grant usage on schema DTAGENT_DB.PUBLIC to role DTAGENT_VIEWER;


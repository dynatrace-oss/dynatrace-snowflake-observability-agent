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
-- DTAGENT_DB.APP.DTAGENT() is the core procedure of Dynatrace Snowflake Observability Agent. 
-- It is responsible for sending data (prepared by other procedures in the app schema) as: metrics, spans, and logs
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.DTAGENT(sources array)
returns object
language python
runtime_version = '3.11'
packages = (
    'requests',
    'pandas',
    'tzlocal',
    'snowflake-snowpark-python',
    'opentelemetry-api',
    'opentelemetry-sdk',
    'opentelemetry-exporter-otlp-proto-http'
)
handler = 'main'
external_access_integrations = (DTAGENT_API_INTEGRATION)
secrets = ('dtagent_token'=DTAGENT_DB.CONFIG.DTAGENT_API_KEY)
execute as caller
as 
$$ 
# -- language=Python
##INSERT ../build/_dtagent.py
$$
;

---------------------------------------------------------------------
grant usage on procedure DTAGENT_DB.APP.DTAGENT(array) to role DTAGENT_VIEWER;

alter procedure DTAGENT_DB.APP.DTAGENT(array) set LOG_LEVEL = INFO;




/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

call APP.DTAGENT(ARRAY_CONSTRUCT('active_queries'));
call APP.DTAGENT(ARRAY_CONSTRUCT('budgets'));
call APP.DTAGENT(ARRAY_CONSTRUCT('data_schemas'));
call APP.DTAGENT(ARRAY_CONSTRUCT('data_volume'));
call APP.DTAGENT(ARRAY_CONSTRUCT('dynamic_tables'));
call APP.DTAGENT(ARRAY_CONSTRUCT('event_log'));
call APP.DTAGENT(ARRAY_CONSTRUCT('event_usage'));
call APP.DTAGENT(ARRAY_CONSTRUCT('login_history'));
call APP.DTAGENT(ARRAY_CONSTRUCT('query_history'));
call APP.DTAGENT(ARRAY_CONSTRUCT('resource_monitors'));
call APP.DTAGENT(ARRAY_CONSTRUCT('tasks'));
call APP.DTAGENT(ARRAY_CONSTRUCT('trust_center'));
call APP.DTAGENT(ARRAY_CONSTRUCT('users'));
call APP.DTAGENT(ARRAY_CONSTRUCT('warehouse_usage'));

 */

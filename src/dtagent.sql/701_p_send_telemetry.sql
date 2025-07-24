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
-- DTAGENT_DB.APP.SEND_TELEMETRY() enables to send given data as telemetry (of selected type) to Dynatrace
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.SEND_TELEMETRY(sources variant, params object)
returns string
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
##INSERT ../build/_send_telemetry.py
$$
;

---------------------------------------------------------------------
grant usage on procedure DTAGENT_DB.APP.SEND_TELEMETRY(variant, object) to role DTAGENT_VIEWER;

alter procedure DTAGENT_DB.APP.SEND_TELEMETRY(variant, object) set LOG_LEVEL = INFO;




/*
use role DTAGENT_VIEWER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

call APP.SEND_TELEMETRY('DTAGENT_DB.APP.V_QUERIES_SUMMARY_INSTRUMENTED'::variant, OBJECT_CONSTRUCT());
*/

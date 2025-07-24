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

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

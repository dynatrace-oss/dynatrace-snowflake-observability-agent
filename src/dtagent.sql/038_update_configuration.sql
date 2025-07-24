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
-- This stored procedure will update configuration of Dynatrace Snowflake Observability Agent
-- HINT: call `./deploy.sh $ENV config` to initialize your Dynatrace Snowflake Observability Agent deployment with proper config-$ENV.json file
--
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH; 

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS()
returns varchar not null
language SQL
execute as caller
as
$$
declare
    SNOWFLAKE_CREDIT_QUOTA INT;
    PROCEDURE_TIMEOUT INT;
begin
    SNOWFLAKE_CREDIT_QUOTA := (select DTAGENT_DB.APP.F_GET_CONFIG_VALUE('core.snowflake_credit_quota', 5));
    if (SNOWFLAKE_CREDIT_QUOTA IS NOT NULL) then
        call DTAGENT_DB.CONFIG.SET_RESOURCE_MONITOR(:SNOWFLAKE_CREDIT_QUOTA);
    end if;

    PROCEDURE_TIMEOUT := (select DTAGENT_DB.APP.F_GET_CONFIG_VALUE('core.procedure_timeout', 3600));
    if (PROCEDURE_TIMEOUT IS NOT NULL) then
        execute immediate 'ALTER WAREHOUSE DTAGENT_WH SET STATEMENT_TIMEOUT_IN_SECONDS = ' || :PROCEDURE_TIMEOUT ||  ';';
    end if;

    call DTAGENT_DB.CONFIG.UPDATE_ALL_PLUGINS_SCHEDULE();

    return 'OK';
exception
    when statement_error then
        return SQLERRM;
end
$$;

-- we need to use ACCOUNTADMIN role to be able to call the procedure SET_RESOURCE_MONITOR() which is referenced in the UPDATE_FROM_CONFIGURATIONS() procedure
use role ACCOUNTADMIN; use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH; 
call DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();

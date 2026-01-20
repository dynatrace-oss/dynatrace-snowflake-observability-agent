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
-- This stored procedure will update configuration of Dynatrace Snowflake Observability Agent
-- HINT: call `./deploy.sh $ENV config` to initialize your Dynatrace Snowflake Observability Agent deployment with proper config-$ENV.yml file
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
    SNOWFLAKE_CREDIT_QUOTA := (select DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('core.snowflake_credit_quota', 5));
    if (SNOWFLAKE_CREDIT_QUOTA IS NOT NULL) then
        call DTAGENT_DB.CONFIG.P_UPDATE_RESOURCE_MONITOR(:SNOWFLAKE_CREDIT_QUOTA);
    end if;

    PROCEDURE_TIMEOUT := (select DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('core.procedure_timeout', 3600));
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

call DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();

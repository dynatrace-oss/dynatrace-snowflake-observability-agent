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
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_SHARES_CONF()
returns text
language SQL
execute as caller
as
$$
begin
    call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('shares');

    return 'shares plugin config updated';
exception
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return SQLERRM;
end;
$$
;

grant usage on procedure DTAGENT_DB.CONFIG.UPDATE_SHARES_CONF() to role DTAGENT_VIEWER;

-- call DTAGENT_DB.CONFIG.UPDATE_SHARES_CONF();
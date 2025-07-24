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

use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(db_name VARCHAR)
returns text
language sql
execute as owner
as
$$
BEGIN
    EXECUTE IMMEDIATE concat('GRANT IMPORTED PRIVILEGES on DATABASE ', :db_name, ' TO ROLE DTAGENT_VIEWER');

    RETURN 'imported privileges granted on ' || :db_name;
EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;
grant usage on procedure DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(VARCHAR) to role DTAGENT_VIEWER;

-- use role DTAGENT_ADMIN;
-- call DTAGENT_DB.APP.P_GET_SHARES();

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
-- APP.P_MONITOR_WAREHOUSES() will grant MONITOR privilege to DTAGENT_VIEWER so that all queries are visible in query_history
-- this procedure is deprecated and not deployed to Snowflake 
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace procedure DTAGENT_DB.APP.P_MONITOR_WAREHOUSES()
returns text
language sql
execute as caller
as
$$
DECLARE
    q_show_warehouses   TEXT DEFAULT    'show warehouses';
    c_warehouse_names   CURSOR FOR      select "name" as name from TABLE(result_scan(last_query_id())) 
                                        where name not in (
                                            select NAME
                                            from snowflake.account_usage.grants_to_roles
                                            where granted_on = 'WAREHOUSE'
                                            and granted_to = 'ROLE'
                                            and grantee_name = 'DTAGENT_VIEWER'
                                            and privilege = 'MONITOR'
                                            and deleted_on is null
                                        );

    q_grant_monitor     TEXT DEFAULT    '';
BEGIN
    -- list all warehouses
    EXECUTE IMMEDIATE :q_show_warehouses;

    -- iterate over warehouses
    FOR r_wh IN c_warehouse_names DO
        q_grant_monitor := 'grant monitor on warehouse ' || r_wh.name || '  to role DTAGENT_VIEWER;';

        EXECUTE IMMEDIATE :q_grant_monitor;
    END FOR;

    RETURN 'MONITOR privilege on warehouses granted to DTAGENT_VIEWER';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;

alter procedure DTAGENT_DB.APP.P_MONITOR_WAREHOUSES() set LOG_LEVEL = WARN;

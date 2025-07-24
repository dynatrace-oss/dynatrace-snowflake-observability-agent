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

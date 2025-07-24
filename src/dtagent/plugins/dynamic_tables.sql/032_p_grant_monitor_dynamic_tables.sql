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
-- APP.P_GRANT_MONITOR_DYNAMIC_TABLES() returns metadata for all dynamic tables defined in Snowflake.
--
-- !! Must be invoked after creation of CONFIG.CONFIGURATIONS table (031_configuration_table)
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES()
returns text
language sql
execute as caller
as
$$
DECLARE
    q_show_databases        TEXT DEFAULT    'show databases';
    c_database_names        CURSOR FOR      with cte_includes as (
                                                select distinct split_part(ci.VALUE, '.', 0) as db_pattern
                                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                                                where c.PATH = 'plugins.dynamic_tables.include'
                                            )
                                            , cte_excludes as (
                                                select distinct split_part(ce.VALUE, '.', 0) as db_pattern
                                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
                                                where c.PATH = 'plugins.dynamic_tables.exclude'
                                            )
                                            select "name" as name 
                                            from TABLE(result_scan(last_query_id())) 
                                            where "kind" = 'STANDARD'
                                                and name LIKE ANY (select db_pattern from cte_includes)
                                                and not name LIKE ANY (select db_pattern from cte_excludes)
                                            ;

    q_grant_monitor_all     TEXT DEFAULT    '';
    q_grant_monitor_future  TEXT DEFAULT    '';
BEGIN
    -- list all warehouses
    EXECUTE IMMEDIATE :q_show_databases;

    -- iterate over warehouses
    FOR r_db IN c_database_names DO
        q_grant_monitor_all := 'grant monitor on all dynamic tables in database ' || r_db.name || '  to role DTAGENT_VIEWER;';
        q_grant_monitor_future := 'grant monitor on future dynamic tables in database ' || r_db.name || '  to role DTAGENT_VIEWER;';

        EXECUTE IMMEDIATE :q_grant_monitor_all;
        EXECUTE IMMEDIATE :q_grant_monitor_future;
    END FOR;

    RETURN 'granted monitor for future and dynamic tables to DTAGENT_VIEWER';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;

alter procedure DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES() set LOG_LEVEL = WARN;

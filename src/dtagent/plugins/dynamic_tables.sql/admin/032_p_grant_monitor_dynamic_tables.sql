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
-- APP.P_GRANT_MONITOR_DYNAMIC_TABLES() returns metadata for all dynamic tables defined in Snowflake.
--
-- !! Must be invoked after creation of CONFIG.CONFIGURATIONS table (031_configuration_table)
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES()
returns text
language sql
execute as caller
as
$$
DECLARE
    rs_database_names       RESULTSET;

    q_grant_monitor_all     TEXT DEFAULT    '';
    q_grant_monitor_future  TEXT DEFAULT    '';
BEGIN
    rs_database_names := (SHOW DATABASES ->>
                            with cte_includes as (
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
                            from $1
                            where "kind" = 'STANDARD'
                                and name LIKE ANY (select db_pattern from cte_includes)
                                and not name LIKE ANY (select db_pattern from cte_excludes))
                            ;
    LET c_database_names CURSOR FOR rs_database_names;

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

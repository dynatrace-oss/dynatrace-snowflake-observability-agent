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
-- APP.P_GRANT_MONITOR_DYNAMIC_TABLES() grants MONITOR privileges on dynamic tables to DTAGENT_VIEWER.
--
-- Grant granularity is derived from the include pattern:
--   - DB.%.%            (wildcard schema, wildcard table) → GRANT ... IN DATABASE db_name
--   - DB.SCHEMA.%       (specific schema, wildcard table) → GRANT ... IN SCHEMA db_name.schema_name
--   - DB.SCHEMA.TABLE   (specific schema, specific table) → GRANT ... ON DYNAMIC TABLE db_name.schema_name.table_name
--
-- !! Must be invoked after creation of CONFIG.CONFIGURATIONS table (031_configuration_table)
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES()
returns text
language sql
execute as caller
as
$$
DECLARE
    rs_database_names       RESULTSET;
    rs_schema_names         RESULTSET;
    rs_table_names          RESULTSET;

    q_grant_monitor_all     TEXT DEFAULT    '';
    q_grant_monitor_future  TEXT DEFAULT    '';
BEGIN
    -- Grant at DATABASE level for patterns where schema part is a wildcard (e.g. DB.%.%)
    rs_database_names := (SHOW DATABASES ->>
                            with cte_includes as (
                                select distinct split_part(ci.VALUE, '.', 1) as db_pattern
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                                where c.PATH = 'plugins.dynamic_tables.include'
                                    and split_part(ci.VALUE, '.', 2) = '%'
                            )
                            , cte_excludes as (
                                select distinct split_part(ce.VALUE, '.', 1) as db_pattern
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

    FOR r_db IN c_database_names DO
        q_grant_monitor_all := 'grant monitor on all dynamic tables in database identifier(?) to role DTAGENT_VIEWER';
        q_grant_monitor_future := 'grant monitor on future dynamic tables in database identifier(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (r_db.name);
        EXECUTE IMMEDIATE :q_grant_monitor_future USING (r_db.name);
    END FOR;

    -- Grant at SCHEMA level for patterns where schema is specific and table is a wildcard (e.g. DB.ANALYTICS.%)
    rs_schema_names := (SHOW DATABASES ->>
                            with cte_includes as (
                                select distinct
                                    split_part(ci.VALUE, '.', 1) as db_pattern,
                                    split_part(ci.VALUE, '.', 2) as schema_name
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                                where c.PATH = 'plugins.dynamic_tables.include'
                                    and split_part(ci.VALUE, '.', 2) != '%'
                                    and split_part(ci.VALUE, '.', 3) = '%'
                            )
                            , cte_excludes as (
                                select distinct split_part(ce.VALUE, '.', 1) as db_pattern
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
                                where c.PATH = 'plugins.dynamic_tables.exclude'
                            )
                            select "name" as db_name, ci.schema_name
                            from $1
                            join cte_includes ci on "name" LIKE ci.db_pattern
                            where "kind" = 'STANDARD'
                                and not "name" LIKE ANY (select db_pattern from cte_excludes))
                            ;
    LET c_schema_names CURSOR FOR rs_schema_names;

    FOR r_schema IN c_schema_names DO
        q_grant_monitor_all := 'grant monitor on all dynamic tables in schema IDENTIFIER(?) to role DTAGENT_VIEWER';
        q_grant_monitor_future := 'grant monitor on future dynamic tables in schema IDENTIFIER(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (r_schema.db_name || '.' || r_schema.schema_name);
        EXECUTE IMMEDIATE :q_grant_monitor_future USING (r_schema.db_name || '.' || r_schema.schema_name);
    END FOR;

    -- Grant at TABLE level for patterns where both schema and table parts are specific (e.g. DB.ANALYTICS.ORDERS_DT)
    -- Note: FUTURE grants are not applicable at the individual table level
    rs_table_names := (select distinct
                            split_part(ci.VALUE, '.', 1) as db_name,
                            split_part(ci.VALUE, '.', 2) as schema_name,
                            split_part(ci.VALUE, '.', 3) as table_name
                        from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                        where c.PATH = 'plugins.dynamic_tables.include'
                            and split_part(ci.VALUE, '.', 2) != '%'
                            and split_part(ci.VALUE, '.', 3) != '%');
    LET c_table_names CURSOR FOR rs_table_names;

    FOR r_table IN c_table_names DO
        q_grant_monitor_all := 'grant monitor on dynamic table IDENTIFIER(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (r_table.db_name || '.' || r_table.schema_name || '.' || r_table.table_name);
    END FOR;

    RETURN 'granted monitor for future and dynamic tables to DTAGENT_VIEWER';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GRANT_MONITOR_DYNAMIC_TABLES() to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin

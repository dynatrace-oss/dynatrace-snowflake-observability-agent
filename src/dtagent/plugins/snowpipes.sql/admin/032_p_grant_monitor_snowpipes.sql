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
-- APP.P_GRANT_MONITOR_SNOWPIPES() grants MONITOR privileges on pipes to DTAGENT_VIEWER.
--
-- Grant granularity is derived from the include pattern:
--   - DB.%.%            (wildcard schema, wildcard pipe)  → GRANT ... IN DATABASE db_name
--   - DB.SCHEMA.%       (specific schema, wildcard pipe)  → GRANT ... IN SCHEMA db_name.schema_name
--   - DB.SCHEMA.PIPE    (specific schema, specific pipe)  → GRANT ... ON PIPE db_name.schema_name.pipe_name
--
-- Exclude patterns are matched at the same fully-qualified granularity as includes:
--   - DB-level grants   are suppressed only when an exclude pattern covers the whole database (e.g. DB.%.%)
--   - Schema-level grants are suppressed when an exclude pattern covers the schema (e.g. DB.SCHEMA.%)
--   - Pipe-level grants  are suppressed when an exclude pattern covers the specific pipe (e.g. DB.SCHEMA.PIPE)
-- A fine-grained exclude (e.g. PROD_DB.SECRET_SCHEMA.%) does NOT suppress a database-level grant;
-- it prevents the schema from appearing in schema-level grants instead.
--
-- !! Must be invoked after creation of CONFIG.CONFIGURATIONS table (031_configuration_table)
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_MONITOR_SNOWPIPES()
returns text
language sql
execute as caller
as
$$
DECLARE
    rs_database_names       RESULTSET;
    rs_schema_names         RESULTSET;
    rs_pipe_names           RESULTSET;

    q_grant_monitor_all     TEXT DEFAULT    '';
    q_grant_monitor_future  TEXT DEFAULT    '';
BEGIN
    -- Grant at DATABASE level for patterns where schema part is a wildcard (e.g. DB.%.%)
    -- Excludes are matched at DB-level only for patterns that also cover the whole database (exclude.part2 = '%')
    rs_database_names := (SHOW DATABASES ->>
                            with cte_includes as (
                                select distinct split_part(ci.VALUE, '.', 1) as db_pattern
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                                where c.PATH = 'plugins.snowpipes.include'
                                    and split_part(ci.VALUE, '.', 2) = '%'
                            )
                            , cte_excludes as (
                                select distinct split_part(ce.VALUE, '.', 1) as db_pattern
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
                                where c.PATH = 'plugins.snowpipes.exclude'
                                    and split_part(ce.VALUE, '.', 2) = '%'
                            )
                            select "name" as name
                            from $1
                            where "kind" = 'STANDARD'
                                and name LIKE ANY (select db_pattern from cte_includes)
                                and not name LIKE ANY (select db_pattern from cte_excludes))
                            ;
    LET c_database_names CURSOR FOR rs_database_names;

    FOR r_db IN c_database_names DO
        LET v_db_name TEXT := r_db.name;
        q_grant_monitor_all := 'grant monitor on all pipes in database identifier(?) to role DTAGENT_VIEWER';
        q_grant_monitor_future := 'grant monitor on future pipes in database identifier(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (v_db_name);
        EXECUTE IMMEDIATE :q_grant_monitor_future USING (v_db_name);
    END FOR;

    -- Grant at SCHEMA level for patterns where schema is specific and pipe is a wildcard (e.g. DB.ANALYTICS.%)
    -- Excludes are matched at schema-level: a candidate schema is suppressed when the full schema FQN
    -- (db_name.schema_name.%) matches any exclude pattern (covers both DB.SCHEMA.% and DB.%.% excludes)
    rs_schema_names := (SHOW DATABASES ->>
                            with cte_includes as (
                                select distinct
                                    split_part(ci.VALUE, '.', 1) as db_pattern,
                                    split_part(ci.VALUE, '.', 2) as schema_name
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                                where c.PATH = 'plugins.snowpipes.include'
                                    and split_part(ci.VALUE, '.', 2) != '%'
                                    and split_part(ci.VALUE, '.', 3) = '%'
                            )
                            , cte_excludes as (
                                select distinct ce.VALUE as exclude_pattern
                                from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce
                                where c.PATH = 'plugins.snowpipes.exclude'
                            )
                            select "name" as db_name, ci.schema_name
                            from $1
                            join cte_includes ci on "name" LIKE ci.db_pattern
                            where "kind" = 'STANDARD'
                                and not ("name" || '.' || ci.schema_name || '.%')
                                    LIKE ANY (select exclude_pattern from cte_excludes))
                            ;
    LET c_schema_names CURSOR FOR rs_schema_names;

    FOR r_schema IN c_schema_names DO
        LET v_schema_fqn TEXT := r_schema.db_name || '.' || r_schema.schema_name;
        q_grant_monitor_all := 'grant monitor on all pipes in schema IDENTIFIER(?) to role DTAGENT_VIEWER';
        q_grant_monitor_future := 'grant monitor on future pipes in schema IDENTIFIER(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (v_schema_fqn);
        EXECUTE IMMEDIATE :q_grant_monitor_future USING (v_schema_fqn);
    END FOR;

    -- Grant at PIPE level for patterns where both schema and pipe parts are specific (e.g. DB.ANALYTICS.MY_PIPE)
    -- Note: FUTURE grants are not applicable at the individual pipe level
    -- Excludes are matched against the full pipe FQN so any exclude pattern covering the pipe suppresses the grant
    rs_pipe_names := (select distinct
                            split_part(ci.VALUE, '.', 1) as db_name,
                            split_part(ci.VALUE, '.', 2) as schema_name,
                            split_part(ci.VALUE, '.', 3) as pipe_name
                        from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci
                        where c.PATH = 'plugins.snowpipes.include'
                            and split_part(ci.VALUE, '.', 2) != '%'
                            and split_part(ci.VALUE, '.', 3) != '%'
                            and not ci.VALUE
                                LIKE ANY (select ce.VALUE
                                          from CONFIG.CONFIGURATIONS c2, table(flatten(c2.VALUE)) ce
                                          where c2.PATH = 'plugins.snowpipes.exclude'));
    LET c_pipe_names CURSOR FOR rs_pipe_names;

    FOR r_pipe IN c_pipe_names DO
        LET v_pipe_fqn TEXT := r_pipe.db_name || '.' || r_pipe.schema_name || '.' || r_pipe.pipe_name;
        q_grant_monitor_all := 'grant monitor on pipe IDENTIFIER(?) to role DTAGENT_VIEWER';

        EXECUTE IMMEDIATE :q_grant_monitor_all USING (v_pipe_fqn);
    END FOR;

    RETURN 'granted monitor for future and pipes to DTAGENT_VIEWER';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GRANT_MONITOR_SNOWPIPES() to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin

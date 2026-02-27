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
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace transient table DTAGENT_DB.APP.TMP_BUDGETS (
        created_on timestamp_ltz, name text,
        database_name text, schema_name text,
        current_version text, comment text, owner text, owner_role_type text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS (
        LIMIT int, BUDGET_NAME text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES (
        LINKED_RESOURCES array, BUDGET_NAME text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.APP.TMP_BUDGET_SPENDING (
        MEASUREMENT_DATE date, SERVICE_TYPE text,
        CREDITS_SPENT float, BUDGET_NAME text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGET_SPENDING to role DTAGENT_VIEWER;

create or replace procedure DTAGENT_DB.APP.P_GET_BUDGETS()
returns text
language sql
execute as owner
as
$$
DECLARE
    v_budgets_json              VARIANT;

    tr_budgets                  TEXT DEFAULT 'truncate table DTAGENT_DB.APP.TMP_BUDGETS;';
    tr_linked_resources         TEXT DEFAULT 'truncate table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES;';
    tr_limits                   TEXT DEFAULT 'truncate table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS;';
    tr_spendings                TEXT DEFAULT 'truncate table DTAGENT_DB.APP.TMP_BUDGET_SPENDING;';

    c_budgets                   CURSOR      for select database_name, name, schema_name from DTAGENT_DB.APP.TMP_BUDGETS;
    budget_name                 TEXT DEFAULT '';
    schema_name                 TEXT DEFAULT '';
    db_name                     TEXT DEFAULT '';

    linked_resources            ARRAY;
    budget_limit                INT;
BEGIN
    EXECUTE IMMEDIATE :tr_budgets;
    EXECUTE IMMEDIATE :tr_linked_resources;
    EXECUTE IMMEDIATE :tr_limits;
    EXECUTE IMMEDIATE :tr_spendings;

    v_budgets_json := (SELECT PARSE_JSON(SYSTEM$SHOW_BUDGETS_IN_ACCOUNT()));
    INSERT INTO DTAGENT_DB.APP.TMP_BUDGETS (created_on, name, database_name, schema_name, current_version, comment, owner, owner_role_type)
        SELECT
            TO_TIMESTAMP_LTZ(b.value:created_on::TEXT)  AS created_on,
            b.value:name::TEXT                          AS name,
            b.value:database_name::TEXT                 AS database_name,
            b.value:schema_name::TEXT                   AS schema_name,
            b.value:current_version::TEXT               AS current_version,
            b.value:comment::TEXT                       AS comment,
            b.value:owner::TEXT                         AS owner,
            b.value:owner_role_type::TEXT               AS owner_role_type
        FROM TABLE(FLATTEN(input => :v_budgets_json)) b;

    FOR budget IN c_budgets DO
        budget_name := budget.name;
        schema_name := budget.schema_name;
        db_name := budget.database_name;
        execute immediate 'call ' || :db_name || '.' || :schema_name || '.' || :budget_name || '!GET_LINKED_RESOURCES();';
        select
            name as "snowflake.budget.resource.name",
            domain as "snowflake.budget.resource.domain",
            database_name as "db.namespace",
            schema_name as "snowflake.schema.name"
        from table(result_scan(last_query_id()));

        linked_resources := (select top 1 array_agg(object_construct(*)) from table(result_scan(last_query_id(-1))));
        INSERT INTO DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES(LINKED_RESOURCES, BUDGET_NAME) SELECT :linked_resources, :budget_name;

        execute immediate 'call ' || :db_name || '.' || :schema_name || '.' || :budget_name || '!GET_SPENDING_LIMIT();';
        budget_limit := (select top 1 "GET_SPENDING_LIMIT" from table(result_scan(last_query_id(-1))));
        INSERT INTO DTAGENT_DB.APP.TMP_BUDGETS_LIMITS(LIMIT, BUDGET_NAME) SELECT :budget_limit, :budget_name;

        execute immediate 'call ' || :db_name || '.' || :schema_name || '.' || :budget_name || '!GET_SPENDING_HISTORY(TIME_LOWER_BOUND => DATEADD(days, -1, CURRENT_TIMESTAMP()), TIME_UPPER_BOUND => CURRENT_TIMESTAMP());';

        insert into DTAGENT_DB.APP.TMP_BUDGET_SPENDING(MEASUREMENT_DATE, SERVICE_TYPE, CREDITS_SPENT, BUDGET_NAME)
            select "MEASUREMENT_DATE", "SERVICE_TYPE", "CREDITS_SPENT", :budget_name from table(result_scan(last_query_id(-1)));

    END FOR;

    RETURN 'tables APP.TMP_BUDGETS, APP.TMP_BUDGETS_RESOURCES, APP.TMP_BUDGETS_LIMITS, APP.TMP_BUDGET_SPENDING updated';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GET_BUDGETS() to role DTAGENT_VIEWER;

-- use role DTAGENT_VIEWER;
-- call DTAGENT_DB.APP.P_GET_BUDGETS();
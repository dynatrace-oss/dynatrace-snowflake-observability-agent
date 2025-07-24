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

create transient table if not exists DTAGENT_DB.APP.TMP_BUDGETS (
        created_on timestamp_ltz, name text, 
        database_name text, schema_name text, 
        current_version text, comment text, owner text, owner_role_type text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.APP.TMP_BUDGETS_LIMITS (
        LIMIT int, BUDGET_NAME text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES (
        LINKED_RESOURCES array, BUDGET_NAME text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.APP.TMP_BUDGET_SPENDING (
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
    q_get_budgets               TEXT DEFAULT 'show SNOWFLAKE.CORE.BUDGET;';
    q_pop_budgets               TEXT DEFAULT 'insert into DTAGENT_DB.APP.TMP_BUDGETS select * from table(result_scan(last_query_id()));';

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

    EXECUTE IMMEDIATE :q_get_budgets;
    EXECUTE IMMEDIATE :q_pop_budgets;

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

use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS_RESOURCES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGETS_LIMITS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_BUDGET_SPENDING to role DTAGENT_ADMIN copy current grants;

-- use role DTAGENT_VIEWER;
-- call DTAGENT_DB.APP.P_GET_BUDGETS();
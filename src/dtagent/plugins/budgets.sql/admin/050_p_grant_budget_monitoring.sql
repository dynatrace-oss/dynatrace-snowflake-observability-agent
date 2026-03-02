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
-- APP.P_GRANT_BUDGET_MONITORING() grants DTAGENT_VIEWER the necessary privileges
-- to monitor custom budgets configured in CONFIG.CONFIGURATIONS.
--
-- !! Must be invoked after creation of CONFIG.CONFIGURATIONS table
-- !! Requires DTAGENT_ADMIN role (admin deployment scope)
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.APP.P_GRANT_BUDGET_MONITORING()
returns text
language sql
execute as caller
as
$$
DECLARE
    c_budgets                   CURSOR FOR
                                    SELECT ci.VALUE::TEXT AS budget_fqn
                                    FROM CONFIG.CONFIGURATIONS c, TABLE(FLATTEN(c.VALUE)) ci
                                    WHERE c.PATH = 'plugins.budgets.monitored_budgets';

    budget_fqn                  TEXT DEFAULT '';
    budget_db                   TEXT DEFAULT '';
    budget_schema               TEXT DEFAULT '';
    budget_name                 TEXT DEFAULT '';

    q_grant_usage_db            TEXT DEFAULT '';
    q_grant_usage_schema        TEXT DEFAULT '';
    q_grant_budget_viewer       TEXT DEFAULT '';
    q_grant_usage_viewer        TEXT DEFAULT '';

    grants_count                INT DEFAULT 0;
BEGIN
    q_grant_usage_viewer := 'grant database role SNOWFLAKE.USAGE_VIEWER to role DTAGENT_VIEWER;';
    EXECUTE IMMEDIATE :q_grant_usage_viewer;

    FOR r_budget IN c_budgets DO
        budget_fqn    := r_budget.budget_fqn;
        budget_db     := SPLIT_PART(:budget_fqn, '.', 1);
        budget_schema := SPLIT_PART(:budget_fqn, '.', 2);
        budget_name   := SPLIT_PART(:budget_fqn, '.', 3);

        q_grant_usage_db     := 'grant usage on database ' || :budget_db || ' to role DTAGENT_VIEWER;';
        q_grant_usage_schema := 'grant usage on schema ' || :budget_db || '.' || :budget_schema || ' to role DTAGENT_VIEWER;';
        q_grant_budget_viewer := 'grant snowflake.core.budget role ' || :budget_fqn || '!VIEWER to role DTAGENT_VIEWER;';

        EXECUTE IMMEDIATE :q_grant_usage_db;
        EXECUTE IMMEDIATE :q_grant_usage_schema;
        EXECUTE IMMEDIATE :q_grant_budget_viewer;

        grants_count := :grants_count + 1;
    END FOR;

    RETURN 'granted budget monitoring privileges for ' || :grants_count || ' budget(s) to DTAGENT_VIEWER';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);

    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GRANT_BUDGET_MONITORING() to role DTAGENT_ADMIN;
--%:OPTION:dtagent_admin

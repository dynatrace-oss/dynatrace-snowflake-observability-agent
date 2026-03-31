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

    budget_db_q                 TEXT DEFAULT '';
    budget_schema_q             TEXT DEFAULT '';
    budget_fqn_q                TEXT DEFAULT '';

    safe_identifier_re          TEXT DEFAULT '^[A-Za-z_][A-Za-z0-9_$]*$';

    grants_count                INT DEFAULT 0;
BEGIN
    FOR r_budget IN c_budgets DO
        budget_fqn    := r_budget.budget_fqn;
        budget_db     := UPPER(SPLIT_PART(:budget_fqn, '.', 1));
        budget_schema := UPPER(SPLIT_PART(:budget_fqn, '.', 2));
        budget_name   := UPPER(SPLIT_PART(:budget_fqn, '.', 3));

        IF (NOT REGEXP_LIKE(:budget_db,     :safe_identifier_re)
         OR NOT REGEXP_LIKE(:budget_schema, :safe_identifier_re)
         OR NOT REGEXP_LIKE(:budget_name,   :safe_identifier_re)) THEN
            SYSTEM$LOG_WARN('P_GRANT_BUDGET_MONITORING: skipping invalid budget FQN (unsafe identifier): ' || :budget_fqn);
            CONTINUE;
        END IF;

        budget_db_q     := '"' || :budget_db     || '"';
        budget_schema_q := :budget_db_q || '.' || '"' || :budget_schema || '"';
        budget_fqn_q    := :budget_schema_q || '."' || :budget_name || '"';

        -- For imported/shared databases (e.g. SNOWFLAKE) GRANT USAGE is not allowed;
        -- GRANT IMPORTED PRIVILEGES must be used instead.  Attempt the standard grant
        -- first and fall back to the imported-privileges form on error.
        BEGIN
            EXECUTE IMMEDIATE concat('grant usage on database ', :budget_db_q, ' to role DTAGENT_VIEWER;');
        EXCEPTION
            WHEN STATEMENT_ERROR THEN
                EXECUTE IMMEDIATE concat('grant imported privileges on database ', :budget_db_q, ' to role DTAGENT_VIEWER;');
        END;

        -- Schema-level GRANT USAGE is not applicable for imported databases (the
        -- imported-privileges grant already covers all schemas).  Skip on error.
        BEGIN
            EXECUTE IMMEDIATE concat('grant usage on schema ', :budget_schema_q, ' to role DTAGENT_VIEWER;');
        EXCEPTION
            WHEN STATEMENT_ERROR THEN
                SYSTEM$LOG_INFO('P_GRANT_BUDGET_MONITORING: skipping schema grant for imported database ' || :budget_db_q);
        END;

        -- For the SNOWFLAKE application (e.g. ACCOUNT_ROOT_BUDGET) the instance-role
        -- grant is not permitted; access is controlled via the SNOWFLAKE.BUDGET_VIEWER
        -- application role which is already granted unconditionally above.  Skip on error.
        BEGIN
            EXECUTE IMMEDIATE concat('grant snowflake.core.budget role ', :budget_fqn_q, '!VIEWER to role DTAGENT_VIEWER;');
        EXCEPTION
            WHEN STATEMENT_ERROR THEN
                SYSTEM$LOG_INFO('P_GRANT_BUDGET_MONITORING: skipping budget instance-role grant for ' || :budget_fqn_q || ' (application-owned budget — SNOWFLAKE.BUDGET_VIEWER app role covers access)');
        END;

        grants_count := :grants_count + 1;
    END FOR;

    -- NOTE: SNOWFLAKE.USAGE_VIEWER is granted during init (009_budget_init.sql) by ACCOUNTADMIN.
    -- Attempting that grant here (EXECUTE AS CALLER) would fail for callers that lack the
    -- MANAGE GRANTS privilege.  The init step is the correct place for account-level database
    -- role grants; no action needed here.

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

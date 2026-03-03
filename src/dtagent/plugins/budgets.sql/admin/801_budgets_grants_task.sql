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
--  This task periodically calls P_GRANT_BUDGET_MONITORING() to keep budget
--  monitoring grants in sync with the configured monitored_budgets list.
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 30 */12 * * * UTC' -- every 12 hours at 00:30, 12:30 UTC
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.P_GRANT_BUDGET_MONITORING();

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS to role DTAGENT_ADMIN revoke current grants;
grant monitor on task DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS to role DTAGENT_VIEWER;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_BUDGETS_GRANTS suspend;
--%:OPTION:dtagent_admin

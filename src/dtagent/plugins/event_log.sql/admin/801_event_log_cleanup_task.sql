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
--  This task ensures Dynatrace Snowflake Observability Agent is called periodically
--
--%OPTION:dtagent_admin:
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

-- IMPORTANT: this task is executed as DTAGENT_ADMIN, so it can alter EVENT_LOG table
-- we wanted to run this task after TASK_DTAGENT_EVENT_LOG to ensure data is cleaned
-- but according to Snowflake documentation:
--  "All tasks in a task graph must have the same task owner. A single role must have the OWNERSHIP privilege on all of the tasks in the task graph."


create or replace task DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 0 * * * * UTC' -- every hour at 00:00, 01:00, 02:00, ..., 23:00 UTC
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.P_CLEANUP_EVENT_LOG();

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP to role DTAGENT_ADMIN revoke current grants;
grant monitor on task DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP to role DTAGENT_VIEWER;
alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_EVENT_LOG_CLEANUP suspend;
--%:OPTION:dtagent_admin
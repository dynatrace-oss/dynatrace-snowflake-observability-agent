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
--  This task collects clustering information and then invokes the table_health
--  plugin for the table_clustering context.  Runs every 6 hours offset by 1 hour
--  from the storage task to avoid warehouse contention.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_CLUSTERING
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 0 1,7,13,19 * * * UTC' -- every 6 hours at 01:00, 07:00, 13:00, 19:00 UTC
    allow_overlapping_execution = FALSE
as
begin
    call DTAGENT_DB.APP.P_COLLECT_CLUSTERING_INFO();
    call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('table_health:table_clustering'));
end;

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_CLUSTERING to role DTAGENT_VIEWER revoke current grants;
grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_CLUSTERING to role DTAGENT_VIEWER;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_CLUSTERING resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_CLUSTERING suspend;

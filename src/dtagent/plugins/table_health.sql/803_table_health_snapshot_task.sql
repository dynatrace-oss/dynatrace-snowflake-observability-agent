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
--  This task snapshots table health history and then invokes the table_health
--  plugin for the table_health_derived context.  Runs every 6 hours offset by
--  2 hours from the storage task (after clustering has completed) to ensure
--  both storage and clustering data are fresh before snapshotting.
--
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT
    warehouse = DTAGENT_WH
    schedule = 'USING CRON 0 2,8,14,20 * * * UTC' -- every 6 hours at 02:00, 08:00, 14:00, 20:00 UTC
    allow_overlapping_execution = FALSE
as
begin
    call DTAGENT_DB.APP.P_SNAPSHOT_TABLE_HEALTH();
    call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('table_health:table_health_derived'));
end;

grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT to role DTAGENT_VIEWER revoke current grants;
grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT to role DTAGENT_VIEWER;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_TABLE_HEALTH_SNAPSHOT suspend;

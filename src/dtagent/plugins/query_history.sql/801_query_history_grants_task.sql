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
--
--  This task ensures Dynatrace Snowflake Observability Agent is called periodically
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;  

-- IMPORTANT: this task is executed as DTAGENT_ADMIN, so it can grant MONITOR privilege to DTAGENT_VIEWER
-- we wanted to run this task before TASK_DTAGENT_QUERY_HISTORY to ensure that all warehouses are monitored
-- but according to Snowflake documentation: 
--  "All tasks in a task graph must have the same task owner. A single role must have the OWNERSHIP privilege on all of the tasks in the task graph."

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS
    warehouse = DTAGENT_WH
    schedule = 'USING CRON */30 * * * * UTC' -- every 30 minutes at 00:00, 00:30, 01:00, ..., 23:30 UTC
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.P_MONITOR_WAREHOUSES();


grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS to role DTAGENT_VIEWER;
alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_QUERY_HISTORY_GRANTS resume;


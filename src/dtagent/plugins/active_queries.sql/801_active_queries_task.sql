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

create or replace task DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES
    warehouse = DTAGENT_WH
    schedule = 'USING CRON */6 * * * * UTC'
    allow_overlapping_execution = FALSE
as
    call DTAGENT_DB.APP.DTAGENT(ARRAY_CONSTRUCT('active_queries'));
    
grant ownership on task DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES to role DTAGENT_VIEWER revoke current grants;
grant operate, monitor on task DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES to role DTAGENT_VIEWER;
alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES resume;

-- alter task if exists DTAGENT_DB.APP.TASK_DTAGENT_ACTIVE_QUERIES suspend;

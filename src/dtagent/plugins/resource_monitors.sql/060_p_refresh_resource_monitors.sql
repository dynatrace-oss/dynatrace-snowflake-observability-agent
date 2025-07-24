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
-- APP.P_REFRESH_RESOURCE_MONITORS() will recreate two transient table with information on currently present resource monitors:
-- * APP.TMP_RESOURCE_MONITORS
-- * APP.TMP_WAREHOUSES
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create transient table if not exists APP.TMP_RESOURCE_MONITORS(
        name text, 
        credit_quota text, used_credits text, remaining_credits text, level text, frequency text, 
        start_time timestamp_ltz, end_time timestamp_ltz, 
        notify_at text, suspend_at text, suspend_immediately_at text, 
        created_on timestamp_ltz, 
        owner text, comment text, notify_users text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table APP.TMP_RESOURCE_MONITORS to role DTAGENT_VIEWER;

create transient table if not exists APP.TMP_WAREHOUSES(
            name text, state text, type text, size text, 
            min_cluster_count int, max_cluster_count int, 
            started_clusters int, running int, queued int, 
            is_default text, is_current text, auto_suspend int, auto_resume text, 
            available text, provisioning text, quiescing text, other text, 
            created_on timestamp_ltz, resumed_on timestamp_ltz, updated_on timestamp_ltz, 
            owner text, comment text, enable_query_acceleration text, query_acceleration_max_scale_factor text, 
            resource_monitor text, 
            actives int, pendings int, failed int, suspended int, 
            uuid text, scaling_policy text, budget text, 
            owner_role_type text, resource_constraint text) 
        DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table APP.TMP_WAREHOUSES to role DTAGENT_VIEWER;
create or replace procedure DTAGENT_DB.APP.P_REFRESH_RESOURCE_MONITORS()
returns text
language sql
execute as owner
as
$$
DECLARE
    tr_tmp_resource_monitors    TEXT DEFAULT 'truncate table APP.TMP_RESOURCE_MONITORS;';
    q_show_resource_monitors    TEXT DEFAULT 'show resource monitors;';
    q_pop_tmp_res_mon           TEXT DEFAULT 'insert into APP.TMP_RESOURCE_MONITORS select * from table(result_scan(last_query_id()));';

    tr_tmp_warehouses           TEXT DEFAULT 'truncate table APP.TMP_WAREHOUSES;';
    q_show_warehouses           TEXT DEFAULT 'show warehouses;';
    q_pop_tmp_wh                TEXT DEFAULT 'insert into APP.TMP_WAREHOUSES select * from table(result_scan(last_query_id()));';

BEGIN
    EXECUTE IMMEDIATE :tr_tmp_resource_monitors;
    EXECUTE IMMEDIATE :q_show_resource_monitors;
    EXECUTE IMMEDIATE :q_pop_tmp_res_mon;

    EXECUTE IMMEDIATE :tr_tmp_warehouses;
    EXECUTE IMMEDIATE :q_show_warehouses;
    EXECUTE IMMEDIATE :q_pop_tmp_wh;

    RETURN 'tables APP.TMP_RESOURCE_MONITORS, APP.TMP_WAREHOUSES updated';
EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_REFRESH_RESOURCE_MONITORS() to role DTAGENT_VIEWER;
alter procedure DTAGENT_DB.APP.P_REFRESH_RESOURCE_MONITORS() set LOG_LEVEL = WARN;

use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_RESOURCE_MONITORS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_WAREHOUSES to role DTAGENT_ADMIN copy current grants;

-- use role DTAGENT_VIEWER;
-- call DTAGENT_DB.APP.P_REFRESH_RESOURCE_MONITORS();
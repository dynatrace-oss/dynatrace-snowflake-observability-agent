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
    q_pop_tmp_res_mon           TEXT DEFAULT 'insert into APP.TMP_RESOURCE_MONITORS select 
                                                "name", 
                                                "credit_quota", "used_credits", "remaining_credits", "level", "frequency", 
                                                "start_time", "end_time", 
                                                "notify_at", "suspend_at", "suspend_immediately_at", 
                                                "created_on", 
                                                "owner", "comment", "notify_users" 
                                              from table(result_scan(last_query_id()));';

    tr_tmp_warehouses           TEXT DEFAULT 'truncate table APP.TMP_WAREHOUSES;';
    q_show_warehouses           TEXT DEFAULT 'show warehouses;';
    q_pop_tmp_wh                TEXT DEFAULT 'insert into APP.TMP_WAREHOUSES select 
                                                "name", "state", "type", "size", 
                                                "min_cluster_count", "max_cluster_count", 
                                                "started_clusters", "running", "queued", 
                                                "is_default", "is_current", "auto_suspend", "auto_resume", 
                                                "available", "provisioning", "quiescing", "other", 
                                                "created_on", "resumed_on", "updated_on", 
                                                "owner", "comment", "enable_query_acceleration", "query_acceleration_max_scale_factor", 
                                                "resource_monitor", 
                                                "actives", "pendings", "failed", "suspended", 
                                                -- The "budget" column does not exist in the source data, but is required by the target table schema.
                                                -- Insert a hardcoded NULL to maintain column alignment with APP.TMP_WAREHOUSES.
                                                "uuid", "scaling_policy", null as "budget", 
                                                "owner_role_type", "resource_constraint" 
                                              from table(result_scan(last_query_id()));';

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
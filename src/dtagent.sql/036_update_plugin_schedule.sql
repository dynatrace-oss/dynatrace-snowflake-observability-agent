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
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH; 

-- upgrade from version <0.8.3
drop procedure if exists DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE(varchar);
create or replace procedure DTAGENT_DB.CONFIG.UPDATE_TASK_SCHEDULE(
    PLUGIN_NAME varchar, 
    AUX_TASK_NAME varchar default null)
returns varchar not null
language SQL
execute as caller
as
$$
declare
    SCHEDULE varchar;
    SCHEDULE_PATH varchar;
    TASK_NAME varchar;
    ALTER_TASK_STMT varchar;
    AUX_SUFFIX varchar default '';
begin
    if (AUX_TASK_NAME is not null) then
        AUX_SUFFIX := concat('_', upper(AUX_TASK_NAME));
    end if;

    SCHEDULE_PATH := concat('plugins.', PLUGIN_NAME, '.schedule', AUX_SUFFIX);
    SCHEDULE := (select VALUE from CONFIG.CONFIGURATIONS where PATH = :SCHEDULE_PATH);

    TASK_NAME := concat('DTAGENT_DB.APP.TASK_DTAGENT_', upper(PLUGIN_NAME), AUX_SUFFIX);
    ALTER_TASK_STMT := concat('alter task if exists ', TASK_NAME);

    if (SCHEDULE is not null) then
        if (trim(lower(left(SCHEDULE, 6))) = 'after ') then
            -- Remove existing schedule if present
            execute immediate concat(ALTER_TASK_STMT, ' unset schedule allow_overlapping_execution;');
            -- Set the AFTER dependency
            execute immediate concat(ALTER_TASK_STMT, ' add ', SCHEDULE, ';');
        else
            -- Get the current predecessors (AFTER dependencies) for the task
            execute immediate concat('describe task ', TASK_NAME);
            let C_PREDECESSORS CURSOR for select distinct value as predecessor 
                                          from table(flatten(input => (select "predecessors" from table(result_scan(last_query_id())))));
            
            -- Remove any AFTER dependency if present
            for REC in C_PREDECESSORS do
                execute immediate concat(ALTER_TASK_STMT, ' remove after ', REC.predecessor, ';');
            end for;

            -- Set the schedule
            execute immediate concat(ALTER_TASK_STMT, ' set schedule=''', SCHEDULE, ''' allow_overlapping_execution = FALSE;');
        end if;

        return concat('updated schedule for task ', TASK_NAME, ' to ', SCHEDULE);
    end if;

    return concat('no schedule found for task ', TASK_NAME);
exception
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return SQLERRM;
end;
$$
;

grant usage on procedure DTAGENT_DB.CONFIG.UPDATE_TASK_SCHEDULE(varchar, varchar) to role DTAGENT_VIEWER;


-- 


create or replace procedure DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE(
        PLUGIN_NAME varchar, 
        AUX_TASK_NAMES array default array_construct())
returns varchar not null
language SQL
execute as caller
as
$$
declare
    UPPER_PLUGIN_NAME varchar;
    SCHEDULE varchar;
    SCHEDULE_PATH varchar;
    ALL_TASK_NAMES array;
    AUX_TASK_NAME varchar;
    IS_DISABLED_BY_DEFAULT boolean default false;
    IS_DISABLED boolean default false;
    IS_ENABLED boolean default false;
begin
    UPPER_PLUGIN_NAME := upper(:PLUGIN_NAME);

    -- validate the plugin configuration schedule
    SCHEDULE_PATH := 'plugins.' || :PLUGIN_NAME || '.schedule'; 
    SCHEDULE := (select VALUE from CONFIG.CONFIGURATIONS where PATH = :SCHEDULE_PATH);
    
    if (SCHEDULE is null) then
        return 'invalid plugin name or plugin schedule not uploaded to config table';
    end if;

    -- we construct the list of all task names related to the plugin
    ALL_TASK_NAMES := array_construct(concat('DTAGENT_DB.APP.TASK_DTAGENT_', :UPPER_PLUGIN_NAME));
    if (AUX_TASK_NAMES is not null) then
        for i in 0 to array_size(:AUX_TASK_NAMES)-1 do
            ALL_TASK_NAMES := array_cat(ALL_TASK_NAMES, 
                              array_construct(concat('DTAGENT_DB.APP.TASK_DTAGENT_', :UPPER_PLUGIN_NAME, '_', :AUX_TASK_NAMES[i])));
        end for;
    end if;

    IS_DISABLED_BY_DEFAULT := NVL((select VALUE::boolean from DTAGENT_DB.CONFIG.CONFIGURATIONS where PATH = 'plugins.disabled_by_default'), false);
    IS_DISABLED := NVL((select VALUE::boolean from DTAGENT_DB.CONFIG.CONFIGURATIONS where PATH = 'plugins.' || :PLUGIN_NAME || '.is_disabled'), false);
    IS_ENABLED := NVL((select VALUE::boolean from DTAGENT_DB.CONFIG.CONFIGURATIONS where PATH = 'plugins.' || :PLUGIN_NAME || '.is_enabled'), false);

    -- if the plugin is disabled, we suspend all tasks related to the plugin and return a message
    if (IS_DISABLED or (IS_DISABLED_BY_DEFAULT and not IS_ENABLED)) then  
        -- if the plugin is disabled, we suspend the task and return a message
        for i in 0 to array_size(:ALL_TASK_NAMES) - 1 do
            execute immediate concat('alter task if exists ', :ALL_TASK_NAMES[i], ' suspend;');
        end for;      
        return concat('plugin ', :PLUGIN_NAME, ' is disabled (globally = ', :IS_DISABLED_BY_DEFAULT, ')');
    end if;

    -- if the plugin is enabled, we update the schedule for all tasks related to the plugin

    -- we first suspend all tasks related to the plugin to avoid overlapping executions
    for i in 0 to array_size(:ALL_TASK_NAMES) - 1 do
        execute immediate concat('alter task if exists ', :ALL_TASK_NAMES[i], ' suspend;');
    end for;      

    -- we update the schedule for the main task of the plugin
    call DTAGENT_DB.CONFIG.UPDATE_TASK_SCHEDULE(:PLUGIN_NAME);

    -- we update the schedule for auxiliary tasks if provided
    if (AUX_TASK_NAMES is not null) then
        for i in 0 to array_size(:AUX_TASK_NAMES) - 1 do
            AUX_TASK_NAME := :AUX_TASK_NAMES[i];
            call DTAGENT_DB.CONFIG.UPDATE_TASK_SCHEDULE(:PLUGIN_NAME, :AUX_TASK_NAME);
        end for;
    end if;

    -- we resume all tasks related to the plugin after updating the schedule
    for i in 0 to array_size(:ALL_TASK_NAMES) - 1 do
        AUX_TASK_NAME := ALL_TASK_NAMES[i];
        execute immediate concat('alter task if exists ', :AUX_TASK_NAME, ' resume;');
    end for;      

    return 'schedule for ' || :PLUGIN_NAME || ' plugin set to ' || :SCHEDULE;
exception
    when statement_error then
        return SQLERRM;
end;
$$
;

grant usage on procedure DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE(varchar, array) to role DTAGENT_VIEWER;

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

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_ALL_PLUGINS_SCHEDULE()
returns text
language SQL
execute as caller
as
$$
declare
    c_plugins               CURSOR  for select 
                                        split_part(PATH, '.', 2) as plugin_name,
                                        array_agg(
                                            case 
                                                when PATH like 'plugins.%.schedule_%' then split_part(PATH, '_', -1)
                                                else null
                                            end
                                        ) as aux_names
                                    from DTAGENT_DB.CONFIG.CONFIGURATIONS 
                                    where PATH like '%.schedule%'
                                    group by all;
    plugin_name             TEXT;
    aux_names               ARRAY;
    schedule_update_proc    TEXT;
begin
    for entry in c_plugins do
        plugin_name := entry.plugin_name;
        aux_names := entry.aux_names;
        call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE(:plugin_name, :aux_names);
    end for;

    return 'updated config for all plugins';
exception
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return SQLERRM;
end;
$$
;

grant usage on procedure DTAGENT_DB.CONFIG.UPDATE_ALL_PLUGINS_SCHEDULE() to role DTAGENT_VIEWER;

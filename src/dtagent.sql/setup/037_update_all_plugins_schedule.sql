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
use role DTAGENT_OWNER; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

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

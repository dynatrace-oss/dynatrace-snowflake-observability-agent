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
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.CONFIG.UPDATE_QUERY_HISTORY_CONF()
returns text
language SQL
execute as caller
as
$$
begin
    call DTAGENT_DB.CONFIG.UPDATE_PLUGIN_SCHEDULE('query_history', array_construct('grants'));

    return 'query_history plugin config updated';
exception
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return SQLERRM;
end;
$$
;

grant usage on procedure DTAGENT_DB.CONFIG.UPDATE_QUERY_HISTORY_CONF() to role DTAGENT_VIEWER;

-- call DTAGENT_DB.CONFIG.UPDATE_QUERY_HISTORY_CONF();
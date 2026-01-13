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
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

drop table if exists DTAGENT_DB.CONFIG.CONFIGURATION;
create table if not exists DTAGENT_DB.CONFIG.CONFIGURATIONS (
    PATH            varchar     not null,
    VALUE           variant     not null,
    TYPE            varchar     not null
);

grant update on CONFIG.CONFIGURATIONS to role DTAGENT_ADMIN;
grant select on CONFIG.CONFIGURATIONS to role DTAGENT_VIEWER;
create temp table if not exists TEMP_CONFIG(DATA variant);

--%UPLOAD:CONFIG
-- will be replaced with INSERT code ingested here:
put file://config.json @%TEMP_CONFIG;
list @%TEMP_CONFIG;
copy into TEMP_CONFIG from '@%TEMP_CONFIG/config.json' file_format = (type=JSON);
--%:UPLOAD:CONFIG

merge into DTAGENT_DB.CONFIG.CONFIGURATIONS c using (
    select 
        PARSE_JSON(data):PATH::string    as PATH,
        PARSE_JSON(data):VALUE::variant  as VALUE,
        PARSE_JSON(data):TYPE::string    as TYPE,
    from TEMP_CONFIG
    ) t
    on t.PATH = c.PATH
        when matched then 
            update set VALUE = t.VALUE::variant, 
                        TYPE = t.TYPE::string
        when not matched then
            insert (PATH, VALUE, TYPE) VALUES (
                    t.PATH::string, 
                    t.VALUE::variant, 
                    t.TYPE::string
                );

--%UPLOAD:SKIP:
remove @%TEMP_CONFIG pattern='.*.json.gz';
--%:UPLOAD:SKIP
drop table if exists TEMP_CONFIG;

/*
use role DTAGENT_VIEWER; 
use schema DTAGENT_DB.CONFIG; 
use warehouse DTAGENT_WH;
select path, value, type from CONFIG.CONFIGURATIONS;
 */

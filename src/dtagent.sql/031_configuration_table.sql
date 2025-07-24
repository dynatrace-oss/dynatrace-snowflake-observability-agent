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

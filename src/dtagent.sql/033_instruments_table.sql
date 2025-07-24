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
-- Setting up instruments table
-- This table contains information on all dimensions and metrics we will deliver to DT
-- The content of the table is initialized with data from intruments-def.json
-- HINT: use `./deploy.sh $ENV 033` to reinitialize the table
-- 
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

-- this table will keep content of instruments-def.json available for scripts
create table if not exists CONFIG.INSTRUMENTS (
    TYPE varchar not null,
    KEY varchar not null,
    VALUE variant not null
);

-- app admin can update app config from outside streamlit if they like
grant update on CONFIG.INSTRUMENTS to role DTAGENT_ADMIN;
grant select on CONFIG.INSTRUMENTS to role DTAGENT_VIEWER;

-- loading data from instruments-def.yml
create temp table if not exists TEMP_INSTRUMENTS(DATA variant);

--%UPLOAD:INSTRUMENTS
-- will be replaced with INSERT code ingested here:
put file://instruments-def.json @%TEMP_INSTRUMENTS;
list @%TEMP_INSTRUMENTS;
copy into TEMP_INSTRUMENTS from '@%TEMP_INSTRUMENTS/instruments-def.json' file_format = (type=JSON);
--%:UPLOAD:INSTRUMENTS

truncate CONFIG.INSTRUMENTS;
insert into CONFIG.INSTRUMENTS
select
    first_level.KEY     as j_key,
    second_level.KEY,
    second_level.VALUE
from TEMP_INSTRUMENTS, 
     table(flatten(parse_json(DATA))) as first_level,
     table(flatten(first_level.VALUE))  as second_level
;

--%UPLOAD:SKIP:
remove @%TEMP_INSTRUMENTS pattern='.*.json.gz';
--%:UPLOAD:SKIP
drop table if exists TEMP_INSTRUMENTS;

-- creating convenience view for getting info into dtagent
create or replace view CONFIG.V_INSTRUMENTS
as
select 
    OBJECT_AGG(type, v::variant) as data
from (
    select 
        type, 
        OBJECT_AGG(key, value::variant) as v 
    from 
        CONFIG.INSTRUMENTS
    group by all
) 
group by all
;
grant select on CONFIG.V_INSTRUMENTS to role DTAGENT_VIEWER;

-- select * from CONFIG.INSTRUMENTS;
-- select * from CONFIG.V_INSTRUMENTS;

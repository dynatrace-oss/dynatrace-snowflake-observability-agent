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

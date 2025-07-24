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
-- APP.LOG_PROCESSED_MEASUREMENTS() will update the log of measurement sources processed in STATUS.PROCESSED_MESAUREMENTS_LOG
-- 
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace procedure DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS(
    measurements_source text,
    last_timestamp      text,
    last_id             text,
    entries_count       text
)
returns text
language sql
as
$$
declare
    inserted_queries int;
begin
    insert into DTAGENT_DB.STATUS.PROCESSED_MEASUREMENTS_LOG
    select 
        current_timestamp   as process_time, 
        column1             as measurements_source,
        column2             as last_timestamp,
        column3             as last_id,
        parse_json(column4) as entries_count
    from values
    (
        :measurements_source,
        :last_timestamp,
        :last_id,
        :entries_count
    );

    return 'ok';
end;
$$
;

grant usage on procedure DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS(text, text, text, text) to role DTAGENT_VIEWER;

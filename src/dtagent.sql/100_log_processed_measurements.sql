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

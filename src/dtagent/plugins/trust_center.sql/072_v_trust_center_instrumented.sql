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
create or replace view DTAGENT_DB.APP.V_TRUST_CENTER_INSTRUMENTED
as
select
    concat('[', tcf.severity, '] ', tcf.scanner_name, ' ', tcf.scanner_short_description)                       as _MESSAGE,
    tcf.severity                                                                                                as _SEVERITY,
    case
        when tcf.completion_status='SUCCEEDED'          then 'OK'
        when length(NVL(tcf.completion_status, '')) > 0 then 'ERROR'
                                                        else 'UNSET'
        end                                                                                                     as STATUS_CODE,

    extract(epoch_nanosecond from tcf.start_timestamp)                                                          as START_TIME,
    extract(epoch_nanosecond from tcf.start_timestamp)                                                          as EVENT_START,
    extract(epoch_nanosecond from tcf.end_timestamp)                                                            as EVENT_END,
    extract(epoch_nanosecond from tcf.created_on)                                                               as TIMESTAMP,
    
    -- metric and span dimensions
    OBJECT_CONSTRUCT(
        'event.category',                                           IFF(tcf.severity = 'LOW', 
                                                                        'Warning', 
                                                                        'Vulnerability management'),
        'vulnerability.risk.level',                                 coalesce(tcf.severity, 'NONE'),
        'snowflake.trust_center.scanner.id',                        tcf.scanner_id,
        'snowflake.trust_center.scanner.type',                      tcf.scanner_type,
        'snowflake.trust_center.scanner.package.id',                tcf.scanner_package_id
    )                                                                                                            as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'status.message',                                           _MESSAGE,
        'error.code',                                               tcf.scanner_id,
        'event.id',                                                 tcf.event_id,
        'event.kind',                                               'SECURITY_EVENT',
        'snowflake.trust_center.scanner.name',                      tcf.scanner_name,
        'snowflake.trust_center.scanner.description',               tcf.scanner_short_description,
        'snowflake.trust_center.scanner.package.name',              tcf.scanner_package_name,
        'snowflake.entity.id',                                      ate.value:entity_id,
        'snowflake.entity.name',                                    ate.value:entity_name,
        'snowflake.entity.type',                                    ate.value:entity_object_type,
        'snowflake.entity.details',                                 coalesce(ate.value:entity_detail, 
                                                                             ate.value:entity_details)
    )
                                                                                                                as ATTRIBUTES
from DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS tcf
   , lateral flatten (input => IFF(DTAGENT_DB.APP.F_GET_CONFIG_VALUE('plugins.trust_center.log_details', FALSE)::boolean, AT_RISK_ENTITIES, []), path=>'', outer=>TRUE) ate
order by
    tcf.created_on asc
;

grant select on table DTAGENT_DB.APP.V_TRUST_CENTER_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TRUST_CENTER_INSTRUMENTED
limit 10;
*/
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
   , lateral flatten (input => IFF(DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.trust_center.log_details', FALSE)::boolean, AT_RISK_ENTITIES, []), path=>'', outer=>TRUE) ate
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
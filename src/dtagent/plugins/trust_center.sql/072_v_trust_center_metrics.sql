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
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_TRUST_CENTER_METRICS
as
select
    extract(epoch_nanosecond from current_timestamp())                                                            as TIMESTAMP,

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
    )
                                                                                                                as ATTRIBUTES,
    OBJECT_CONSTRUCT(
        'snowflake.trust_center.findings',                    tcf.total_at_risk_count
    )
                                                                                                                as METRICS
from DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS tcf
;

grant select on table DTAGENT_DB.APP.V_TRUST_CENTER_METRICS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TRUST_CENTER_METRICS
limit 10;
*/
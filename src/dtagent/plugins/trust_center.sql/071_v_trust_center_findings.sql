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
use role DTAGENT_OWNER;  use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace view DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS
as
with cte_last_execution as (
    SELECT
        scanner_id,
        MAX(start_timestamp) AS max_start_timestamp
    FROM
        SNOWFLAKE.TRUST_CENTER.FINDINGS
    GROUP BY
        scanner_id
)
select
    tcf.completion_status,
    tcf.event_id,
    tcf.scanner_id,
    tcf.scanner_name,
    tcf.scanner_package_id,
    tcf.scanner_package_name,
    tcf.scanner_short_description,
    tcf.scanner_type,
    tcf.severity,
    tcf.at_risk_entities,
    tcf.total_at_risk_count,
    tcf.start_timestamp,
    tcf.end_timestamp,
    tcf.created_on
from SNOWFLAKE.TRUST_CENTER.FINDINGS tcf
join cte_last_execution le
    on le.scanner_id = tcf.scanner_id
    and le.max_start_timestamp = tcf.start_timestamp
;

grant select on table DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_TRUST_CENTER_FINDINGS
limit 10;
*/
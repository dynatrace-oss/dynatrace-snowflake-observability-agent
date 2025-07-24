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
use role DTAGENT_ADMIN;  use database DTAGENT_DB; use warehouse DTAGENT_WH;

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
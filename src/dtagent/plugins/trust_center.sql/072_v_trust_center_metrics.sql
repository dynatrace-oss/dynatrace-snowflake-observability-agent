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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;

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
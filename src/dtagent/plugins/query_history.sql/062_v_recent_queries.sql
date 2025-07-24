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
-- APP.V_RECENT_QUERIES() combines two transient tables: APP.TMP_RECENT_QUERIES and APP.TMP_QUERY_OPERATOR_STATS 
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_RECENT_QUERIES
as
select 
    rc.query_id                                 as QUERY_ID, 
    qos.query_operator_stats                    as QUERY_OPERATOR_STATS, 
    rc.parent_query_id                          as PARENT_QUERY_ID, 
    rc.session_id                               as SESSION_ID, 
    rc.name                                     as NAME, 
    rc.start_time                               as START_TIME, 
    rc.end_time                                 as END_TIME, 
    rc._SPAN_ID                                 as _SPAN_ID,
    rc._TRACE_ID                                as _TRACE_ID,
    rc.status_code                              as STATUS_CODE, 
    rc.dimensions                               as DIMENSIONS, 
    case when qae.attributes is not null then
        MAP_CAT(qae.attributes::map(varchar,variant)::map(varchar,variant), 
                rc.attributes::map(varchar,variant))::object
        else rc.attributes
    end                                         as ATTRIBUTES,
    rc.METRICS                                  as METRICS, 
    rc.is_parent                                as IS_PARENT,
    rc.is_root                                  as IS_ROOT
from      DTAGENT_DB.APP.TMP_RECENT_QUERIES rc
left join DTAGENT_DB.APP.TMP_QUERY_OPERATOR_STATS qos
    using (QUERY_ID)
left join DTAGENT_DB.APP.TMP_QUERY_ACCELERATION_ESTIMATES qae
    using (QUERY_ID);
    
grant select on view DTAGENT_DB.APP.V_RECENT_QUERIES to role DTAGENT_VIEWER;

-- example call

-- use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
-- select * from APP.V_RECENT_QUERIES limit 10;
-- select * from APP.TMP_RECENT_QUERIES rc;

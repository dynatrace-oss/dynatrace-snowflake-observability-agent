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

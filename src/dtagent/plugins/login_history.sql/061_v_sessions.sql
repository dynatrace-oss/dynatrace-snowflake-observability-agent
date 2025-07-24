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
-- APP.V_SESSIONS() return events (less than 1000) from SNOWFLAKE.ACCOUNT_USAGE.SESSIONS view since the last time we checked (but not further than 1 day)
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_SESSIONS
as
select 
    s.created_on                        as TIMESTAMP,
    concat('New Sessions entry for ',
            s.user_name)                as _MESSAGE,
    OBJECT_CONSTRUCT(
        'db.user',                                      s.USER_NAME
    )                                   as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.session.start',                      s.CREATED_ON,
        'session.id',                                   s.SESSION_ID,
        'authentication.type',                          s.AUTHENTICATION_METHOD,
        'event.id',                                     s.LOGIN_EVENT_ID,
        'client.application.id',                        s.CLIENT_APPLICATION_ID,
        'client.application.version',                   s.CLIENT_APPLICATION_VERSION,
        'client.environment',                           s.CLIENT_ENVIRONMENT,
        'client.build_id',                              s.CLIENT_BUILD_ID,
        'client.version',                               s.CLIENT_VERSION,
        'snowflake.session.closed_reason',              s.CLOSED_REASON
    )                                   as ATTRIBUTES
from 
    SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
where
    s.created_on > GREATEST( timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('sessions') )
order by
    s.created_on asc
limit 1000
;


grant select on view DTAGENT_DB.APP.V_SESSIONS to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_SESSIONS;
 */

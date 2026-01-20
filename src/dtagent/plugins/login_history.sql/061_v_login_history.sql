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
-- APP.V_LOGIN_HISTORY() return events (less than 1000) from SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY view since the last time we checked (but not further than 1 day)
--
use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;
create or replace view DTAGENT_DB.APP.V_LOGIN_HISTORY
as
select
    lh.event_timestamp                 as TIMESTAMP,
    concat(lh.event_type,
           ': ',
           lh.user_name)               as _MESSAGE, -- _underscored attributes are not reported; _message is used as content/title for log
    OBJECT_CONSTRUCT(
        'event.name',                                   lh.EVENT_TYPE,
        'db.user',                                      lh.USER_NAME,
        'client.ip',                                    lh.CLIENT_IP,
        'client.type',                                  lh.REPORTED_CLIENT_TYPE
    )                                  as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'event.id',                                     lh.EVENT_ID,
        'client.version',                               lh.REPORTED_CLIENT_VERSION,
        'authentication.factor.first',                 lh.FIRST_AUTHENTICATION_FACTOR,
        'authentication.factor.second',                lh.SECOND_AUTHENTICATION_FACTOR,
        'status.code',                                  IFF(lh.IS_SUCCESS = 'YES', 'OK', 'ERROR'),
        'error.code',                                   lh.ERROR_CODE,
        'status.message',                               lh.ERROR_MESSAGE,
        'event.related_id',                             lh.RELATED_EVENT_ID,
        'db.snowflake.connection',                      lh.CONNECTION
    )                                  as ATTRIBUTES
from
    SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY lh
where
    lh.event_timestamp > GREATEST( timeadd(hour, -24, current_timestamp), DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('login_history') )
order by
    lh.event_timestamp asc
limit 1000
;


grant select on view DTAGENT_DB.APP.V_LOGIN_HISTORY to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_LOGIN_HISTORY;
 */

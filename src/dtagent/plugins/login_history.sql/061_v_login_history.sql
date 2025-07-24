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
    lh.event_timestamp > GREATEST( timeadd(hour, -24, current_timestamp), DTAGENT_DB.APP.F_LAST_PROCESSED_TS('login_history') )
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

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

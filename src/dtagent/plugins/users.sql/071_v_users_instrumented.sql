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

create or replace view DTAGENT_DB.APP.V_USERS_INSTRUMENTED
as 
with cte_hash as (
    select DTAGENT_DB.APP.F_GET_CONFIG_VALUE('plugins.users.is_hashed', TRUE)::boolean as hash
)
select
    u.login_name                                                                            as LOGIN,
    concat('User details for ', u.login_name)                                               as _MESSAGE,
    extract(epoch_nanosecond from current_timestamp())                                      as TIMESTAMP,
    OBJECT_CONSTRUCT(
        'db.user',                                                          u.login_name
    )                                                                                       as DIMENSIONS,
    OBJECT_CONSTRUCT(
        'snowflake.user.id',                                                u.user_id,
        'snowflake.user.display_name',                                      u.display_name,
        'snowflake.user.name',                                              u.name,
        'snowflake.user.name.first',                                        u.first_name,
        'snowflake.user.name.last',                                         u.last_name,
        'snowflake.user.email',                                             IFF(h.hash = FALSE, u.email, u.email_hash),
        'snowflake.user.must_change_password',                              u.must_change_password,
        'snowflake.user.has_password',                                      u.has_password,
        'snowflake.user.comment',                                           u.comment,
        'snowflake.user.is_disabled',                                       u.disabled,
        'snowflake.user.is_locked',                                         u.snowflake_lock,
        'snowflake.user.default.warehouse',                                 u.default_warehouse,
        'snowflake.user.default.namespace',                                 u.default_namespace,
        'snowflake.user.default.role',                                      u.default_role,
        'snowflake.user.ext_authn.duo',                                     u.ext_authn_duo,
        'snowflake.user.ext_authn.uid',                                     u.ext_authn_uid,
        'snowflake.user.owner',                                             u.owner,
        'snowflake.user.default.secondary_role',                            u.default_secondary_role,
        'snowflake.user.type',                                              u.type,
        -- attributes that are neither metrics nor event timestamps
        'snowflake.user.expires_at',                                        extract(epoch_nanosecond from u.expires_at),
        'snowflake.user.locked_until_time',                                 extract(epoch_nanosecond from u.locked_until_time),
        'snowflake.user.bypass_mfa_until',                                  extract(epoch_nanosecond from u.bypass_mfa_until),
        -- not reported as EVENT_TIMESTAMPS as we do not want to send events, and it would mess up documentation test
        'snowflake.user.created_on',                                        extract(epoch_nanosecond from u.created_on),
        'snowflake.user.last_success_login',                                (select extract(epoch_nanosecond from max(lh.event_timestamp)) from SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY lh 
                                                                                    where lh.user_name = u.login_name and lh.event_type = 'LOGIN' and lh.is_success = 'YES'),
        'snowflake.user.deleted_on',                                        extract(epoch_nanosecond from u.deleted_on),
        'snowflake.user.password_last_set_time',                            extract(epoch_nanosecond from u.password_last_set_time)
    )                                                                                       as ATTRIBUTES
from DTAGENT_DB.APP.TMP_USERS u, cte_hash h;

grant select on table DTAGENT_DB.APP.V_USERS_INSTRUMENTED to role DTAGENT_VIEWER;

-- example call
/*
use database DTAGENT_DB; use warehouse DTAGENT_WH; use role DTAGENT_VIEWER;
select * from DTAGENT_DB.APP.V_USERS_INSTRUMENTED
limit 10;
*/
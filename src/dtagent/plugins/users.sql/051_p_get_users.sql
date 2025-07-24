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

-- upgrading TMP_USERS and TMP_USERS_HELPER from earlier versions
-- FIXME in DP-11368
EXECUTE IMMEDIATE $$
BEGIN
if ( not exists (
    select 1
    from INFORMATION_SCHEMA.COLUMNS
    where TABLE_CATALOG = 'DTAGENT_DB'
    and TABLE_SCHEMA = 'APP'
    and TABLE_NAME = 'TMP_USERS'
    and COLUMN_NAME = 'EMAIL_HASH'
))
then
    -- Add the column
    drop table if exists DTAGENT_DB.APP.TMP_USERS;
    return 'Old version of TMP_USERS dropped';
else
    return 'Already on new version of TMP_USERS';
end if;
EXCEPTION
when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    return SQLERRM;
END;
$$
;
EXECUTE IMMEDIATE $$
BEGIN
if ( not exists (
    select 1
    from INFORMATION_SCHEMA.COLUMNS
    where TABLE_CATALOG = 'DTAGENT_DB'
    and TABLE_SCHEMA = 'APP'
    and TABLE_NAME = 'TMP_USERS_HELPER'
    and COLUMN_NAME = 'EMAIL_HASH'
))
then
    -- Add the column
    drop table if exists DTAGENT_DB.APP.TMP_USERS_HELPER;
    return 'Old version of TMP_USERS_HELPER dropped';
else
    return 'Already on new version of TMP_USERS_HELPER';
end if;
EXCEPTION
when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    return SQLERRM;
END;
$$
;


create transient table if not exists DTAGENT_DB.APP.TMP_USERS (
        email_hash text, email text, user_id number, name text, 
        created_on timestamp_ltz, deleted_on timestamp_ltz,
        login_name text, display_name text, first_name text, last_name text, 
        must_change_password boolean, has_password boolean,
        comment text, disabled variant, snowflake_lock variant, 
        default_warehouse text, default_namespace text, default_role text,
        ext_authn_duo boolean, ext_authn_uid text, has_mfa boolean, bypass_mfa_until timestamp_ltz, 
        last_success_login timestamp_ltz, expires_at timestamp_ltz, locked_until_time timestamp_ltz, 
        has_rsa_public_key boolean, password_last_set_time timestamp_ltz,
        owner text, default_secondary_role text, type text, 
        database_name text, database_id number, schema_name text, schema_id number) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_USERS to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.APP.TMP_USERS_HELPER (
        email_hash text, email text, user_id number, name text, 
        created_on timestamp_ltz, deleted_on timestamp_ltz,
        login_name text, display_name text, first_name text, last_name text, 
        must_change_password boolean, has_password boolean,
        comment text, disabled variant, snowflake_lock variant, 
        default_warehouse text, default_namespace text, default_role text,
        ext_authn_duo boolean, ext_authn_uid text, has_mfa boolean, bypass_mfa_until timestamp_ltz, 
        last_success_login timestamp_ltz, expires_at timestamp_ltz, locked_until_time timestamp_ltz, 
        has_rsa_public_key boolean, password_last_set_time timestamp_ltz,
        owner text, default_secondary_role text, type text, 
        database_name text, database_id number, schema_name text, schema_id number) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_USERS_HELPER to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.STATUS.EMAIL_HASH_MAP (email text, email_hash text) DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.STATUS.EMAIL_HASH_MAP to role DTAGENT_VIEWER;

create or replace procedure DTAGENT_DB.APP.P_GET_USERS()
returns text
language sql
execute as owner
as
$$
DECLARE
    tr_us_table                  TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_USERS;';
    tr_us_h_table                TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_USERS_HELPER;';
    create_snap                  TEXT DEFAULT 'create temporary table DTAGENT_DB.APP.TMP_USERS_SNAPSHOT 
                                                            as select sha2(email) as email_hash, email, * exclude(email) 
                                                                 from SNOWFLAKE.ACCOUNT_USAGE.USERS 
                                                                where DELETED_ON is null 
                                                                   or DELETED_ON > DTAGENT_DB.APP.F_LAST_PROCESSED_TS(\'users\');';
    del_snap                     TEXT DEFAULT 'drop table DTAGENT_DB.APP.TMP_USERS_SNAPSHOT';
    tr_map                       TEXT DEFAULT 'truncate table if exists DTAGENT_DB.STATUS.EMAIL_HASH_MAP;';
BEGIN
    -- truncate TMP_USERS to not report old entries
    EXECUTE IMMEDIATE :tr_us_table;

    -- create current snapshot of snowflake.account_usage.users
    EXECUTE IMMEDIATE :create_snap;

    -- update email to hash map with new entries to dtagent_db.app.tmp_users_snapshot
    if ((DTAGENT_DB.APP.F_GET_CONFIG_VALUE('plugins.users.retain_email_hash_map', FALSE)::boolean) = TRUE) then
        merge into DTAGENT_DB.STATUS.EMAIL_HASH_MAP as trg using (select email, email_hash from DTAGENT_DB.APP.TMP_USERS_SNAPSHOT) as src
            on trg.email = src.email 
            when not matched and src.email is not null then
                insert (email, email_hash)
                values (src.email, src.email_hash);
    else
        EXECUTE IMMEDIATE :tr_map;
    end if;
    
    -- if first run of the day, truncate helper to report everything from snapshot
    if (DATE(DTAGENT_DB.APP.F_LAST_PROCESSED_TS('users')) = DATEADD(day, -1, (CURRENT_DATE()))) then 
        EXECUTE IMMEDIATE :tr_us_h_table;
    end if;
    
    -- insert to DTAGENT_DB.APP.TMP_USERS all new entries from snapshot
    insert into DTAGENT_DB.APP.TMP_USERS
        select * from DTAGENT_DB.APP.TMP_USERS_SNAPSHOT
        except
        select * from DTAGENT_DB.APP.TMP_USERS_HELPER;

    -- update helper to keep newly reported entries from snapshot
    insert into DTAGENT_DB.APP.TMP_USERS_HELPER
        select * from DTAGENT_DB.APP.TMP_USERS_SNAPSHOT;

    EXECUTE IMMEDIATE :del_snap;

RETURN 'tables APP.TMP_USERS, APP.TMP_USERS_HELPER updated';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GET_USERS() to role DTAGENT_VIEWER;

use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_USERS to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_USERS_HELPER to role DTAGENT_ADMIN copy current grants;

-- use role DTAGENT_ADMIN;
-- call DTAGENT_DB.APP.P_GET_USERS();

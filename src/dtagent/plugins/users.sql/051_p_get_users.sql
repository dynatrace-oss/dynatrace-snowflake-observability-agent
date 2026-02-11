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

use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;

create or replace transient table DTAGENT_DB.APP.TMP_USERS (
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
        database_name text, database_id number, schema_name text, schema_id number,
        is_from_organization_user boolean)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_USERS to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.APP.TMP_USERS_HELPER (
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
        database_name text, database_id number, schema_name text, schema_id number,
        is_from_organization_user boolean)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.APP.TMP_USERS_HELPER to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.STATUS.EMAIL_HASH_MAP (email text, email_hash text) DATA_RETENTION_TIME_IN_DAYS = 0;
grant select on table DTAGENT_DB.STATUS.EMAIL_HASH_MAP to role DTAGENT_VIEWER;

create or replace procedure DTAGENT_DB.APP.P_GET_USERS()
returns text
language sql
execute as owner
as
$$
DECLARE
    tr_us_table       TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_USERS;';
    tr_us_h_table     TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_USERS_HELPER;';
    create_snap       TEXT DEFAULT 'create or replace temporary table DTAGENT_DB.APP.TMP_USERS_SNAPSHOT
                                                            as select sha2(email) as email_hash, email, user_id, name,
                                                                      created_on, deleted_on,
                                                                      login_name, display_name, first_name, last_name,
                                                                      must_change_password, has_password,
                                                                      comment, disabled, snowflake_lock,
                                                                      default_warehouse, default_namespace, default_role,
                                                                      ext_authn_duo, ext_authn_uid, has_mfa, bypass_mfa_until,
                                                                      last_success_login, expires_at, locked_until_time,
                                                                      has_rsa_public_key, password_last_set_time,
                                                                      owner, default_secondary_role, type,
                                                                      database_name, database_id, schema_name, schema_id,
                                                                      is_from_organization_user
                                                                 from SNOWFLAKE.ACCOUNT_USAGE.USERS
                                                                where DELETED_ON is null
                                                                   or DELETED_ON > DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS(\'users\');';
    del_snap          TEXT DEFAULT 'drop table DTAGENT_DB.APP.TMP_USERS_SNAPSHOT';
    tr_map            TEXT DEFAULT 'truncate table if exists DTAGENT_DB.STATUS.EMAIL_HASH_MAP;';
BEGIN
    -- truncate TMP_USERS to not report old entries
    EXECUTE IMMEDIATE :tr_us_table;

    -- create current snapshot of snowflake.account_usage.users
    EXECUTE IMMEDIATE :create_snap;

    -- update email to hash map with new entries to dtagent_db.app.tmp_users_snapshot
    if ((DTAGENT_DB.CONFIG.F_GET_CONFIG_VALUE('plugins.users.retain_email_hash_map', FALSE)::boolean) = TRUE) then
        merge into DTAGENT_DB.STATUS.EMAIL_HASH_MAP as trg using (select email, email_hash from DTAGENT_DB.APP.TMP_USERS_SNAPSHOT) as src
            on trg.email = src.email
            when not matched and src.email is not null then
                insert (email, email_hash)
                values (src.email, src.email_hash);
    else
        EXECUTE IMMEDIATE :tr_map;
    end if;

    -- if first run of the day, truncate helper to report everything from snapshot
    if (DATE(DTAGENT_DB.STATUS.F_LAST_PROCESSED_TS('users')) = DATEADD(day, -1, (CURRENT_DATE()))) then
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

-- use role DTAGENT_OWNER;
-- call DTAGENT_DB.APP.P_GET_USERS();

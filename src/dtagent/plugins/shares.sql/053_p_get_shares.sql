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

-- FIXME in DP-11368
EXECUTE IMMEDIATE $$
BEGIN
    if ( not exists (
        select 1
        from INFORMATION_SCHEMA.COLUMNS
        where TABLE_CATALOG = 'DTAGENT_DB'
        and TABLE_SCHEMA = 'APP'
        and TABLE_NAME = 'TMP_INBOUND_SHARES'
        and COLUMN_NAME = 'DETAILS'
    ))
    then
        -- Add the column
        drop table if exists DTAGENT_DB.APP.TMP_INBOUND_SHARES;
        return 'Old version of TMP_INBOUND_SHARES dropped';
    else
        return 'Already on new version of TMP_INBOUND_SHARES';
    end if;
EXCEPTION
    when statement_error then
        SYSTEM$LOG_WARN(SQLERRM);
        return SQLERRM;
END;
$$
;

create transient table if not exists DTAGENT_DB.APP.TMP_SHARES (
        created_on timestamp_ltz, 
        kind text, owner_account text, name text, database_name text, 
        given_to text, owner text, 
        comment text, listing_global_name text, secure_objects_only text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select, truncate, insert on table DTAGENT_DB.APP.TMP_SHARES to role DTAGENT_VIEWER;


create transient table if not exists DTAGENT_DB.APP.TMP_OUTBOUND_SHARES (
        created_on timestamp_ltz, 
        privilege text, granted_on text, name text, 
        granted_to text, grantee_name text, grant_option text, granted_by text, 
        share_name text) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select, truncate, insert on table DTAGENT_DB.APP.TMP_OUTBOUND_SHARES to role DTAGENT_VIEWER;

create transient table if not exists DTAGENT_DB.APP.TMP_INBOUND_SHARES (
        SHARE_NAME text, IS_REPORTED boolean, DETAILS object) 
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select, truncate, insert on table DTAGENT_DB.APP.TMP_INBOUND_SHARES to role DTAGENT_VIEWER;

create or replace procedure DTAGENT_DB.APP.P_GET_SHARES()
returns text
language sql
execute as caller
as
$$
DECLARE
    q_get_shares                TEXT DEFAULT 'SHOW SHARES;';
    q_pop_shares                TEXT DEFAULT 'insert into DTAGENT_DB.APP.TMP_SHARES select * from table(result_scan(last_query_id()));';

    tr_sh_table                 TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_SHARES;';
    tr_out_table                TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_OUTBOUND_SHARES;';
    tr_in_table                 TEXT DEFAULT 'truncate table if exists DTAGENT_DB.APP.TMP_INBOUND_SHARES;';

    c_shares                    CURSOR      for select database_name, kind, name from DTAGENT_DB.APP.TMP_SHARES;

    db_name                     TEXT DEFAULT '';
    share_kind                  TEXT DEFAULT '';
    share_name                  TEXT DEFAULT '';
BEGIN
    EXECUTE IMMEDIATE :tr_sh_table;
    EXECUTE IMMEDIATE :tr_out_table;
    EXECUTE IMMEDIATE :tr_in_table;

    EXECUTE IMMEDIATE :q_get_shares;
    EXECUTE IMMEDIATE :q_pop_shares;


    for share in c_shares do
        db_name := share.database_name;
        share_kind := share.kind;
        share_name := share.name; 
        if (:share_kind = 'OUTBOUND') then 
            EXECUTE IMMEDIATE concat('show grants to share ', :share_name);

            insert into DTAGENT_DB.APP.TMP_OUTBOUND_SHARES
                select t.*, :share_name from table(result_scan(last_query_id())) t;

        elseif (:share_kind = 'INBOUND' and NVL(:db_name, 'SNOWFLAKE') <> 'SNOWFLAKE' and len(:db_name) > 0) then

            if ((not (:db_name || '.%.%') LIKE ANY (select ci.VALUE from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ci where c.PATH = 'plugins.data_volume.include') 
                and ((:db_name || '.%.%') LIKE ANY (select ce.VALUE from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce where c.PATH = 'plugins.data_volume.exclude')))
                and (:share_name LIKE ANY (select ce.VALUE from CONFIG.CONFIGURATIONS c, table(flatten(c.VALUE)) ce where c.PATH = 'plugins.shares.exclude_from_monitoring'))) then

                insert into DTAGENT_DB.APP.TMP_INBOUND_SHARES(SHARE_NAME, IS_REPORTED)
                    select :share_name, FALSE;
            
            else
                insert into DTAGENT_DB.APP.TMP_INBOUND_SHARES(SHARE_NAME, IS_REPORTED)
                    select :share_name, TRUE;

                if ((SELECT count(*) > 0 from SNOWFLAKE.ACCOUNT_USAGE.DATABASES where DATABASE_NAME = :db_name and DELETED is null)) then
                    call DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(:share_name, :db_name);

                    insert into DTAGENT_DB.APP.TMP_INBOUND_SHARES 
                        select SHARE_NAME, IS_REPORTED, DETAILS 
                        from TABLE(result_scan(last_query_id()));
                else
                    insert into DTAGENT_DB.APP.TMP_INBOUND_SHARES(SHARE_NAME, DETAILS)
                        select :share_name, OBJECT_CONSTRUCT('HAS_DB_DELETED', TRUE); -- FIXME this needs to be reported in TMP_SHARES
                end if;
            end if;  

        end if;
    end for;


RETURN 'tables APP.TMP_SHARES, APP.TMP_OUTBOUND_SHARES, APP.TMP_INBOUND_SHARES updated';

EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM);
    
    return SQLERRM;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_GET_SHARES() to role DTAGENT_VIEWER;

use role ACCOUNTADMIN;
grant ownership on table DTAGENT_DB.APP.TMP_SHARES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_OUTBOUND_SHARES to role DTAGENT_ADMIN copy current grants;
grant ownership on table DTAGENT_DB.APP.TMP_INBOUND_SHARES to role DTAGENT_ADMIN copy current grants;

-- use role DTAGENT_ADMIN;
-- call DTAGENT_DB.APP.P_GET_SHARES();

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

use role DTAGENT_ADMIN; use database DTAGENT_DB; use warehouse DTAGENT_WH;


create or replace transient table DTAGENT_DB.APP.TMP_SHARES (
        created_on timestamp_ltz,
        kind text, owner_account text, name text, database_name text,
        given_to text, owner text,
        comment text, listing_global_name text, secure_objects_only text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select, truncate, insert on table DTAGENT_DB.APP.TMP_SHARES to role DTAGENT_VIEWER;


create or replace transient table DTAGENT_DB.APP.TMP_OUTBOUND_SHARES (
        created_on timestamp_ltz,
        privilege text, granted_on text, name text,
        granted_to text, grantee_name text, grant_option text, granted_by text,
        share_name text)
    DATA_RETENTION_TIME_IN_DAYS = 0;
grant select, truncate, insert on table DTAGENT_DB.APP.TMP_OUTBOUND_SHARES to role DTAGENT_VIEWER;

create or replace transient table DTAGENT_DB.APP.TMP_INBOUND_SHARES (
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
    q_get_shares                TEXT DEFAULT 'SHOW SHARES ->> insert into DTAGENT_DB.APP.TMP_SHARES select * from $1;';

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

    for share in c_shares do
        db_name := share.database_name;
        share_kind := share.kind;
        share_name := share.name;
        if (:share_kind = 'OUTBOUND') then
            EXECUTE IMMEDIATE concat('SHOW GRANTS TO SHARE ', :share_name);

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

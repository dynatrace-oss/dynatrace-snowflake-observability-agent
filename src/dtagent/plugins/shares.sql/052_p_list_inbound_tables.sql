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
use role DTAGENT_OWNER; use database DTAGENT_DB; use schema APP; use warehouse DTAGENT_WH; -- fixed DP-11334

create or replace procedure DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(share_name VARCHAR, db_name VARCHAR)
returns table (
    SHARE_NAME text,
    IS_REPORTED boolean,
    DETAILS object
)
language sql
execute as caller
as
$$
DECLARE
    query               TEXT;
    rs                  RESULTSET;
    rs_empty            RESULTSET DEFAULT (SELECT NULL:text as SHARE_NAME,
                                              FALSE:boolean as IS_REPORTED,
                                         OBJECT_CONSTRUCT() as DETAILS
                                           WHERE 1=0);
    rs_unavailable      RESULTSET DEFAULT (SELECT :share_name as SHARE_NAME,
                                                 TRUE:boolean as IS_REPORTED,
                                             OBJECT_CONSTRUCT('SHARE_STATUS', 'UNAVAILABLE',
                                                              'SHARE_NAME', :share_name,
                                                              'DATABASE_NAME', :db_name,
                                                              'ERROR_MESSAGE', 'Shared database is no longer available') as DETAILS);
    error_msg           TEXT;
    share_name_safe     TEXT DEFAULT '';
    v_db                TEXT DEFAULT '';
BEGIN
    v_db            := UPPER(:db_name);
    share_name_safe := REPLACE(:share_name, '''', '');

    query := concat('select ''', :share_name_safe, ''' as SHARE_NAME, TRUE as IS_REPORTED, OBJECT_CONSTRUCT(t.*)',
                    ' from IDENTIFIER(''', :v_db, '.INFORMATION_SCHEMA.TABLES'') t',
                    ' where TABLE_SCHEMA != ''INFORMATION_SCHEMA''');

    rs := (EXECUTE IMMEDIATE :query);
    RETURN TABLE(rs);
EXCEPTION
  when statement_error then
    error_msg := SQLERRM;

    -- First attempt failed — grant imported privileges inline and retry once
    call DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(:db_name);

    BEGIN
        rs := (EXECUTE IMMEDIATE :query);
        RETURN TABLE(rs);
    EXCEPTION
      when statement_error then
        error_msg := SQLERRM;
        IF (CONTAINS(:error_msg, 'Shared database is no longer available') OR
            CONTAINS(:error_msg, 'does not exist or not authorized')) THEN
            -- Expected condition: share is unavailable or access was revoked
            RETURN TABLE(rs_unavailable);
        ELSE
            -- Unexpected error after grant attempt
            SYSTEM$LOG_WARN(:error_msg || ' | Query: ' || :query);
            RETURN TABLE(rs_empty);
        END IF;
    END;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(VARCHAR, VARCHAR) to role DTAGENT_VIEWER;


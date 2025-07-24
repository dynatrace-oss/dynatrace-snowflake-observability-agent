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
use role DTAGENT_ADMIN; use database DTAGENT_DB; use schema APP; use warehouse DTAGENT_WH; -- fixed DP-11334

create or replace procedure DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(share_name VARCHAR, db_name VARCHAR, with_grant BOOLEAN default FALSE)
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
    query     TEXT;
    rs        RESULTSET;
    rs_repeat RESULTSET;
    rs_empty  RESULTSET DEFAULT (SELECT NULL:text as SHARE_NAME, FALSE:boolean as IS_REPORTED, OBJECT_CONSTRUCT() as DETAILS WHERE 1=0);
BEGIN
    IF (:with_grant) THEN
        call DTAGENT_DB.APP.P_GRANT_IMPORTED_PRIVILEGES(:db_name);
    END IF;

    query := concat('select ''', :share_name, ''' as SHARE_NAME, TRUE as IS_REPORTED, OBJECT_CONSTRUCT(t.*) from ', :db_name, '.INFORMATION_SCHEMA.TABLES t where TABLE_SCHEMA != ''INFORMATION_SCHEMA''');

    rs := (EXECUTE IMMEDIATE :query);
    RETURN TABLE(rs);  
EXCEPTION
  when statement_error then
    SYSTEM$LOG_WARN(SQLERRM || :query);

    IF (:with_grant) then
        return TABLE(rs_empty);
    ELSE
        -- If the query fails and we are not granting privileges, we try to repeat the query asking for privileges to be granted first
        rs_repeat := (EXECUTE IMMEDIATE concat('call DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(''', :share_name, ''', ''', :db_name, ''', TRUE)'));
        RETURN TABLE(rs_repeat);  
    END IF;
END;
$$
;

grant usage on procedure DTAGENT_DB.APP.P_LIST_INBOUND_TABLES(VARCHAR, VARCHAR, BOOLEAN) to role DTAGENT_VIEWER;


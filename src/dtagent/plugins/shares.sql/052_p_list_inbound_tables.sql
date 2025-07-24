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


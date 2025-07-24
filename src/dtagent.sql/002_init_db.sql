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
-- Initializing Dynatrace Snowflake Observability Agent by creating: DB
--
use role ACCOUNTADMIN;
create database if not exists DTAGENT_DB;

grant ownership on database DTAGENT_DB to role DTAGENT_ADMIN;
grant usage on database DTAGENT_DB to role DTAGENT_VIEWER;

grant OPERATE on all tasks in database DTAGENT_DB to role DTAGENT_VIEWER;
grant OPERATE on future tasks in database DTAGENT_DB to role DTAGENT_VIEWER;


create schema if not exists DTAGENT_DB.PUBLIC;
grant ownership on schema DTAGENT_DB.PUBLIC to role DTAGENT_ADMIN;
grant usage on schema DTAGENT_DB.PUBLIC to role DTAGENT_VIEWER;


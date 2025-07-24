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
-- Initializing Dynatrace Snowflake Observability Agent by creating: admin role
--
use role ACCOUNTADMIN;
create role if not exists DTAGENT_ADMIN;
grant role DTAGENT_ADMIN to role ACCOUNTADMIN;

-- this is required to grant monitoring privileges on warehouses and dynamic tables to the DTAGENT_VIEWER role
grant manage grants on ACCOUNT to role DTAGENT_ADMIN;

grant MODIFY LOG LEVEL on account to role DTAGENT_ADMIN;

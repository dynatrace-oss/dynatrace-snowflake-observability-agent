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
-- Initializing Dynatrace Snowflake Observability Agent by creating: view role
--
use role ACCOUNTADMIN;
create role if not exists DTAGENT_VIEWER;

-- viewer permissions are a subset of those for the admin
grant role DTAGENT_VIEWER to role DTAGENT_ADMIN;

grant MONITOR on ACCOUNT to role DTAGENT_VIEWER;
grant MONITOR USAGE on ACCOUNT to role DTAGENT_VIEWER;
grant MONITOR EXECUTION on ACCOUNT to role DTAGENT_VIEWER;

grant MODIFY SESSION LOG LEVEL on account to role DTAGENT_VIEWER;
grant IMPORTED PRIVILEGES on database SNOWFLAKE to role DTAGENT_VIEWER;

grant EXECUTE TASK on account to role DTAGENT_VIEWER;

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
-- Initializing Dynatrace Snowflake Observability Agent by creating: warehouse
--
use role ACCOUNTADMIN;

-- ensure a warehouse is usable by provider
create warehouse if not exists DTAGENT_WH with 
    warehouse_type=STANDARD 
    warehouse_size=XSMALL 
    scaling_policy=ECONOMY 
    initially_suspended=TRUE 
    auto_resume=TRUE 
    auto_suspend=60;
grant ownership on warehouse DTAGENT_WH to role DTAGENT_ADMIN revoke current grants;
grant modify on warehouse DTAGENT_WH to role DTAGENT_ADMIN;
grant usage, operate on warehouse DTAGENT_WH to role DTAGENT_VIEWER;


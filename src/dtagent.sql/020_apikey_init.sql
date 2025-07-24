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
-- Initializing Dynatrace Token API KEY if not exists
--
use role ACCOUNTADMIN;  use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH;

create secret if not exists DTAGENT_API_KEY 
              type = GENERIC_STRING 
              secret_string = '-';
grant ownership on secret DTAGENT_API_KEY to role DTAGENT_ADMIN revoke current grants;
grant usage on secret DTAGENT_API_KEY to role DTAGENT_VIEWER;

create network rule if not exists DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE
               mode = EGRESS
               type = HOST_PORT
               value_list = ('dynatrace.com');
grant ownership on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_ADMIN revoke current grants;
grant usage on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_VIEWER;

create external access integration if not exists DTAGENT_API_INTEGRATION 
    allowed_network_rules = (DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE)
    allowed_authentication_secrets = (DTAGENT_DB.CONFIG.DTAGENT_API_KEY)
    enabled = TRUE;
grant ownership on integration DTAGENT_API_INTEGRATION to role DTAGENT_ADMIN revoke current grants;
grant usage on integration DTAGENT_API_INTEGRATION to role DTAGENT_VIEWER;

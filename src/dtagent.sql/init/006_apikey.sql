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
--
-- Initializing Dynatrace Token API KEY if not exists
--
use role ACCOUNTADMIN;  use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH;

create secret if not exists DTAGENT_API_KEY
              type = GENERIC_STRING
              secret_string = '-';
grant ownership on secret DTAGENT_API_KEY to role DTAGENT_OWNER revoke current grants;
grant usage on secret DTAGENT_API_KEY to role DTAGENT_VIEWER;

create network rule if not exists DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE
               mode = EGRESS
               type = HOST_PORT
               value_list = ('dynatrace.com');
grant ownership on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_OWNER revoke current grants;
grant usage on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_VIEWER;

create external access integration if not exists DTAGENT_API_INTEGRATION
    allowed_network_rules = (DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE)
    allowed_authentication_secrets = (DTAGENT_DB.CONFIG.DTAGENT_API_KEY)
    enabled = TRUE;
grant ownership on integration DTAGENT_API_INTEGRATION to role DTAGENT_OWNER revoke current grants;
grant usage on integration DTAGENT_API_INTEGRATION to role DTAGENT_VIEWER;

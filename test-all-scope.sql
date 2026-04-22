
SELECT 'init';

SELECT 'admin'; CREATE ROLE IF NOT EXISTS DTAGENT_TEST_ADMIN;

SELECT 'setup'; CREATE SCHEMA IF NOT EXISTS MAIN_SCHEMA;

SELECT 'plugin';

SELECT 'config';

SELECT 'agents';
use role DTAGENT_TEST_OWNER; use schema DTAGENT_TEST_DB.CONFIG; use warehouse DTAGENT_TEST_WH;

alter secret DTAGENT_TEST_API_KEY set secret_string = 'dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890';
alter network rule DTAGENT_NETWORK_RULE set value_list = ('abc12345.live.dynatrace.com', 'dynatrace.com');

alter external access integration DTAGENT_TEST_API_INTEGRATION set
    allowed_network_rules = (DTAGENT_TEST_DB.CONFIG.DTAGENT_NETWORK_RULE)
    allowed_authentication_secrets = (DTAGENT_TEST_DB.CONFIG.DTAGENT_TEST_API_KEY)
    enabled = TRUE;

use role DTAGENT_TEST_OWNER; use database DTAGENT_TEST_DB; use schema CONFIG; use warehouse DTAGENT_TEST_WH;
call DTAGENT_TEST_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();

#!/usr/bin/env bash
#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
#
#
# Updates DT API Token as secret with the provided value in the given Snowflake account (env_name)
#
# Args:
# * INSTALL_SCRIPT_SQL  [REQUIRED] - the path to the temporary SQL script to be executed against Snowflake

INSTALL_SCRIPT_SQL="$1"

DYNATRACE_TENANT_ADDRESS=$(./get_config_key.sh core.dynatrace_tenant_address)

if [ -z "$DTAGENT_TOKEN" ]; then
    echo "Environment variable DTAGENT_TOKEN is not defined."
    echo
    read -p "Enter an access token for $DYNATRACE_TENANT_ADDRESS: " TMP_DTAGENT_TOKEN </dev/tty
    echo
    if [ -n "$TMP_DTAGENT_TOKEN" ]; then
        DTAGENT_TOKEN="$TMP_DTAGENT_TOKEN"
    fi
fi

if [[ -z "$DTAGENT_TOKEN" || ! $DTAGENT_TOKEN =~ ^dt[0-9]{1}c[0-9]{2}\.[A-Za-z0-9]{24}\.[A-Za-z0-9]{64}$ ]]; then
    echo "[WARNING] DTAGENT_API_KEY will NOT be updated: DTAGENT_TOKEN is not set or is not a valid Dynatrace token."
    exit 1
fi

cat <<EOF >>$INSTALL_SCRIPT_SQL
use role DTAGENT_ADMIN; use schema DTAGENT_DB.CONFIG; use warehouse DTAGENT_WH;

create or replace secret DTAGENT_API_KEY type = GENERIC_STRING secret_string = '$DTAGENT_TOKEN';
grant ownership on secret DTAGENT_API_KEY to role DTAGENT_ADMIN revoke current grants;
grant usage on secret DTAGENT_API_KEY to role DTAGENT_VIEWER;

create or replace network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE
                  mode = EGRESS
                  type = HOST_PORT
                  value_list = ('$DYNATRACE_TENANT_ADDRESS', 'dynatrace.com');

grant ownership on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_ADMIN revoke current grants;
grant usage on network rule DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE to role DTAGENT_VIEWER;

use role ACCOUNTADMIN;

create or replace external access integration DTAGENT_API_INTEGRATION
    allowed_network_rules = (DTAGENT_DB.CONFIG.DTAGENT_NETWORK_RULE)
    allowed_authentication_secrets = (DTAGENT_DB.CONFIG.DTAGENT_API_KEY)
    enabled = TRUE;
    
grant ownership on integration DTAGENT_API_INTEGRATION to role DTAGENT_ADMIN revoke current grants;
grant usage on integration DTAGENT_API_INTEGRATION to role DTAGENT_VIEWER;

EOF

#!/usr/bin/env bash
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
# Updates DT API Token as secret with the provided value in the given Snowflake account (env_name)
#
# Args:
# * INSTALL_SCRIPT_SQL  [REQUIRED] - the path to the temporary SQL script to be executed against Snowflake

INSTALL_SCRIPT_SQL="$1"
CWD=$(dirname "$0")

DYNATRACE_TENANT_ADDRESS=$($CWD/get_config_key.sh core.dynatrace_tenant_address)

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

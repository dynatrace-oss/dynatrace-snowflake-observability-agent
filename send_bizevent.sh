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

PARAM="$1"
STATUS="$2"
DEPLOYMENT_ID="$3"

if [[ -z "$DTAGENT_TOKEN" || ! "$DTAGENT_TOKEN" =~ ^dt0c[0-9]{0,2}\.[a-zA-Z0-9]{24}\.[a-zA-Z0-9]{64}$ ]]; then
    echo "Environment variable DTAGENT_TOKEN is not set or is not a valid Dynatrace token; skipping sending bizevents."

elif [ "$(./get_config_key.sh plugins.self_monitoring.send_bizevents_on_deploy)" = "true" ]; then
    DT_ADDRESS="$(./get_config_key.sh core.dynatrace_tenant_address)"

    if [ "$PARAM" == "config" ]; then
        TITLE="New Dynatrace Snowflake Observability Agent config and instruments deployment."
    elif [ "$PARAM" == "teardown" ]; then
        TITLE="Dynatrace Snowflake Observability Agent teardown initiated."
    elif [ "$PARAM" == "apikey" ]; then
        TITLE="Dynatrace Snowflake Observability Agent API key redeployed."
    else
        TITLE="New complete Dynatrace Snowflake Observability Agent deployment."
        PARAM="full_deployment"
    fi

    if ! curl -f -X POST "https://${DT_ADDRESS}/api/v2/bizevents/ingest" \
        -H "Authorization: Api-Token ${DTAGENT_TOKEN}" \
        -H 'Content-Type: application/json' \
        -d "{
            \"event.type\": \"CUSTOM_DEPLOYMENT\",
            \"event.title\": \"${TITLE}\",
            \"db.system\": \"snowflake\",
            \"deployment.environment\": \"$(./get_config_key.sh core.deployment_environment)\",
            \"host.name\": \"$(./get_config_key.sh core.snowflake_host_name)\",
            \"telemetry.exporter.name\": \"dynatrace.snowagent\",
            \"telemetry.exporter.version\": \"$(grep 'VERSION =' build/700_dtagent.sql | awk -F'"' '{print $2}')\",
            \"dsoa.deployment.parameter\": \"${PARAM}\",
            \"dsoa.deployment.status\": \"${STATUS}\",
            \"dsoa.deployment.id\": \"${DEPLOYMENT_ID}\"
        }" >/dev/null 2>&1; then
        exit 1
    fi
fi

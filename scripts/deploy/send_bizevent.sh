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

PARAM="$1"
STATUS="$2"
DEPLOYMENT_ID="$3"
CWD=$(dirname "$0")

if [[ -z "$DTAGENT_TOKEN" || ! "$DTAGENT_TOKEN" =~ ^dt0c[0-9]{0,2}\.[a-zA-Z0-9]{24}\.[a-zA-Z0-9]{64}$ ]]; then
    echo "Environment variable DTAGENT_TOKEN is not set or is not a valid Dynatrace token; skipping sending bizevents."

elif [ "$($CWD/get_config_key.sh plugins.self_monitoring.send_bizevents_on_deploy)" = "true" ]; then
    DT_ADDRESS="$($CWD/get_config_key.sh core.dynatrace_tenant_address)"

    if [ "$PARAM" == "config" ]; then
        TITLE="New Dynatrace Snowflake Observability Agent config deployment."
    elif [ "$PARAM" == "teardown" ]; then
        TITLE="Dynatrace Snowflake Observability Agent teardown initiated."
    elif [ "$PARAM" == "apikey" ]; then
        TITLE="Dynatrace Snowflake Observability Agent API key redeployed."
    else
        TITLE="New complete Dynatrace Snowflake Observability Agent deployment."
        PARAM="full_deployment"
    fi

    VERSION="$(grep 'VERSION =' build/70_agents.sql | awk -F'"' '{print $2}')"
    BUILD="$(grep 'BUILD =' build/70_agents.sql | awk -F' ' '{print $3}')"

    if ! curl -f -X POST "https://${DT_ADDRESS}/api/v2/bizevents/ingest" \
        -H "Authorization: Api-Token ${DTAGENT_TOKEN}" \
        -H 'Content-Type: application/json' \
        -d @<(cat <<EOF
        {
            "event.type": "CUSTOM_DEPLOYMENT",
            "event.title": "${TITLE}",
            "db.system": "snowflake",
            "deployment.environment": "$($CWD/get_config_key.sh core.deployment_environment)",
            "host.name": "$($CWD/get_config_key.sh core.snowflake.host_name)",
            "app.version": "${VERSION}.${BUILD}",
            "app.short_version": "${VERSION}",
            "app.bundle": "self_monitoring",
            "app.id": "dynatrace.snowagent",
            "dsoa.run.context": "self_monitoring",
            "dsoa.run.plugin": "deployment",
            "dsoa.run.id": "${DEPLOYMENT_ID}",
            "telemetry.exporter.name": "dynatrace.snowagent",
            "telemetry.exporter.version": "${VERSION}",
            "dsoa.deployment.parameter": "${PARAM}",
            "dsoa.deployment.status": "${STATUS}",
            "dsoa.deployment.id": "${DEPLOYMENT_ID}"
        }
EOF
        ) >/dev/null 2>&1; then
        exit 1
    fi
fi

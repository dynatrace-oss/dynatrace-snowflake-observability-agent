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

# This script will install all necessary components to enable deployments of Dynatrace Snowflake Observability Agent

ENV=$1

echo "Checking for missing tools"

TO_INSTALL=""
for cmd in "jq"; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "$cmd is missing"
        TO_INSTALL="$cmd $TO_INSTALL"
    fi
done

if [ $(uname -s) = 'Darwin' ]; then
    if [ "$TO_INSTALL" != "" ]; then
        brew install $TO_INSTALL
    fi

    if ! command -v "snow" &>/dev/null; then
        echo "Snowflake CLI is missing"
        brew tap snowflakedb/snowflake-cli
        brew install snowflake-cli
    fi
else
    if [ "$TO_INSTALL" != "" ]; then
        sudo apt update
        sudo apt install software-properties-common -y
        sudo add-apt-repository ppa:deadsnakes/ppa
        sudo apt update

        sudo apt install $TO_INSTALL
    fi

    if ! command -v "snow" &>/dev/null; then
        echo "Snowflake CLI is missing"
        sudo apt install pipx
        pipx install snowflake-cli-labs
        pipx ensurepath
        source ~/.bashrc
    fi
fi

if ! command -v "snow" &>/dev/null; then
    echo "Snowflake CLI is STILL missing - fallback scenario"
    ./install_snow_cli.sh
fi

echo "Checking for Snowflake connection profiles"

if [ "$ENV" == '' ]; then
    if ! echo $(snow connection list) | grep -q "snow_agent_"; then
        echo "WARNING: No Dynatrace Snowflake Observability Agent connections are defined for the Snowflake CLI."
        echo "         Run ./setup.sh with an environment name to create one for your environment."
    fi
else
    EXISTING_CONNECTIONS=$(snow connection list)

    for DEPLOYMENT_ENV in $(jq -r '.[].CORE.DEPLOYMENT_ENVIRONMENT' conf/config-$ENV.json); do
        echo "Checking connection profile for $DEPLOYMENT_ENV..."
        CONNECTION_ENV="${DEPLOYMENT_ENV,,}" # convert to lower case
        if ! echo "$EXISTING_CONNECTIONS" | grep -E -q "snow_agent_$CONNECTION_ENV\s"; then
            echo "WARNING: No Dynatrace Snowflake Observability Agent connection is defined for the $DEPLOYMENT_ENV environment. Creating it now..."

            snow connection add --connection-name snow_agent_$CONNECTION_ENV
        fi
    done
fi

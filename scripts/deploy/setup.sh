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

# This script will install all necessary components to enable deployments of Dynatrace Snowflake Observability Agent

ENV=$1
CWD=$(dirname "$0")

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
    $CWD/install_snow_cli.sh
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

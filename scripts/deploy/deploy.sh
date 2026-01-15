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

#
# This is a script for deploying / updating the whole or part of Dynatrace Snowflake Observability Agent
# Call as ./deploy.sh "$ENV" --scope=$SCOPE [--from-version=$VERSION] [--options=$OPTIONS]
#
# Args:
# * ENV            [REQUIRED] - environment identifier (config-$ENV.yml must exist)
# * --scope        [OPTIONAL] - deployment scope (default: all):
#                               init, setup, plugins, config, agents, apikey, all, teardown, upgrade, or file_part
# * --from-version [OPTIONAL] - version number for upgrade scope (required if scope=upgrade)
# * --options      [OPTIONAL] - comma-separated: manual, service_user, skip_confirm, no_dep
#

ENV=$1
shift

# Parse arguments
SCOPE="all"
FROM_VERSION=""
OPTIONS_STR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --scope=*)
            SCOPE="${1#*=}"
            shift
            ;;
        --from-version=*)
            FROM_VERSION="${1#*=}"
            shift
            ;;
        --options=*)
            OPTIONS_STR="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# Parse options into array
IFS=',' read -ra OPTIONS <<< "$OPTIONS_STR"

# Check if option is present
has_option() {
    local opt=$1
    for item in "${OPTIONS[@]}"; do
        [[ "$item" == "$opt" ]] && return 0
    done
    return 1
}

CWD=$(dirname "$0")

if has_option "manual"; then
    "$CWD/setup.sh"
else
    "$CWD/setup.sh" $ENV
fi

echo "Deploying Dynatrace Snowflake Observability Agent with [$ENV] configuration, using SCOPE=[$SCOPE]"

if [ "$ENV" == '' ]; then
    echo "Needs environment name to proceed"
    exit 1
fi

if [ "$SCOPE" == '' ]; then
    echo "Needs --scope parameter to proceed"
    exit 1
fi

if [ "$SCOPE" == "upgrade" ] && [ "$FROM_VERSION" == '' ]; then
    echo "--from-version parameter is required when scope=upgrade"
    exit 1
fi

#%DEV:
# we only need to check DTAGENT_TOKEN if we are deploying through Jenkins
if has_option "service_user" && [ -z "$DTAGENT_TOKEN" ]; then
    echo "Environment variable DTAGENT_TOKEN is not defined"
    exit 1
fi
#%:DEV

DEFAULT_CONFIG_FILE="build/config-default.yml"
CONFIG_FILE="conf/config-$ENV.yml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "There is no configuration file [conf/config-$ENV.yml]"
    #%DEV:
    # we could just exit if config file doesn't exist and we either do not want to deploy at all or want to deploy through jenkins

    if ! has_option "no_dep" && ! has_option "service_user"; then
        #%:DEV
        exit 1
        #%DEV:
    fi
    #%:DEV
fi

export BUILD_CONFIG_FILE="build/config.json"

DEPLOYMENT_ID=$(uuidgen)

$CWD/prepare_config.sh "${DEFAULT_CONFIG_FILE}" "${CONFIG_FILE}"

DEPLOYMENT_ENV="$($CWD/get_config_key.sh core.deployment_environment)"
CONNECTION_ENV="${DEPLOYMENT_ENV,,}" # convert to lower case
NOW_TS=$(date '+%Y%m%d-%H%M%S')

if has_option "manual"; then
    INSTALL_SCRIPT_SQL="dsoa-deploy-script-${DEPLOYMENT_ENV}-${NOW_TS}.sql"
else
    INSTALL_SCRIPT_SQL=$(mktemp -p build)
    # clean up this way, because rm did not always work
    trap " rm -f ${INSTALL_SCRIPT_SQL} " EXIT
fi

# Get list of plugins to exclude
EXCLUDED_PLUGINS=$($CWD/list_plugin_to_exclude.sh)

# Filter function to remove disabled plugin code
filter_plugin_code() {
    local input_file=$1
    local output_file=$2

    if [ -z "$EXCLUDED_PLUGINS" ]; then
        cat "$input_file" > "$output_file"
        return
    fi

    local temp_file=$(mktemp)
    cp "$input_file" "$temp_file"

    for plugin_name in $EXCLUDED_PLUGINS; do
        awk -v plugin="$plugin_name" '
            BEGIN { active=1; }
            /^([#]|[-]{2})[%]PLUGIN:/ {
                # Match PLUGIN:plugin_name: with colon after plugin name
                pattern = "[%]PLUGIN:" plugin ":"
                if (index($0, pattern) > 0) active=0;
            }
            { if (active==1) print $0; }
            /^([#]|[-]{2})[%][:]PLUGIN:/ {
                # Match :PLUGIN:plugin_name (end marker, no trailing colon)
                pattern = "[%]:PLUGIN:" plugin
                if (index($0, pattern) > 0 && index($0, pattern ":") == 0) active=1;
            }
        ' "$temp_file" > "$output_file"
        cp "$output_file" "$temp_file"
    done

    rm "$temp_file"
}

# preparing one big deployment script
$CWD/prepare_deploy_script.sh "${INSTALL_SCRIPT_SQL}" "${ENV}" "${SCOPE}" "${FROM_VERSION}"

# Apply plugin filtering for non-special scopes
if [ "$SCOPE" != "apikey" ] && [ "$SCOPE" != "teardown" ]; then
    FILTERED_SQL=$(mktemp -p build)
    filter_plugin_code "${INSTALL_SCRIPT_SQL}" "${FILTERED_SQL}"
    mv "${FILTERED_SQL}" "${INSTALL_SCRIPT_SQL}"
fi

if [ -s "$INSTALL_SCRIPT_SQL" ] && ! has_option "manual"; then

    if has_option "service_user"; then
        # added for Jenkins to be able to skip this step, as it will never find the config file
        # this is taken care of in the update_config.py, and config_file doesn't exist necessary data is taken from environment variables
        SNOWFLAKE_ACCOUNT_NAME=${SNOWFLAKE_ACC_NAME}
    else
        SNOWFLAKE_ACCOUNT_NAME="$($CWD/get_config_key.sh core.snowflake_account_name)"
    fi

    INSTALL_SCRIPT_LOG="dsoa-deploy-$DEPLOYMENT_ENV-${NOW_TS}.log"
    #%DEV:
    mkdir .logs 2>&1
    INSTALL_SCRIPT_LOG=".logs/$INSTALL_SCRIPT_LOG"
    #%:DEV
    echo -e "\n\n--------\n"
    cat "$INSTALL_SCRIPT_SQL"
    echo -e "\n--------\n\n"

    echo -e "Deploying to Snowflake with the snow_agent_$CONNECTION_ENV connection profile and as the $DEPLOYMENT_ENV deployment environment\n"

    if ! has_option "skip_confirm"; then
        read -p "Press Enter if you wish to continue deployment with script above or Ctrl+C to exit" </dev/tty
    fi

    if ! has_option "no_dep"; then
        if ! $CWD/send_bizevent.sh "${SCOPE}" "STARTED" "${DEPLOYMENT_ID}"; then
            echo "Encountered issues when sending deployment bizevent, proceeding..."
        fi
    fi
    #%DEV:

    if ! has_option "no_dep" && ! has_option "service_user"; then
        #%:DEV
        pushd build
        snow sql --connection "snow_agent_$CONNECTION_ENV" \
            --filename "$(basename ${INSTALL_SCRIPT_SQL})"
        popd
        #%DEV:
    elif has_option "service_user"; then
        pushd build
        snow sql --temporary-connection \
            --account ${SNOWFLAKE_ACCOUNT_NAME} \
            --user ${SNOWFLAKE_USER_NAME} \
            --filename "$(basename ${INSTALL_SCRIPT_SQL})"
        popd
    fi
    #%:DEV

    cat "$INSTALL_SCRIPT_SQL" >>"$INSTALL_SCRIPT_LOG"

    rm ${INSTALL_SCRIPT_SQL}

elif has_option "manual"; then
    echo "Skipping automated deployment"
else
    echo "No scripts matching requested deploy filter: $SCOPE"
fi

if ! has_option "no_dep"; then
    if ! $CWD/send_bizevent.sh "${SCOPE}" "FINISHED" "${DEPLOYMENT_ID}"; then
        echo "Encountered issues when sending deployment bizevent, proceeding..."
    fi
fi

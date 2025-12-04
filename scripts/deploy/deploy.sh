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
# Call as ./deploy.sh "$ENV" "$PARAM1" "$PARAM2" "$PARAM3"
#%DEV:
# Double quotes around parameters are necessary if param1 is left empty, and param2 is to be specified
#%:DEV
#
# Args:
# * ENV      [REQUIRED] - needs to be a environment identifier so that there is a config-$ENV.yml file in the same folder as this script
# * PARAM1   [OPTIONAL] - can be either
#              = config         - which will update Dynatrace Snowflake Observability Agent configuration
#              = apikey         - which will install new Dynatrace Token for Dynatrace Snowflake Observability Agent
#              = manual         - this will prepare the complete installation script but will not run snowflake-cli to run it
#              = teardown       - this will remove Dynatrace Snowflake Observability Agent completely
#              = *              - this will be used to ONLY process scripts PREFIXed with this value, or ALL if none provided
#%DEV:
# * PARAM2   [OPTIONAL] - if set to
#              = no_dep         - the deploy procedure will omit the step of sending script to snowflake
#              = service_user   - the deploy will use jenkins service user data from environment variables
#              = *              - the deploy will be executed using data from "conf/config-$1.yml"
# * PARAM3   [OPTIONAL] - if set to
#              = skip_confirm   - will not wait for confirmation before deploying to Snowflake
#%:DEV
#

ENV=$1
PARAM=$2
CWD=$(dirname "$0")

if [ "$PARAM" == "manual" ]; then
    "$CWD/setup.sh"
else
    "$CWD/setup.sh" $ENV
fi

echo "Deploying Dynatrace Snowflake Observability Agent with [$ENV] configuration, using PARAM=[$PARAM]"

if [ "$ENV" == '' ]; then
    echo "Needs environment name to proceed"
    exit 1
fi
#%DEV:
# we only need to check DTAGENT_TOKEN if we are deploying through Jenkins
if [ "$3" == 'service_user' ] && [ -z "$DTAGENT_TOKEN" ]; then
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
    if [ "$3" != 'no_dep' ] && [ "$3" != 'service_user' ]; then
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

if [ "$PARAM" == "manual" ]; then
    INSTALL_SCRIPT_SQL="DSOA-deploy-script-${DEPLOYMENT_ENV}-${NOW_TS}.sql"
else
    INSTALL_SCRIPT_SQL=$(mktemp -p build)
    # clean up this way, because rm did not always work
    trap " rm -f ${INSTALL_SCRIPT_SQL} " EXIT
fi

# preparing one big deployment script
$CWD/prepare_deploy_script.sh "${INSTALL_SCRIPT_SQL}" "${ENV}" "${PARAM}"

if [ -s "$INSTALL_SCRIPT_SQL" ] && [ "$PARAM" != "manual" ]; then

    if [ "${PARAM}" == "service_user" ]; then
        # added for Jenkins to be able to skip this step, as it will never find the config file
        # this is taken care of in the update_config.py, and config_file doesn't exist necessary data is taken from environment variables
        SNOWFLAKE_ACCOUNT_NAME=${SNOWFLAKE_ACC_NAME}
    else
        SNOWFLAKE_ACCOUNT_NAME="$($CWD/get_config_key.sh core.snowflake_account_name)"
    fi

    INSTALL_SCRIPT_LOG="DSOA-deploy-$DEPLOYMENT_ENV-${NOW_TS}.log"
    #%DEV:
    mkdir .logs 2>&1
    INSTALL_SCRIPT_LOG=".logs/$INSTALL_SCRIPT_LOG"
    #%:DEV
    echo -e "\n\n--------\n"
    cat "$INSTALL_SCRIPT_SQL"
    echo -e "\n--------\n\n"

    echo -e "Deploying to Snowflake with the snow_agent_$CONNECTION_ENV connection profile and as the $DEPLOYMENT_ENV deployment environment\n"

    if [ "$4" != 'skip_confirm' ]; then
        read -p "Press Enter if you wish to continue deployment with script above or Ctrl+C to exit" </dev/tty
    fi

    if [ "$PARAM" != 'no_dep' ]; then
        if ! $CWD/send_bizevent.sh "${PARAM}" "STARTED" "${DEPLOYMENT_ID}"; then
            echo "Encountered issues when sending deployment bizevent, proceeding..."
        fi
    fi

    #%DEV:
    if [ "$3" != 'no_dep' ] && [ "$3" != 'service_user' ]; then
        #%:DEV
        pushd build
        snow sql --connection "snow_agent_$CONNECTION_ENV" \
            --filename "$(basename ${INSTALL_SCRIPT_SQL})"
        popd
        #%DEV:
    elif [ "$3" == 'service_user' ]; then

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

elif [ "$PARAM" == 'manual' ]; then
    echo "Skipping automated deployment"
else
    echo "No scripts matching requested deploy filter: $PARAM"
fi

if [ "$PARAM" != 'no_dep' ]; then
    if ! $CWD/send_bizevent.sh "${PARAM}" "FINISHED" "${DEPLOYMENT_ID}"; then
        echo "Encountered issues when sending deployment bizevent, proceeding..."
    fi
fi

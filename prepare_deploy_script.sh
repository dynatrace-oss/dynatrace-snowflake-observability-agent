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
#
# This is a script for preparing single SQL deploy script
# which could be installed automatically (by deploy.sh) or manually on Snowflake
# Call as ./prepare_deploy_script.sh "$INSTALL_SCRIPT_SQL" "$ENV" "$PARAM"
#
# Args:
# * INSTALL_SCRIPT_SQL [REQUIRED] - path to the file where installation script must be written to
# * ENV                [REQUIRED] - needs to be a environment identifier so that there is a config-$ENV.json file in the same folder as this script
# * PARAM              [OPTIONAL] - can be either
#                       = config         - which will update Dynatrace Snowflake Observability Agent configuration
#                       = apikey         - which will install new Dynatrace Token for Dynatrace Snowflake Observability Agent
#                       = manual         - this will prepare the complete installation script but will not run snowflake-cli to run it
#                       = teardown       - this will remove Dynatrace Snowflake Observability Agent completely
#                       = *              - this will be used to ONLY process scripts PREFIXed with this value, or ALL if none provided
INSTALL_SCRIPT_SQL="$1"
ENV="$2"
PARAM="$3"

#
# checking multitenancy TAG
#
TAG=$(./get_config_key.sh core.tag)
TAG=${TAG:-""}

echo "Deploying with tag "${TAG}""

if [ "$PARAM" == 'config' ]; then
    #
    #   --- script for updating Dynatrace Snowflake Observability Agent configuration ----
    #
    echo "Will update configuration"
    echo -e "\n\n--- local configuration ---\n" \
        >>"$INSTALL_SCRIPT_SQL"

    FILES_FOR_CONF_UPDATE=(
        "build/031_configuration_table.sql"
        "build/032_f_get_config_value.sql"
        "build/033_instruments_table.sql"
        "build/035_resource_monitor.sql"
        "build/036_update_plugin_schedule.sql"
        "build/037_update_all_plugins_schedule.sql"
        "build/038_update_configuration.sql"
    )

    for file in "${FILES_FOR_CONF_UPDATE[@]}"; do
        cat $file >>"$INSTALL_SCRIPT_SQL"
    done
fi

if [ "$PARAM" != 'apikey' ] && [ "$PARAM" != 'config' ] && [ "$PARAM" != 'teardown' ]; then
    #
    #   --- script for updating whole or part of Dynatrace Snowflake Observability Agent  ----
    #
    if [ "$PARAM" == '' ] || [ "$PARAM" == "manual" ]; then
        SQL_FILES='*.sql'
    else
        SQL_FILES="$PARAM*.sql"
    fi

    echo "Will process [build/$SQL_FILES]"

    #
    #   --- building one big script to be run
    #
    find 'build/'$SQL_FILES -type f -print |
        sort |
        xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
            >"$INSTALL_SCRIPT_SQL"

    echo "Deploy script prepared"
fi

if [ "$PARAM" == 'teardown' ]; then
    cat <<EOF >>$INSTALL_SCRIPT_SQL
use role ACCOUNTADMIN;

drop integration if exists DTAGENT_API_INTEGRATION;

drop database if exists DTAGENT_DB;
drop warehouse if exists DTAGENT_WH;

drop role if exists DTAGENT_ADMIN;
drop role if exists DTAGENT_VIEWER;
drop resource monitor if exists DTAGENT_RS;
EOF
fi

if [ "$PARAM" == 'apikey' ] || [ "$PARAM" == "manual" ] || [ "$PARAM" == "" ]; then
    #
    #   --- we do not update API key each time we run - you need to request that explicitly
    #
    echo "Updating API Key from environment variable DTAGENT_TOKEN in $ENV environment"

    ./update_secret.sh "${INSTALL_SCRIPT_SQL}"

    echo "Updating all plugins from the configuration provided"

    cat <<EOF >>$INSTALL_SCRIPT_SQL
use role ACCOUNTADMIN; use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH;
call DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();
EOF
fi

#
# ensuring we have replaced configuration and instruments file upload with inline INSERT
#
SQL_INGEST_CONFIG=$(./prepare_configuration_ingest.sh)
SQL_INGEST_INSTRUMENTS=$(./prepare_instruments_ingest.sh)

awk -v config="${SQL_INGEST_CONFIG}" '
  BEGIN { in_block = 0 }
  /--%UPLOAD:CONFIG/ { print; gsub(/\\\\\*/, "*", config); print config; in_block = 1; next }
  /--%:UPLOAD:CONFIG/ { in_block = 0 }
  !in_block { print }
' "$INSTALL_SCRIPT_SQL" |
    awk -v config="${SQL_INGEST_INSTRUMENTS}" '
  BEGIN { in_block = 0 }
  /--%UPLOAD:INSTRUMENTS/ { print; print config; in_block = 1; next }
  /--%:UPLOAD:INSTRUMENTS/ { in_block = 0 }
  !in_block { print }
' |
    awk 'BEGIN { print_out=1; } 
    /^[#][%]UPLOAD:SKIP[:].*/ { print_out=0; }
    { if (print_out==1) print $0; }
    /^[#][%][:]UPLOAD:SKIP.*/ { print_out=1; }' \
        >temp.sql && mv temp.sql "$INSTALL_SCRIPT_SQL"

#
#   --- Running the scripts (or configuration update) with SnowSQL
#   Removing SQL comments, as SnowCLI has problems reading them.
#
if [ $(uname -s) = 'Darwin' ]; then
    sed -i "" -E -e 's/--.*$//' "$INSTALL_SCRIPT_SQL"
    sed -i "" -E -e '/^\/\*/,/\*\//d' "$INSTALL_SCRIPT_SQL"

    if [ -n "$TAG" ]; then
        sed -i "" -E -e "s/DTAGENT_/DTAGENT_${TAG}_/g" "$INSTALL_SCRIPT_SQL"
        sed -i "" -E -e "s/${TAG}_${TAG}_/${TAG}_/g" "$INSTALL_SCRIPT_SQL"
    fi
else
    sed -i -E -e 's/--.*$//' "$INSTALL_SCRIPT_SQL"
    sed -i -E -e '/^\/\*/,/\*\//d' "$INSTALL_SCRIPT_SQL"

    if [ -n "$TAG" ]; then
        sed -i -E -e "s/DTAGENT_/DTAGENT_${TAG}_/g" "$INSTALL_SCRIPT_SQL"
        sed -i -E -e "s/${TAG}_${TAG}_/${TAG}_/g" "$INSTALL_SCRIPT_SQL"
    fi
fi

if [ "$PARAM" == 'manual' ]; then
    echo "-----"
    echo "Dynatrace Snowflake Observability Agent Deployment SQL script has been created in file ${INSTALL_SCRIPT_SQL}"
    echo "-----"
fi

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
# This is a script for preparing single SQL deploy script
# which could be installed automatically (by deploy.sh) or manually on Snowflake
# Call as ./prepare_deploy_script.sh "$INSTALL_SCRIPT_SQL" "$ENV" "$SCOPE" "$FROM_VERSION"
#
# Args:
# * INSTALL_SCRIPT_SQL [REQUIRED] - path to the file where installation script must be written to
# * ENV                [REQUIRED] - environment identifier (config-$ENV.yml must exist)
# * SCOPE              [REQUIRED] - deployment scope:
#                       init, setup, plugins, config, agents, apikey, all, teardown, upgrade, or file_part
# * FROM_VERSION       [OPTIONAL] - version number for upgrade scope
#

INSTALL_SCRIPT_SQL="$1"
ENV="$2"
SCOPE="$3"
FROM_VERSION="$4"
CWD=$(dirname "$0")

#
# checking multitenancy TAG
#
TAG=$($CWD/get_config_key.sh core.tag)
TAG=${TAG:-""}

echo "Deploying with tag "${TAG}""

# Map scope to file prefixes
case "$SCOPE" in
    init)
        SQL_FILES="00_init.sql"
        ;;
    setup)
        SQL_FILES="10_setup.sql"
        ;;
    plugins)
        SQL_FILES="20_plugins/*.sql"
        ;;
    config)
        SQL_FILES="30_config.sql"
        ;;
    agents)
        SQL_FILES="70_agents.sql"
        ;;
    all)
        SQL_FILES="00_init.sql 10_setup.sql 20_plugins/*.sql 30_config.sql 70_agents.sql"
        ;;
    upgrade)
        if [ -z "$FROM_VERSION" ]; then
            echo "ERROR: --from-version required for upgrade scope"
            exit 1
        fi
        # Process upgrade scripts >= FROM_VERSION
        SQL_FILES="09_upgrade/*.sql"
        ;;
    apikey|teardown)
        # These are handled specially below
        SQL_FILES=""
        ;;
    *)
        # Treat as file_part - custom prefix
        SQL_FILES="$SCOPE*.sql"
        ;;
esac

if [ "$SCOPE" == 'config' ]; then
    #
    #   --- script for updating Dynatrace Snowflake Observability Agent configuration ----
    #
    echo "Will update configuration"
    echo -e "\n\n--- local configuration ---\n" \
        >>"$INSTALL_SCRIPT_SQL"

    FILES_FOR_CONF_UPDATE=(
        "build/config/040_update_config.sql"
    )

    for file in "${FILES_FOR_CONF_UPDATE[@]}"; do
        cat $file >>"$INSTALL_SCRIPT_SQL"
    done
fi

if [ "$SCOPE" != 'apikey' ] && [ "$SCOPE" != 'config' ] && [ "$SCOPE" != 'teardown' ]; then
    #
    #   --- script for updating whole or part of Dynatrace Snowflake Observability Agent  ----
    #

    echo "Will process [build/$SQL_FILES]"

    #
    #   --- building one big script to be run
    #
    if [ "$SCOPE" == "upgrade" ]; then
        # For upgrade, filter by version
        find build/$SQL_FILES -type f -print |
            awk -F'/' -v from_ver="$FROM_VERSION" '
                function version_to_num(v) {
                    split(v, parts, ".");
                    return parts[1] * 1000000 + parts[2] * 1000 + parts[3];
                }
                {
                    # Extract version from filename (e.g., 09_upgrade/v1.2.3.sql or v1.2.3_something.sql)
                    if (match($0, /v([0-9]+\.[0-9]+\.[0-9]+)/, arr)) {
                        file_ver = arr[1];
                        if (version_to_num(file_ver) >= version_to_num(from_ver)) {
                            print $0;
                        }
                    } else {
                        # Print files without version numbers
                        print $0;
                    }
                }
            ' |
            sort |
            xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
                >"$INSTALL_SCRIPT_SQL"
    else
        find build/$SQL_FILES -type f -print 2>/dev/null |
            sort |
            xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
                >"$INSTALL_SCRIPT_SQL"
    fi

    echo "Deploy script prepared"
fi

if [ "$SCOPE" == 'teardown' ]; then
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

if [ "$SCOPE" == 'apikey' ] || [ "$SCOPE" == 'all' ]; then
    #
    #   --- we do not update API key each time we run - you need to request that explicitly
    #
    echo "Updating API Key from environment variable DTAGENT_TOKEN in $ENV environment"

    $CWD/update_secret.sh "${INSTALL_SCRIPT_SQL}"

    echo "Updating all plugins from the configuration provided"

    cat <<EOF >>$INSTALL_SCRIPT_SQL
use role ACCOUNTADMIN; use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH;
call DTAGENT_DB.CONFIG.UPDATE_FROM_CONFIGURATIONS();
EOF
fi

#
# ensuring we have replaced configuration file upload with inline INSERT
#
SQL_INGEST_CONFIG=$($CWD/prepare_configuration_ingest.sh)

awk -v config="${SQL_INGEST_CONFIG}" '
  BEGIN { in_block = 0 }
  /--%UPLOAD:CONFIG/ { print; gsub(/\\\\\*/, "*", config); print config; in_block = 1; next }
  /--%:UPLOAD:CONFIG/ { in_block = 0 }
  !in_block { print }
' "$INSTALL_SCRIPT_SQL" |
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

if [ "$SCOPE" == 'manual' ]; then
    echo "-----"
    echo "Dynatrace Snowflake Observability Agent Deployment SQL script has been created in file ${INSTALL_SCRIPT_SQL}"
    echo "-----"
fi

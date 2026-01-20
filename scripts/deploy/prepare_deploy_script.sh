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
#                       init, admin, setup, plugins, config, agents, apikey, all, teardown, upgrade, or file_part
# * FROM_VERSION       [OPTIONAL] - version number for upgrade scope
#

INSTALL_SCRIPT_SQL="$1"
ENV="$2"
SCOPE="$3"
FROM_VERSION="$4"
IS_MANUAL="$5"
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
    admin)
        SQL_FILES="10_admin.sql"
        ;;
    setup)
        SQL_FILES="20_setup.sql"
        ;;
    plugins)
        SQL_FILES="30_plugins/*.sql"
        ;;
    config)
        SQL_FILES="40_config.sql"
        ;;
    agents)
        SQL_FILES="70_agents.sql"
        ;;
    all)
        SQL_FILES="00_init.sql 10_admin.sql 20_setup.sql 30_plugins/*.sql 40_config.sql 70_agents.sql"
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

# Check if required SQL files exist in build folder (skip for scopes with empty SQL_FILES)
if [ -n "$SQL_FILES" ]; then
    if ! find build/$SQL_FILES -type f 2>/dev/null | grep -q .; then
        echo "ERROR: Build files missing for scope $SCOPE"
        exit 1
    fi
fi

if [ "$SCOPE" != 'apikey' ] && [ "$SCOPE" != 'teardown' ]; then
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
            awk -v from_ver="$FROM_VERSION" '
                function version_to_num(v) {
                    split(v, parts, ".");
                    return parts[1] * 1000000 + parts[2] * 1000 + parts[3];
                }
                {
                    # Extract version from filename (e.g., 09_upgrade/v1.2.3.sql or v1.2.3_something.sql)
                    if (match($0, /v[0-9]+\.[0-9]+\.[0-9]+/)) {
                        # Extract the matched version string
                        file_ver = substr($0, RSTART + 1, RLENGTH - 1);
                        if (version_to_num(file_ver) > version_to_num(from_ver)) {
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
        # Process each SQL file pattern separately
        for pattern in $SQL_FILES; do
            find build/$pattern -type f -print 2>/dev/null
        done | sort | xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
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
use role DTAGENT_OWNER; use database DTAGENT_DB; use schema CONFIG; use warehouse DTAGENT_WH;
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
            {
                # Check for start marker: --%PLUGIN:plugin_name: or #%PLUGIN:plugin_name:
                if ($0 ~ /^(--|#)%PLUGIN:/) {
                    start_pattern = "%PLUGIN:" plugin ":"
                    if (index($0, start_pattern) > 0) {
                        active=0;
                    }
                }

                # Print line only if active
                if (active==1) print $0;

                # Check for end marker: --%:PLUGIN:plugin_name or #%:PLUGIN:plugin_name
                if ($0 ~ /^(--|#)%:PLUGIN:/) {
                    end_pattern = "%:PLUGIN:" plugin
                    # Make sure we match the exact plugin name, not a prefix
                    if (index($0, end_pattern) > 0) {
                        # Check if followed by end of line or whitespace, not another colon
                        idx = index($0, end_pattern)
                        len = length(end_pattern)
                        rest = substr($0, idx + len)
                        if (rest == "" || rest ~ /^[ \t]*$/) {
                            active=1;
                        }
                    }
                }
            }
        ' "$temp_file" > "$output_file"
        cp "$output_file" "$temp_file"
    done

    rm "$temp_file"
}

# Get list of plugins to exclude
EXCLUDED_PLUGINS=$($CWD/list_plugins_to_exclude.sh)

# Apply plugin filtering for non-special scopes
if [ "$SCOPE" != "apikey" ] && [ "$SCOPE" != "teardown" ]; then
    if [ -n "$EXCLUDED_PLUGINS" ]; then
        EXCLUDED_PLUGINS_FORMATTED=$(echo "$EXCLUDED_PLUGINS" | tr '\n' ',' | sed 's/,$//')
        echo "Filtering out disabled plugins: $EXCLUDED_PLUGINS_FORMATTED"
        FILTERED_SQL=$(mktemp)
        filter_plugin_code "${INSTALL_SCRIPT_SQL}" "${FILTERED_SQL}"
        mv "${FILTERED_SQL}" "${INSTALL_SCRIPT_SQL}"
    fi
fi

#
#   Cleaning up the final script
#
# Set sed in-place flag based on OS
if [ $(uname -s) = 'Darwin' ]; then
    SED_INPLACE=("sed" "-i" "")
else
    SED_INPLACE=("sed" "-i")
fi

# Remove SQL line comments
"${SED_INPLACE[@]}" -E -e 's/--.*$//' "$INSTALL_SCRIPT_SQL"
# Remove SQL block comments
"${SED_INPLACE[@]}" -E -e '/^\/\*/,/\*\//d' "$INSTALL_SCRIPT_SQL"
# Remove Python comment-only lines (with or without leading whitespace)
"${SED_INPLACE[@]}" -E -e '/^[[:space:]]*#/d' "$INSTALL_SCRIPT_SQL"
# Remove Python inline comments
"${SED_INPLACE[@]}" -E -e 's/[[:space:]]+#.*$//' "$INSTALL_SCRIPT_SQL"

# Handle multitenancy TAG replacements
if [ -n "$TAG" ]; then
    "${SED_INPLACE[@]}" -E -e "s/DTAGENT_/DTAGENT_${TAG}_/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/${TAG}_${TAG}_/${TAG}_/g" "$INSTALL_SCRIPT_SQL"
fi

# Remove double newlines from the deployment script
"${SED_INPLACE[@]}" '/^$/N;/^\n$/d' "$INSTALL_SCRIPT_SQL"

if [ "$IS_MANUAL" == "true" ]; then
    echo "-----"
    echo "Dynatrace Snowflake Observability Agent Deployment SQL script has been created in file ${INSTALL_SCRIPT_SQL}"
    echo "-----"
fi

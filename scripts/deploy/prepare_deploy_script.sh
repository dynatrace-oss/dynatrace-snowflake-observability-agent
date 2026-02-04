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

#
# Get custom object names from config
#
CUSTOM_DB=$($CWD/get_config_key.sh core.snowflake.database.name)
CUSTOM_WH=$($CWD/get_config_key.sh core.snowflake.warehouse.name)
CUSTOM_RS=$($CWD/get_config_key.sh core.snowflake.resource_monitor.name)
CUSTOM_OWNER=$($CWD/get_config_key.sh core.snowflake.roles.owner)
CUSTOM_ADMIN=$($CWD/get_config_key.sh core.snowflake.roles.admin)
CUSTOM_VIEWER=$($CWD/get_config_key.sh core.snowflake.roles.viewer)
CUSTOM_API_INTEGRATION=$($CWD/get_config_key.sh core.snowflake.api_integration.name)

# Function to validate Snowflake object name
validate_snowflake_name() {
    local name="$1"
    local object_type="$2"

    # Skip validation for empty, "-", or null
    if [ -z "$name" ] || [ "$name" = "-" ] || [ "$name" = "null" ]; then
        return 0
    fi

    # Check for spaces
    if [[ "$name" =~ [[:space:]] ]]; then
        echo "ERROR: Invalid $object_type name '$name': contains spaces"
        return 1
    fi

    # Check for invalid characters (must be alphanumeric, underscore, or dollar sign)
    if [[ ! "$name" =~ ^[A-Za-z_][A-Za-z0-9_\$]*$ ]]; then
        echo "ERROR: Invalid $object_type name '$name': must start with letter or underscore, and contain only letters, numbers, underscores, or dollar signs"
        return 1
    fi

    # Check length (Snowflake max identifier length is 255)
    if [ ${#name} -gt 255 ]; then
        echo "ERROR: Invalid $object_type name '$name': exceeds maximum length of 255 characters"
        return 1
    fi

    return 0
}

# Check if both TAG and custom names are set (mutually exclusive)
CUSTOM_NAMES_USED=false
if [ -n "$CUSTOM_DB" ] && [ "$CUSTOM_DB" != "null" ] && [ "$CUSTOM_DB" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_WH" ] && [ "$CUSTOM_WH" != "null" ] && [ "$CUSTOM_WH" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_RS" ] && [ "$CUSTOM_RS" != "null" ] && [ "$CUSTOM_RS" != "" ] && [ "$CUSTOM_RS" != "-" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_OWNER" ] && [ "$CUSTOM_OWNER" != "null" ] && [ "$CUSTOM_OWNER" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_ADMIN" ] && [ "$CUSTOM_ADMIN" != "null" ] && [ "$CUSTOM_ADMIN" != "" ] && [ "$CUSTOM_ADMIN" != "-" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_VIEWER" ] && [ "$CUSTOM_VIEWER" != "null" ] && [ "$CUSTOM_VIEWER" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_API_INTEGRATION" ] && [ "$CUSTOM_API_INTEGRATION" != "null" ] && [ "$CUSTOM_API_INTEGRATION" != "" ]; then CUSTOM_NAMES_USED=true; fi

if [ -n "$TAG" ] && [ "$CUSTOM_NAMES_USED" = true ]; then
    echo "ERROR: Cannot use both multitenancy TAG ('$TAG') and custom Snowflake object names"
    echo "       Please either use core.tag for multitenancy OR custom object names, not both"
    exit 1
fi

# Validate custom names if provided
if [ "$CUSTOM_NAMES_USED" = true ]; then
    validate_snowflake_name "$CUSTOM_DB" "database" || exit 1
    validate_snowflake_name "$CUSTOM_WH" "warehouse" || exit 1
    validate_snowflake_name "$CUSTOM_RS" "resource monitor" || exit 1
    validate_snowflake_name "$CUSTOM_OWNER" "owner role" || exit 1
    validate_snowflake_name "$CUSTOM_ADMIN" "admin role" || exit 1
    validate_snowflake_name "$CUSTOM_VIEWER" "viewer role" || exit 1
    validate_snowflake_name "$CUSTOM_API_INTEGRATION" "API integration" || exit 1

    echo "Using custom Snowflake object names:"
    if [ -n "$CUSTOM_DB" ] && [ "$CUSTOM_DB" != "null" ] && [ "$CUSTOM_DB" != "" ]; then
        echo "  Database: $CUSTOM_DB"
    fi
    if [ -n "$CUSTOM_WH" ] && [ "$CUSTOM_WH" != "null" ] && [ "$CUSTOM_WH" != "" ]; then
        echo "  Warehouse: $CUSTOM_WH"
    fi
    if [ -n "$CUSTOM_RS" ] && [ "$CUSTOM_RS" != "null" ] && [ "$CUSTOM_RS" != "" ] && [ "$CUSTOM_RS" != "-" ]; then
        echo "  Resource Monitor: $CUSTOM_RS"
    fi
    if [ -n "$CUSTOM_OWNER" ] && [ "$CUSTOM_OWNER" != "null" ] && [ "$CUSTOM_OWNER" != "" ]; then
        echo "  Owner Role: $CUSTOM_OWNER"
    fi
    if [ -n "$CUSTOM_ADMIN" ] && [ "$CUSTOM_ADMIN" != "null" ] && [ "$CUSTOM_ADMIN" != "" ] && [ "$CUSTOM_ADMIN" != "-" ]; then
        echo "  Admin Role: $CUSTOM_ADMIN"
    fi
    if [ -n "$CUSTOM_VIEWER" ] && [ "$CUSTOM_VIEWER" != "null" ] && [ "$CUSTOM_VIEWER" != "" ]; then
        echo "  Viewer Role: $CUSTOM_VIEWER"
    fi
    if [ -n "$CUSTOM_API_INTEGRATION" ] && [ "$CUSTOM_API_INTEGRATION" != "null" ] && [ "$CUSTOM_API_INTEGRATION" != "" ]; then
        echo "  API Integration: $CUSTOM_API_INTEGRATION"
    fi
fi

# Function to map a single scope to file pattern
map_scope_to_files() {
    local scope="$1"
    case "$scope" in
        init)
            echo "00_init.sql"
            ;;
        admin)
            echo "10_admin.sql"
            ;;
        setup)
            echo "20_setup.sql"
            ;;
        plugins)
            echo "30_plugins/*.sql"
            ;;
        config)
            echo "40_config.sql"
            ;;
        agents)
            echo "70_agents.sql"
            ;;
        all)
            echo "00_init.sql 10_admin.sql 20_setup.sql 30_plugins/*.sql 40_config.sql 70_agents.sql"
            ;;
        upgrade)
            if [ -z "$FROM_VERSION" ]; then
                return 1
            fi
            # Process upgrade scripts >= FROM_VERSION
            echo "09_upgrade/*.sql"
            ;;
        apikey|teardown)
            # These are handled specially below
            echo ""
            ;;
        *)
            # Treat as file_part - custom prefix
            echo "${scope}*.sql"
            ;;
    esac
}

# Parse comma-separated scopes and build SQL_FILES list
INCLUDE_APIKEY=false
HAS_UPGRADE_SCOPE=false
if [[ "$SCOPE" == *,* ]]; then
    # Multiple scopes provided
    SQL_FILES=""
    IFS=',' read -ra SCOPE_ARRAY <<< "$SCOPE"
    for single_scope in "${SCOPE_ARRAY[@]}"; do
        # Trim whitespace
        single_scope=$(echo "$single_scope" | xargs)

        # Check for special scopes that can't be combined
        if [ "$single_scope" == "teardown" ] || [ "$single_scope" == "all" ]; then
            echo "ERROR: Scope '$single_scope' cannot be combined with other scopes"
            exit 1
        fi

        # Track apikey scope separately
        if [ "$single_scope" == "apikey" ]; then
            INCLUDE_APIKEY=true
            continue
        fi

        # Track upgrade scope
        if [ "$single_scope" == "upgrade" ]; then
            HAS_UPGRADE_SCOPE=true
        fi

        files=$(map_scope_to_files "$single_scope")
        if [ -n "$files" ]; then
            SQL_FILES="$SQL_FILES $files"
        fi
    done
    # Remove leading/trailing spaces and deduplicate
    SQL_FILES=$(echo "$SQL_FILES" | xargs)

    # Validate FROM_VERSION if upgrade scope is included
    if [ "$HAS_UPGRADE_SCOPE" == "true" ] && [ -z "$FROM_VERSION" ]; then
        echo "ERROR: --from-version required for upgrade scope"
        exit 1
    fi
else
    # Single scope
    # Special validation for upgrade scope
    if [ "$SCOPE" == "upgrade" ]; then
        HAS_UPGRADE_SCOPE=true
        if [ -z "$FROM_VERSION" ]; then
            echo "ERROR: --from-version required for upgrade scope"
            exit 1
        fi
    fi
    # Track apikey scope
    if [ "$SCOPE" == "apikey" ]; then
        INCLUDE_APIKEY=true
    elif [ "$SCOPE" == "all" ]; then
        INCLUDE_APIKEY=true
    fi
    SQL_FILES=$(map_scope_to_files "$SCOPE")
fi

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
    if [ "$HAS_UPGRADE_SCOPE" == "true" ]; then
        # For upgrade scope, filter by version
        # Process each SQL file pattern separately, applying version filter to upgrade files
        (
            for pattern in $SQL_FILES; do
                # Use eval to let find handle glob patterns properly
                eval "find build/$pattern -type f -print 2>/dev/null"
            done
        ) |
            awk -v from_ver="$FROM_VERSION" '
                function version_to_num(v) {
                    split(v, parts, ".");
                    return parts[1] * 1000000 + parts[2] * 1000 + parts[3];
                }
                {
                    # Check if this is an upgrade file
                    if (match($0, /09_upgrade/)) {
                        # Extract version from filename (e.g., 09_upgrade/v1.2.3.sql or v1.2.3_something.sql)
                        if (match($0, /v[0-9]+\.[0-9]+\.[0-9]+/)) {
                            # Extract the matched version string
                            file_ver = substr($0, RSTART + 1, RLENGTH - 1);
                            if (version_to_num(file_ver) > version_to_num(from_ver)) {
                                print $0;
                            }
                        } else {
                            # Print upgrade files without version numbers
                            print $0;
                        }
                    } else {
                        # Not an upgrade file, include it
                        print $0;
                    }
                }
            ' |
            sort |
            xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
                >"$INSTALL_SCRIPT_SQL"
    else
        # Process each SQL file pattern separately
        (
            for pattern in $SQL_FILES; do
                # Use eval to let find handle glob patterns properly
                eval "find build/$pattern -type f -print 2>/dev/null"
            done
        ) | sort | xargs -I {} sh -c 'echo "-- SCRIPT: $1"; cat "$1"' _ {} \; \
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

drop role if exists DTAGENT_VIEWER;
drop role if exists DTAGENT_ADMIN;
drop role if exists DTAGENT_OWNER;
--%OPTION:resource_monitor:
drop resource monitor if exists DTAGENT_RS;
--%:OPTION:resource_monitor
EOF
fi

if [ "$INCLUDE_APIKEY" == "true" ]; then
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

# Filter function to remove disabled optional component code
filter_option_code() {
    local input_file=$1
    local output_file=$2

    if [ -z "$EXCLUDED_OPTIONS" ]; then
        cat "$input_file" > "$output_file"
        return
    fi

    local temp_file=$(mktemp)
    cp "$input_file" "$temp_file"

    for option_name in $EXCLUDED_OPTIONS; do
        awk -v option="$option_name" '
            BEGIN { active=1; }
            {
                # Check for start marker: --%OPTION:option_name: or #%OPTION:option_name:
                if ($0 ~ /^(--|#)%OPTION:/) {
                    start_pattern = "%OPTION:" option ":"
                    if (index($0, start_pattern) > 0) {
                        active=0;
                    }
                }

                # Print line only if active
                if (active==1) print $0;

                # Check for end marker: --%:OPTION:option_name or #%:OPTION:option_name
                if ($0 ~ /^(--|#)%:OPTION:/) {
                    end_pattern = "%:OPTION:" option
                    # Make sure we match the exact option name, not a prefix
                    if (index($0, end_pattern) > 0) {
                        # Check if followed by end of line or whitespace
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

# Get list of optional components to exclude
EXCLUDED_OPTIONS=$($CWD/list_options_to_exclude.sh)

# Apply option filtering for all scopes
if [ -n "$EXCLUDED_OPTIONS" ]; then
    EXCLUDED_OPTIONS_FORMATTED=$(echo "$EXCLUDED_OPTIONS" | tr ' ' ',' | sed 's/,$//')
    echo "Filtering out disabled optional components: $EXCLUDED_OPTIONS_FORMATTED"
    FILTERED_SQL=$(mktemp)
    filter_option_code "${INSTALL_SCRIPT_SQL}" "${FILTERED_SQL}"
    mv "${FILTERED_SQL}" "${INSTALL_SCRIPT_SQL}"
fi

# Check if admin scope is requested but dtagent_admin is disabled
if [[ "$SCOPE" == *"admin"* ]] && [[ "$EXCLUDED_OPTIONS" == *"dtagent_admin"* ]]; then
    echo "ERROR: Deployment scope 'admin' was requested, but core.snowflake.roles.admin is set to '-' (disabled)."
    echo "       The admin role will not be created and no admin-related operations can be performed."
    echo ""
    echo "To fix this:"
    echo "  1. Remove 'admin' from the deployment scope, OR"
    echo "  2. Set core.snowflake.roles.admin to a valid role name (or leave empty for default 'DTAGENT_ADMIN')"
    exit 1
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

# Handle multitenancy TAG replacements OR custom object name replacements (mutually exclusive)
if [ -n "$TAG" ]; then
    echo "Applying multitenancy TAG replacements..."
    "${SED_INPLACE[@]}" -E -e "s/DTAGENT_/DTAGENT_${TAG}_/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/${TAG}_${TAG}_/${TAG}_/g" "$INSTALL_SCRIPT_SQL"
elif [ "$CUSTOM_NAMES_USED" = true ]; then
    echo "Applying custom object name replacements..."

    # Replace custom names if provided
    # Use patterns that work on both BSD sed (macOS) and GNU sed (Linux)
    # Match word boundaries by looking for start/end of line or non-identifier characters

    if [ -n "$CUSTOM_DB" ] && [ "$CUSTOM_DB" != "null" ] && [ "$CUSTOM_DB" != "" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_DB([^A-Za-z0-9_\$]|$)/\1$CUSTOM_DB\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_WH" ] && [ "$CUSTOM_WH" != "null" ] && [ "$CUSTOM_WH" != "" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_WH([^A-Za-z0-9_\$]|$)/\1$CUSTOM_WH\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_RS" ] && [ "$CUSTOM_RS" != "null" ] && [ "$CUSTOM_RS" != "" ] && [ "$CUSTOM_RS" != "-" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_RS([^A-Za-z0-9_\$]|$)/\1$CUSTOM_RS\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_OWNER" ] && [ "$CUSTOM_OWNER" != "null" ] && [ "$CUSTOM_OWNER" != "" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_OWNER([^A-Za-z0-9_\$]|$)/\1$CUSTOM_OWNER\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_ADMIN" ] && [ "$CUSTOM_ADMIN" != "null" ] && [ "$CUSTOM_ADMIN" != "" ] && [ "$CUSTOM_ADMIN" != "-" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_ADMIN([^A-Za-z0-9_\$]|$)/\1$CUSTOM_ADMIN\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_VIEWER" ] && [ "$CUSTOM_VIEWER" != "null" ] && [ "$CUSTOM_VIEWER" != "" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_VIEWER([^A-Za-z0-9_\$]|$)/\1$CUSTOM_VIEWER\2/g" "$INSTALL_SCRIPT_SQL"
    fi

    if [ -n "$CUSTOM_API_INTEGRATION" ] && [ "$CUSTOM_API_INTEGRATION" != "null" ] && [ "$CUSTOM_API_INTEGRATION" != "" ]; then
        "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_API_INTEGRATION([^A-Za-z0-9_\$]|$)/\1$CUSTOM_API_INTEGRATION\2/g" "$INSTALL_SCRIPT_SQL"
    fi
fi

# Remove double newlines from the deployment script
"${SED_INPLACE[@]}" '/^$/N;/^\n$/d' "$INSTALL_SCRIPT_SQL"

if [ "$IS_MANUAL" == "true" ]; then
    echo "-----"
    echo "Dynatrace Snowflake Observability Agent Deployment SQL script has been created in file ${INSTALL_SCRIPT_SQL}"
    echo "-----"
fi

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
# Call as ./prepare_deploy_script.sh "$INSTALL_SCRIPT_SQL" "$ENV" "$SCOPE" "$FROM_VERSION" "$IS_MANUAL" "$OPTIONS_STR"
#
# Args:
# * INSTALL_SCRIPT_SQL [REQUIRED] - path to the file where installation script must be written to
# * ENV                [REQUIRED] - environment identifier (config-$ENV.yml must exist)
# * SCOPE              [REQUIRED] - deployment scope:
#                       init, admin, setup, plugins, config, agents, apikey, all, teardown, upgrade, or file_part
# * FROM_VERSION       [OPTIONAL] - version number for upgrade scope
# * IS_MANUAL          [OPTIONAL] - "true" to generate a human-readable script; "false" or empty for automated deploy
# * OPTIONS_STR        [OPTIONAL] - comma-separated deploy options (e.g. cleanup_disabled,skip_confirm)
#

INSTALL_SCRIPT_SQL="$1"
ENV="$2"
SCOPE="$3"
FROM_VERSION="$4"
IS_MANUAL="$5"
OPTIONS_STR="${6:-}"
CWD=$(dirname "$0")

# Parse comma-separated options string into an array and expose a has_option() helper.
IFS=',' read -ra _OPTIONS <<< "$OPTIONS_STR"
has_option() {
    local opt=$1
    for item in "${_OPTIONS[@]}"; do
        [[ "$item" == "$opt" ]] && return 0
    done
    return 1
}

#
# checking multitenancy TAG
#
TAG=$($CWD/get_config_key.sh core.tag)
TAG=${TAG:-""}

echo "Deploying with tag ${TAG}"

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

# Check if custom names are being used
CUSTOM_NAMES_USED=false
if [ -n "$CUSTOM_DB" ] && [ "$CUSTOM_DB" != "null" ] && [ "$CUSTOM_DB" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_WH" ] && [ "$CUSTOM_WH" != "null" ] && [ "$CUSTOM_WH" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_RS" ] && [ "$CUSTOM_RS" != "null" ] && [ "$CUSTOM_RS" != "" ] && [ "$CUSTOM_RS" != "-" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_OWNER" ] && [ "$CUSTOM_OWNER" != "null" ] && [ "$CUSTOM_OWNER" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_ADMIN" ] && [ "$CUSTOM_ADMIN" != "null" ] && [ "$CUSTOM_ADMIN" != "" ] && [ "$CUSTOM_ADMIN" != "-" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_VIEWER" ] && [ "$CUSTOM_VIEWER" != "null" ] && [ "$CUSTOM_VIEWER" != "" ]; then CUSTOM_NAMES_USED=true; fi
if [ -n "$CUSTOM_API_INTEGRATION" ] && [ "$CUSTOM_API_INTEGRATION" != "null" ] && [ "$CUSTOM_API_INTEGRATION" != "" ]; then CUSTOM_NAMES_USED=true; fi

# When custom names are used, TAG only affects telemetry (deployment.environment.tag)
# When custom names are NOT used, TAG affects both object naming AND telemetry
if [ -n "$TAG" ] && [ "$CUSTOM_NAMES_USED" = true ]; then
    echo "INFO: Both TAG and custom names provided."
    echo "      Custom names will be used for Snowflake objects."
    echo "      TAG '$TAG' will only appear in telemetry as deployment.environment.tag."
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
    #%DEV:
    echo "DEBUG: Parsed scopes: ${SCOPE_ARRAY[*]}"
    echo "DEBUG: Built SQL_FILES: [$SQL_FILES]"
    #%:DEV

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
    missing_files=false
    missing_list=""
    for pattern in $SQL_FILES; do
        if ! find build/$pattern -type f 2>/dev/null | grep -q .; then
            missing_files=true
            missing_list="$missing_list build/$pattern"
        fi
    done
    if [ "$missing_files" = true ]; then
        echo ""
        echo "ERROR: Build artifacts are missing. Run the following command first:"
        echo "       ./scripts/dev/build.sh"
        echo ""
        echo "Missing files:$missing_list"
        echo ""
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
        #%DEV:
        echo "DEBUG: Processing with upgrade scope, FROM_VERSION=$FROM_VERSION"
        #%:DEV
        (
            for pattern in $SQL_FILES; do
                # Use eval to let find handle glob patterns properly
                #%DEV:
                echo "DEBUG: Finding files matching build/$pattern" >&2
                #%:DEV
                eval "find build/$pattern -type f -print 2>/dev/null"
            done
        ) |
            awk -v from_ver="$FROM_VERSION" '
                function version_to_num(v) {
                    split(v, parts, ".");
                    return parts[1] * 1000000000 + parts[2] * 1000000 + parts[3] * 1000 + parts[4];
                }
                {
                    # Check if this is an upgrade file
                    if (match($0, /09_upgrade/)) {
                        # Extract version from filename (e.g., 09_upgrade/v1.2.3.sql, v1.2.3.4.sql)
                        if (match($0, /v[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?/)) {
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
        #%DEV:
        echo "DEBUG: Processing without upgrade scope"
        #%:DEV
        (
            for pattern in $SQL_FILES; do
                # Use eval to let find handle glob patterns properly
                #%DEV:
                echo "DEBUG: Finding files matching build/$pattern" >&2
                found_files=$(eval "find build/$pattern -type f -print 2>/dev/null")
                echo "DEBUG: Found files: $found_files" >&2
                echo "$found_files" >&2
                #%:DEV
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

    local temp_file
    temp_file=$(mktemp)
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

    local temp_file
    temp_file=$(mktemp)
    cp "$input_file" "$temp_file"

    for option_name in $EXCLUDED_OPTIONS; do
        awk -v option="$option_name" '
            BEGIN { active=1; }
            {
                # Check for start marker: --%OPTION:option_name: or #%OPTION:option_name: (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%OPTION:/) {
                    start_pattern = "%OPTION:" option ":"
                    if (index($0, start_pattern) > 0) {
                        active=0;
                    }
                }

                # Print line only if active
                if (active==1) print $0;

                # Check for end marker: --%:OPTION:option_name or #%:OPTION:option_name (with optional leading whitespace)
                if ($0 ~ /^[ \t]*(--|#)%:OPTION:/) {
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

# Function to inject ALTER TASK ... SUSPEND statements for excluded (disabled) plugins.
# This ensures stale Snowflake tasks are suspended even when plugin SQL is stripped from the
# deploy script (e.g. --scope=plugins,agents without config scope).
# Task names are extracted from the flat build artifact (build/30_plugins/<plugin>.sql) so the
# function works in packaged deployments where src/dtagent/plugins/ is not present.
inject_suspend_for_excluded_plugins() {
    local install_script="$1"

    if [ -z "$EXCLUDED_PLUGINS" ]; then
        return
    fi

    local suspend_sql=""
    for plugin_name in $EXCLUDED_PLUGINS; do
        local plugin_build_file="build/30_plugins/${plugin_name}.sql"
        if [ ! -f "$plugin_build_file" ]; then
            echo "[deploy] WARNING: built plugin SQL not found for disabled plugin: ${plugin_name} (${plugin_build_file})"
            continue
        fi

        # Extract all fully-qualified task names from CREATE OR REPLACE TASK statements in the flat build file
        while IFS= read -r task_name; do
            if [ -n "$task_name" ]; then
                suspend_sql+="alter task if exists ${task_name} suspend;"$'\n'
                echo "[deploy] Will suspend task for disabled plugin: ${plugin_name} (${task_name})"
            fi
        done < <(grep -i 'create or replace task' "$plugin_build_file" | awk '{print $5}' | sort -u)
    done

    if [ -n "$suspend_sql" ]; then
        cat >> "$install_script" <<EOF
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
${suspend_sql}
EOF
    fi
}

# Function to drop views, procedures, and tasks for excluded (disabled) plugins when
# --options=cleanup_disabled is set. Also handles fully-removed plugins listed in
# conf/removed_plugins.yml and detects orphaned TASK_DTAGENT_% tasks via INFORMATION_SCHEMA.TASKS.
# Only runs when the cleanup_disabled option is present — avoids extra Snowflake queries during
# normal deploys where speed of config scope matters.
inject_cleanup_for_excluded_plugins() {
    local install_script="$1"
    local removed_plugins_file="${CWD}/../../conf/removed_plugins.yml"

    local cleanup_sql=""

    # --- Part 1: drop objects for explicitly excluded (disabled) plugins ---
    for plugin_name in $EXCLUDED_PLUGINS; do
        local plugin_build_file="build/30_plugins/${plugin_name}.sql"
        if [ ! -f "$plugin_build_file" ]; then
            echo "[deploy] WARNING: built plugin SQL not found for cleanup of disabled plugin: ${plugin_name} (${plugin_build_file})"
            continue
        fi

        echo "[deploy] Cleaning up objects for disabled plugin: ${plugin_name}"

        # DROP TASK IF EXISTS for all tasks defined in the plugin build file
        while IFS= read -r task_name; do
            if [ -n "$task_name" ]; then
                cleanup_sql+="alter task if exists ${task_name} suspend;"$'\n'
                cleanup_sql+="drop task if exists ${task_name};"$'\n'
                echo "[deploy]   Drop task: ${task_name}"
            fi
        done < <(grep -i 'create or replace task' "$plugin_build_file" | awk '{print $5}' | sort -u)

        # DROP PROCEDURE IF EXISTS for all procedures defined in the plugin build file
        # Normalize signatures to types-only (Snowflake DROP PROCEDURE requires types, not arg names)
        while IFS= read -r proc_sig; do
            if [ -n "$proc_sig" ]; then
                cleanup_sql+="drop procedure if exists ${proc_sig};"$'\n'
                echo "[deploy]   Drop procedure: ${proc_sig}"
            fi
        done < <(grep -oi 'PROCEDURE[[:space:]]\+[^[:space:]]\+([^)]*)' "$plugin_build_file" | \
                 sed 's/^PROCEDURE[[:space:]]*//' | sort -u | \
                 python3 -c "
import sys, re
for line in sys.stdin:
    line = line.strip()
    m = re.match(r'([^(]+)\(([^)]*)\)', line)
    if m:
        name = m.group(1)
        params = m.group(2)
        if params.strip():
            type_only = ', '.join(p.strip().split()[-1] for p in params.split(','))
            print(f'{name}({type_only})')
        else:
            print(f'{name}()')
    else:
        print(line)
")

        # DROP VIEW IF EXISTS for all views defined in the plugin build file
        while IFS= read -r view_name; do
            if [ -n "$view_name" ]; then
                cleanup_sql+="drop view if exists ${view_name};"$'\n'
                echo "[deploy]   Drop view: ${view_name}"
            fi
        done < <(grep -i 'create or replace view\|create view' "$plugin_build_file" | awk '{print $5}' | sort -u)
    done

    # --- Part 2: drop tasks for fully-removed plugins (listed in conf/removed_plugins.yml) ---
    if [ -f "$removed_plugins_file" ]; then
        local in_removed=false
        local current_plugin=""
        while IFS= read -r line; do
            # Match "- name: <plugin>" entries
            if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+name:[[:space:]]+(.+)$ ]]; then
                current_plugin="${BASH_REMATCH[1]}"
                in_removed=true
                echo "[deploy] Cleaning up removed plugin: ${current_plugin}"
            # Match "    - DTAGENT_DB.APP.TASK_..." task entries under a plugin
            elif $in_removed && [[ "$line" =~ ^[[:space:]]+-[[:space:]]+(DTAGENT[^[:space:]]+TASK_DTAGENT_[^[:space:]]+)$ ]]; then
                local task_name="${BASH_REMATCH[1]}"
                cleanup_sql+="alter task if exists ${task_name} suspend;"$'\n'
                cleanup_sql+="drop task if exists ${task_name};"$'\n'
                echo "[deploy]   Drop removed task: ${task_name}"
            elif [[ "$line" =~ ^[^[:space:]] ]] && ! [[ "$line" =~ ^[[:space:]]*-[[:space:]]+name: ]]; then
                in_removed=false
            fi
        done < "$removed_plugins_file"
    fi

    # --- Part 3: detect orphaned TASK_DTAGENT_% tasks via INFORMATION_SCHEMA.TASKS ---
    # Collect all known task names from current plugin build files to identify orphans
    local known_tasks_pattern=""
    for plugin_sql in build/30_plugins/*.sql; do
        while IFS= read -r task_name; do
            [ -n "$task_name" ] && known_tasks_pattern+="${task_name}|"
        done < <(grep -i 'create or replace task' "$plugin_sql" 2>/dev/null | awk '{print $5}' | sort -u)
    done
    known_tasks_pattern="${known_tasks_pattern%|}"  # strip trailing pipe

    # Emit a Snowflake EXECUTE IMMEDIATE block that suspends and drops orphaned tasks
    # (tasks matching TASK_DTAGENT_% that are not in the known set)
    local known_tasks_sql_list=""
    if [ -n "$known_tasks_pattern" ]; then
        # Convert pipe-separated list to SQL IN (...) values
        known_tasks_sql_list=$(echo "$known_tasks_pattern" | tr '|' '\n' | \
            awk -F'.' '{print toupper($NF)}' | \
            awk '{printf "'"'"'%s'"'"',", $0}' | sed 's/,$//')
    fi

    if [ -z "$known_tasks_sql_list" ]; then
        echo "[deploy] WARNING: No known tasks found in build/30_plugins/*.sql — skipping orphan task detection to avoid dropping all tasks"
    else
        cleanup_sql+=$(cat <<EOSQL
-- Suspend and drop orphaned TASK_DTAGENT_% tasks not belonging to any active plugin
declare
  c cursor for
    select task_schema || '.' || task_name as full_name
    from information_schema.tasks
    where task_name ilike 'TASK_DTAGENT_%'
EOSQL
)
        cleanup_sql+=$'\n'"      and task_name not in (${known_tasks_sql_list})"
        cleanup_sql+=$(cat <<'EOSQL'
;
begin
  for r in c do
    call system$log_info('[deploy] Dropping orphaned task: ' || r.full_name);
    execute immediate 'alter task if exists ' || r.full_name || ' suspend';
    execute immediate 'drop task if exists ' || r.full_name;
  end for;
end;
EOSQL
)
        cleanup_sql+=$'\n'
    fi

    if [ -n "$cleanup_sql" ]; then
        echo "[deploy] Injecting cleanup SQL for disabled/removed plugins"
        cat >> "$install_script" <<EOF
use role DTAGENT_OWNER; use database DTAGENT_DB; use warehouse DTAGENT_WH;
${cleanup_sql}
EOF
    fi
}

# Apply plugin filtering for non-special scopes and inject task suspension for excluded plugins
if [ "$SCOPE" != "apikey" ] && [ "$SCOPE" != "teardown" ]; then
    inject_suspend_for_excluded_plugins "${INSTALL_SCRIPT_SQL}"
    if has_option "cleanup_disabled"; then
        inject_cleanup_for_excluded_plugins "${INSTALL_SCRIPT_SQL}"
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
if [ "$(uname -s)" = 'Darwin' ]; then
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

# Handle object name replacements
# Priority: Custom names > TAG > Default names
# When custom names are provided, TAG does not affect object naming (only telemetry)
if [ "$CUSTOM_NAMES_USED" = true ]; then
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
elif [ -n "$TAG" ]; then
    # Only apply TAG-based naming when custom names are NOT provided.
    # Replace each known DTAGENT_ SQL identifier individually using word-boundary patterns
    # (longest/most-specific identifiers first) so that config string-literal values —
    # which may contain DTAGENT_* substrings (e.g. budget FQNs like DTAGENT_DB.APP.DTAGENT_BUDGET)
    # embedded in INSERT statements by prepare_configuration_ingest.sh — are NOT corrupted.
    echo "Applying multitenancy TAG replacements..."
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_API_INTEGRATION([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_API_INTEGRATION\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_API_KEY([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_API_KEY\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_OWNER([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_OWNER\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_ADMIN([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_ADMIN\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_VIEWER([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_VIEWER\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_DB([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_DB\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_WH([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_WH\2/g" "$INSTALL_SCRIPT_SQL"
    "${SED_INPLACE[@]}" -E -e "s/(^|[^A-Za-z0-9_\$])DTAGENT_RS([^A-Za-z0-9_\$]|$)/\1DTAGENT_${TAG}_RS\2/g" "$INSTALL_SCRIPT_SQL"
fi

# Remove double newlines from the deployment script
"${SED_INPLACE[@]}" '/^$/N;/^\n$/d' "$INSTALL_SCRIPT_SQL"

if [ "$IS_MANUAL" == "true" ]; then
    echo "-----"
    echo "Dynatrace Snowflake Observability Agent Deployment SQL script has been created in file ${INSTALL_SCRIPT_SQL}"
    echo "-----"
fi

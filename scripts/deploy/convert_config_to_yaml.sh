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

# Use this script to covert your configuration file in JSON into the new YAML format.
# If you have multiple configuration objects in the JSON file (i.e., a JSON array), multiple YAML files will be created,
# one per configuration object.
#
# This script also automatically migrates old configuration paths to the new structure:
# - SNOWFLAKE_ACCOUNT_NAME -> SNOWFLAKE.ACCOUNT_NAME
# - SNOWFLAKE_HOST_NAME -> SNOWFLAKE.HOST_NAME
# - SNOWFLAKE_CREDIT_QUOTA -> SNOWFLAKE.RESOURCE_MONITOR.CREDIT_QUOTA
# - SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS -> SNOWFLAKE.DATABASE.DATA_RETENTION_TIME_IN_DAYS
#
# PARAMS: $1 - path to JSON file to convert

if ! command -v jq &> /dev/null || ! command -v yq &> /dev/null; then
    echo "Both jq and yq are required but not installed."
    exit 1
fi

JSON_FILE=$1

if [ -z "$JSON_FILE" ]; then
    echo "Usage: $0 <json_file>"
    exit 1
fi

BASE_NAME=$(basename "$JSON_FILE" .json)
DIR=$(dirname "$JSON_FILE")

# Function to migrate old config paths to new structure
migrate_config_paths() {
    jq '
        # Migrate CORE.SNOWFLAKE_* paths to nested SNOWFLAKE structure
        if type == "object" and has("CORE") then
            .CORE as $core |
            # Check if we have any old SNOWFLAKE_* keys to migrate
            if ($core | has("SNOWFLAKE_ACCOUNT_NAME") or has("SNOWFLAKE_HOST_NAME") or
                has("SNOWFLAKE_CREDIT_QUOTA") or has("SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS")) then
                .CORE = (
                    # Build new SNOWFLAKE object
                    {
                        "SNOWFLAKE": (
                            (if $core.SNOWFLAKE_ACCOUNT_NAME then {"ACCOUNT_NAME": $core.SNOWFLAKE_ACCOUNT_NAME} else {} end) +
                            (if $core.SNOWFLAKE_HOST_NAME then {"HOST_NAME": $core.SNOWFLAKE_HOST_NAME} else {} end) +
                            (if $core.SNOWFLAKE_CREDIT_QUOTA then {"RESOURCE_MONITOR": {"CREDIT_QUOTA": $core.SNOWFLAKE_CREDIT_QUOTA}} else {} end) +
                            (if $core.SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS then {"DATABASE": {"DATA_RETENTION_TIME_IN_DAYS": $core.SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS}} else {} end)
                        )
                    } +
                    # Keep all other CORE keys except the old SNOWFLAKE_* ones
                    ($core | del(.SNOWFLAKE_ACCOUNT_NAME, .SNOWFLAKE_HOST_NAME, .SNOWFLAKE_CREDIT_QUOTA, .SNOWFLAKE_DATA_RETENTION_TIME_IN_DAYS))
                )
            else
                .
            end
        else
            .
        end
    '
}

# Check if array using jq
IS_ARRAY=$(jq -e 'type == "array"' "$JSON_FILE")

if [ "$IS_ARRAY" = "true" ]; then
    LENGTH=$(jq '. | length' "$JSON_FILE")
    for i in $(seq 0 $((LENGTH-1))); do
        if [ $i -eq 0 ]; then
            OUTPUT_FILE="$DIR/$BASE_NAME.yml"
        else
            OUTPUT_FILE="$DIR/${BASE_NAME}_$i.yml"
        fi
        # Extract item, migrate paths, convert keys to lowercase, then convert to YAML
        jq ".[$i]" "$JSON_FILE" | migrate_config_paths | \
            jq 'walk(if type == "object" then with_entries(.key |= ascii_downcase) else . end)' | \
            yq -P > "$OUTPUT_FILE"
        echo "Created: $OUTPUT_FILE (with migrated paths)"
    done
else
    OUTPUT_FILE="$DIR/$BASE_NAME.yml"
    # Migrate paths, convert keys to lowercase, then convert to YAML
    cat "$JSON_FILE" | migrate_config_paths | \
        jq 'walk(if type == "object" then with_entries(.key |= ascii_downcase) else . end)' | \
        yq -P > "$OUTPUT_FILE"
    echo "Created: $OUTPUT_FILE (with migrated paths)"
fi
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
# This script retrieves a value from a JSON configuration file (stored in BUILD_CONFIG_FILE=build/config.json) 
# based on the provided key name.
# It uses jq to parse the JSON file and extract the value associated with the specified key.

get_value_by_name() {
  local KEY_PATH=$1
  echo $(jq -r --arg PATH "$KEY_PATH" '.[] | select(.PATH == $PATH) | .VALUE' "$BUILD_CONFIG_FILE")
}

echo $(get_value_by_name "$1")
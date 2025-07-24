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
# This is a script for prepares SQL code that will insert configuration into temporary table
SELECT_STATEMENTS=""

while IFS= read -r config; do
  ESCAPED_CONFIG=$(echo "$config" | sed "s/'/''/g")
  SELECT_STATEMENTS+="SELECT PARSE_JSON('$ESCAPED_CONFIG') as data UNION ALL "
done < <(jq -c 'map(if .VALUE | type == "string" then .VALUE |= gsub("\\*"; "\\\\*") else . end) | .[]' "${BUILD_CONFIG_FILE}")

# this ensures we only have comma separated entries in case of > 1
SELECT_STATEMENTS=${SELECT_STATEMENTS%UNION ALL }

# final SQL code
SQL="INSERT INTO TEMP_CONFIG (DATA) $SELECT_STATEMENTS;"

echo $SQL
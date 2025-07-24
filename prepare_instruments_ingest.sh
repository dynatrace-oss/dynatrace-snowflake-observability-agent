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
# This is a script for prepares SQL code that will insert instrumetns definition into temporary table
INSTRUMENTS_FILE="build/instruments-def.json"

FILTERED_JSON=$(jq 'walk(if type == "object" then with_entries(select(.key | test("^__") | not)) else . end)' "$INSTRUMENTS_FILE")
COMPRESSED_JSON=$(echo "$FILTERED_JSON" | jq -c .)
ESCAPED_JSON=$(echo "$COMPRESSED_JSON" | sed "s/'/''/g")

# the final SQL code
SQL="INSERT INTO TEMP_INSTRUMENTS (DATA) SELECT (PARSE_JSON('"$ESCAPED_JSON"'));"

echo $SQL
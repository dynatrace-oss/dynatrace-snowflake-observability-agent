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

# Updating build number

TS=$(date +%s%3)
sed -E 's/^BUILD[ ]*=[ ]*([0-9]+)/BUILD = '"$TS"'/g' src/dtagent/version.py >build/_version.py

check_missing_imports() {
  DTAGENT_CHECK=$(flake8 "$1" --select F821)
  if [ ! -z "$DTAGENT_CHECK" ]; then
    echo "$1 has potentially missing imports:"
    echo "$DTAGENT_CHECK"
    exit 1
  fi
}

#
# This script is used to create single 700_dtagent.py src/file from src/dtagent package
#
process_files() {
  local src_file=$1
  local dest_file=$2

  gawk 'match($0, /[#]{2}INSERT (.+)/, a) {system("sed -e \"1,/##endregion COMPILE_REMOVE/d\" "a[1]); next } 1' "$src_file" |
    sed -e '/##region.* IMPORTS/,/##endregion COMPILE_REMOVE/d' |
    grep -v '# COMPILE_REMOVE' >"$dest_file"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' -e '/dtagent/!b' -e '/import/d' "$dest_file"
  else
    sed -i -e '/dtagent/!b' -e '/import/d' "$dest_file"
  fi

  check_missing_imports "$dest_file"
}

process_files "src/dtagent/agent.py" "build/_dtagent.py"
process_files "src/dtagent/connector.py" "build/_send_telemetry.py"

echo "Compiling Dynatrace Snowflake Observability Agent done"

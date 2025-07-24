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
# This script is used to build target SQLs that will be put into ../agent/sql/setup
# It processes the scripts in src/sql and looks for ##INSERT $fileName hints
#

# Cleaning up build directory
rm -Rf build/*

SOURCE_CODE_QUALITY_CHECK_FILE=.logs/source-code-quality-$(date '+%Y%m%d-%H%M%S').log
TEST_CODE_QUALITY_CHECK_FILE=.logs/test-code-quality-$(date '+%Y%m%d-%H%M%S').log

# The ignored cases are:
# C0301 - line-too-long - mostly caught in docstrings
# W0511 - TODO labels should be ignored, as we have them in the code to track what needs to be done
# W0611 - unused-import - we need general imports in src/dtagent/__init__.py, src/dtagent/agent.py, src/dtagent/connector.py
# E0401 - import-error - with all files being parsed to one this shows plenty false negatives
# C0415 - import-outside-top-level - these are necessary to avoid circular imports in some cases
# C0411 - wrong-import-order - impossible to avoid with imports in functions
# R0914 - too-many-locals - in the update_docs file, can't see how to avoid it
# R0902 - too-many-instance-attributes
# R0903 - too-few-public-methods
# R0913 - too-many-arguments - for generic methods like _log_entries - impossible to avoid without heavily refactoring
# R1737 - use-yield-from - yield from reparse objects it iterates on to strings, so it doesn't fit our use case
# R0915 - too-many-statements in a function

SRC_IGNORED_CASES=C0301,W0611,E0401,C0415,C0411,R0914,R0902,R0903,R0913,R1737,R0912,W0107,C0103,W1203,R0915,W0511
TEST_IGNORED_CASES=$SRC_IGNORED_CASES,C0114,C0115,C0116,W0212,E0611,W0613,R1702,R1718

pylint src/ --recursive=y --disable=$SRC_IGNORED_CASES --output-format=parseable >$SOURCE_CODE_QUALITY_CHECK_FILE
pylint test/ --recursive=y --disable=$TEST_IGNORED_CASES, --output-format=parseable >$TEST_CODE_QUALITY_CHECK_FILE

if ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" || ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE"; then
    echo "Found code quality issues."

    ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" && echo "Result file $SOURCE_CODE_QUALITY_CHECK_FILE is not empty."
    ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE" && echo "Result file $TEST_CODE_QUALITY_CHECK_FILE is not empty."
    echo "Check the content and sort out code quality issues before proceeding."

    exit 1
else
    rm $SOURCE_CODE_QUALITY_CHECK_FILE
    rm $TEST_CODE_QUALITY_CHECK_FILE
    echo "Code quality checks passed for test/ and src/."
fi

# Compiling to build/_dtagent.py
./compile.sh

if [ $? -eq 1 ]; then
    exit 1
fi
# Assembling instrument definitions configuration
TMP_INST=$(mktemp -d -p build)
find src -type f -name instruments-def.yml | while IFS= read -r inst_file; do
    source_conf_name=$(basename "$(dirname "$inst_file")")
    source_name=${source_conf_name%.*}
    echo "Assembling from $source_name"

    python -c "import yaml, json; print(json.dumps(yaml.load(open('$inst_file'), Loader=yaml.FullLoader), indent=4))" >"${TMP_INST}/${source_name}-instruments-def.json"

done

jq -n 'reduce inputs as $i ({}; . * $i) | walk(if type == "object" then with_entries(select(.key | test("^__") | not)) else . end)' $(find $TMP_INST -type f) >build/instruments-def.json
rm -Rf $TMP_INST

# Assembling per-plugin configuration into one file
PLUGINS_CONFIG_FILES=()
while IFS= read -r -d '' file; do
    PLUGINS_CONFIG_FILES+=("$file")
done < <(find ./src -type f -name "*-config.json" -print0)
CONFIG_TEMPLATE_FILE="conf/config-template.json"
CONFIG_TEMPLATE="$(jq '.[]' $CONFIG_TEMPLATE_FILE)"

merged_sections=$(jq -s '
    reduce .[] as $item ({}; 
        .PLUGINS += $item.PLUGINS // {} |
        .OTEL += $item.OTEL // {} 
    )' "${PLUGINS_CONFIG_FILES[@]}")

# Combine the merged sections with the rest of the template
jq --argjson sections "$merged_sections" '
    .PLUGINS = (.PLUGINS + $sections.PLUGINS) |
    .OTEL = (.OTEL + $sections.OTEL)
' <<<"$CONFIG_TEMPLATE" >./build/config-default.json

# Building SQL files in build
find src -type f \( -name "*.sql" ! -name "*.off.sql" \) | while IFS= read -r sql_file; do
    echo "Processing $sql_file"
    dest_file="build/$(basename $sql_file)" # Add your processing logic here
    gawk 'match($0, /[#]{2}INSERT (.+)/, a) {system("cat src/"a[1]); next } 1' $sql_file >$dest_file
done

echo "Building Dynatrace Snowflake Observability Agent done"

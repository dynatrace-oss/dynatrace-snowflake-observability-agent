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
# This script is used to build target SQLs that will be put into ../agent/sql/setup
# It processes the scripts in src/sql and looks for ##INSERT $fileName hints
#

set -e

# Check for required commands
if ! command -v gawk &> /dev/null; then
    echo "Error: Required command 'gawk' is not installed."
    exit 1
fi

if ! command -v yq &> /dev/null; then
    echo "Error: Required command 'yq' is not installed."
    exit 1
fi

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

SRC_IGNORED_CASES=$(grep '^disable=' .pylintrc | sed 's/disable=//')
TEST_IGNORED_CASES=$(grep '^disable=' test/.pylintrc | sed 's/disable=//')

pylint src/ --recursive=y --disable=$SRC_IGNORED_CASES --output-format=parseable >$SOURCE_CODE_QUALITY_CHECK_FILE
pylint test/ --recursive=y --disable=$TEST_IGNORED_CASES --output-format=parseable >$TEST_CODE_QUALITY_CHECK_FILE

if (
    [ -s "$SOURCE_CODE_QUALITY_CHECK_FILE" ] && ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" \
) || (
    [ -s "$TEST_CODE_QUALITY_CHECK_FILE" ] && ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE" \
); then
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
./scripts/dev/compile.sh

if [ $? -eq 1 ]; then
    exit 1
fi

# Assembling per-plugin configuration into one file
PLUGINS_CONFIG_FILES=()
while IFS= read -r -d '' file; do
    PLUGINS_CONFIG_FILES+=("$file")
done < <(find ./src -type f -name "*-config.yml" -print0)
CONFIG_TEMPLATE_FILE="conf/config-template.yml"
CONFIG_TEMPLATE="$(yq '.' $CONFIG_TEMPLATE_FILE)"

merged_sections="{}"
for file in "${PLUGINS_CONFIG_FILES[@]}"; do
    merged_sections=$(yq '.plugins = (.plugins // {}) + load("'$file'").plugins | .otel = (.otel // {}) + load("'$file'").otel' <<<"$merged_sections")
done

# Combine the merged sections with the rest of the template
echo "$merged_sections" > /tmp/merged.yml
yq '.plugins = (.plugins // {}) + load("/tmp/merged.yml").plugins | .otel = (.otel // {}) + load("/tmp/merged.yml").otel' "$CONFIG_TEMPLATE_FILE" >./build/config-default.yml
rm /tmp/merged.yml

# Building SQL files in build
find src -type f \( -name "*.sql" ! -name "*.off.sql" \) | while IFS= read -r sql_file; do
    echo "Processing $sql_file"
    dest_file="build/$(basename $sql_file)" # Add your processing logic here
    gawk 'match($0, /[#]{2}INSERT (.+)/, a) {system("cat src/"a[1]); next } 1' $sql_file >$dest_file
done

echo "Building Dynatrace Snowflake Observability Agent done"

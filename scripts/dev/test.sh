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

# Generate NDJSON fixtures from live Snowflake and run plugin tests.
#
# Usage:
#   ./test.sh <test_name>          Run plugin tests (uses existing NDJSON fixtures)
#   ./test.sh <test_name> -p       Regenerate NDJSON fixtures from Snowflake, then run tests
#   ./test.sh -a -p                Regenerate fixtures for ALL plugins, then run all tests
#   ./test.sh <test_name> "" -n    Skip code-quality checks

TEST_NAME=$1
TO_PICKLE=$2
RUN_QUALITY_CHECK=$3

TEST_FILE_PYTHON_PATH="test.plugins.$TEST_NAME"
TEST_FILE_PATH="test/plugins/$TEST_NAME.py"

PLUGIN_NAME=$(echo "$TEST_NAME" | sed 's/test_//g')
PLUGIN_FILE="src/dtagent/plugins/$PLUGIN_NAME.py"

SRC_IGNORED_CASES=$(grep '^disable=' .pylintrc | sed 's/disable=//')
TEST_IGNORED_CASES=$(grep '^disable=' test/.pylintrc | sed 's/disable=//')

# make sure to pass src/... as $1 and test/... as $2
code_quality_checks() {
    # condition is to not make jenkins run code quality tests again after running them for src/ and test/ in build.sh
    # code quality checks here are with the intent to give code quality feedback while running test locally during development
    if [ "$RUN_QUALITY_CHECK" != "-n" ]; then
        SOURCE_CODE_QUALITY_CHECK_FILE=.logs/source-$TEST_NAME-quality-$(date '+%Y%m%d-%H%M%S').log
        TEST_CODE_QUALITY_CHECK_FILE=.logs/test-$TEST_NAME-quality-$(date '+%Y%m%d-%H%M%S').log

        echo "Running code quality check for $1"
        # descriptions of disabled test cases are available in build.sh

        pylint "$1" --disable=$SRC_IGNORED_CASES --output-format=parseable > $SOURCE_CODE_QUALITY_CHECK_FILE

        echo "Running code quality check for $2"
        pylint "$2" --disable=$TEST_IGNORED_CASES --output-format=parseable > $TEST_CODE_QUALITY_CHECK_FILE

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

            echo "No code quality issues found in $1 and $2"
        fi
    fi
}

if [ "$TO_PICKLE" == "-p" ]; then

    if [ "$TEST_NAME" == "-a" ]; then
        code_quality_checks src/dtagent/plugins test/plugins

        echo "Generating NDJSON fixtures for all plugin tests"

        for file in test/plugins/test_*; do
            TEST_NAME=$(basename "${file%.*}")
            TEST_FILE_PYTHON_PATH="test.plugins.${TEST_NAME}"

            echo "Generating fixtures for ${TEST_NAME}"
            PYTHONPATH="$PYTHONPATH:./src" python -m $TEST_FILE_PYTHON_PATH $TO_PICKLE
        done

        echo "Running all plugin tests"
        pytest -s -v test/plugins/

    else
        code_quality_checks $PLUGIN_FILE $TEST_FILE_PATH

        echo "Generating NDJSON fixtures for ${TEST_NAME}."
        PYTHONPATH="$PYTHONPATH:./src" python -m $TEST_FILE_PYTHON_PATH $TO_PICKLE

        echo "Running tests for ${TEST_NAME}."
        pytest -s -v "$TEST_FILE_PATH"
    fi
else
    code_quality_checks $PLUGIN_FILE $TEST_FILE_PATH

    echo "Executing tests for ${TEST_NAME}."
    pytest -s -v "$TEST_FILE_PATH"
fi


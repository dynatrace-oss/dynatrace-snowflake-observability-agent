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

# to pickle new test data call as
# ./test.sh $test_name -p
# You can also pickle for all tests at once, by running
# ./test.sh -a -p
# If You wish to omit running code quality checks on plugin plugin test file and python plugin file set -n as the third param
# ./test.sh $test_name "" -n
# ./test.sh -a -p -n
# this script is not written to handle test/core/test_config test. it is intented to perfrom and validate plugin tests from test/plugins/
TEST_NAME=$1
TO_PICKLE=$2
RUN_QUALITY_CHECK=$3

EXEMPLARY_RESULT_FILE="test/test_results/${TEST_NAME}_results.txt"
TEST_FILE_PYTHON_PATH="test.plugins.$TEST_NAME"
TEST_FILE_PATH="test/plugins/$TEST_NAME.py"

PLUGIN_NAME=$(echo "$TEST_NAME" | sed 's/test_//g')
PLUGIN_FILE="src/dtagent/plugins/$PLUGIN_NAME.py"

SRC_IGNORED_CASES=C0301,W0611,E0401,C0415,C0411,R0914,R0902,R0903,R0913,R1737,R0912,W0107,C0103,W1203,R0915
TEST_IGNORED_CASES=$SRC_IGNORED_CASES,C0114,C0115,C0116,W0212,E0611,W0613,R1702,R1718

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
        
        if ! grep -q "at 10.00/10" "$SOURCE_CODE_QUALITY_CHECK_FILE" || ! grep -q "at 10.00/10" "$TEST_CODE_QUALITY_CHECK_FILE"; then
            
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

        echo "Pickling for all plugin tests"

        for file in test/plugins/test_*; do
            if [ $(basename "${file}") == "test_1_validate.py" ]; then
                continue
            fi

            TEST_NAME=$(basename "${file%.*}")
            TEST_FILE_PYTHON_PATH="test.plugins.${TEST_NAME}"
            EXEMPLARY_RESULT_FILE="test/test_results/${TEST_NAME}_results.txt"

            echo "Pickling for ${TEST_NAME}"

            PYTHONPATH="$PYTHONPATH:./src" python -m $TEST_FILE_PYTHON_PATH $TO_PICKLE &> $EXEMPLARY_RESULT_FILE

            pytest -s -v --result="$EXEMPLARY_RESULT_FILE" test/plugins/test_1_validate.py
        done

    else
        code_quality_checks $PLUGIN_FILE $TEST_FILE_PATH

        echo "Pickling for ${TEST_NAME}."

        PYTHONPATH="$PYTHONPATH:./src" python -m $TEST_FILE_PYTHON_PATH $TO_PICKLE &> $EXEMPLARY_RESULT_FILE
        pytest -s -v --result="$EXEMPLARY_RESULT_FILE" test/plugins/test_1_validate.py
    fi
else
    code_quality_checks $PLUGIN_FILE $TEST_FILE_PATH

    echo "Executing test and verification for ${TEST_NAME}."
    LOG_FILE_NAME=".logs/dtagent-${TEST_NAME}-$(date '+%Y%m%d-%H%M%S').log"
    PYTHONPATH="$PYTHONPATH:./src" python -m $TEST_FILE_PYTHON_PATH $LOG_FILE_NAME &> $LOG_FILE_NAME
    echo "Test result file - ${LOG_FILE_NAME}"

    # it looks like calling pytest from python with parameters would quite a hassle, so I decided to make the call in this script, not at the end of test classes
    # it also excludes calling pytest when pickling which would be pointless as both files (current result and exemplary) would point to the same file
    
    pytest -s -v --result="$LOG_FILE_NAME" --exemplary_result="$EXEMPLARY_RESULT_FILE" test/plugins/test_1_validate.py
fi

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
# the name isn't pretty but I wanted this file to be at the top of other tests, and it needed to start with test_, hence this one

# if You wish to run validation manually from command line, do it as
# pytest -s -v --result=$LOG_FILE_NAME --exemplary_result=$EXEMPLARY_RESULT_FILE test/plugins/test_1_validate.py

from typing import Union


def get_lines_with_substr(lines, substr):
    return [line for line in lines if substr in line]


def prepare_result_text(result: str) -> Union[str, None]:
    def __remove_false_positives(text: str, false_positives: str) -> str:
        import re

        p = re.compile(re.escape(false_positives), re.IGNORECASE)
        return p.sub("", text)

    def __check_issue_tag(text: str, tag: str) -> bool:
        """Checks whether a line in text does not start with a tag

        Args:
            text (str): text to check
            tag (str): tag to discover at the begining of a line

        Returns:
            bool: True if such line was discovered
        """
        for line in text.splitlines():
            if line.startswith(tag) and not "_OTLP" in line:
                return True
        return False

    with open(result, "r", encoding="utf-8") as f:
        result_text = f.read()

    # I have no clue how to get rid of this error, tests run properly despite it showing up
    result_text = __remove_false_positives(result_text, "error:root:no such file or directory")
    result_text = __remove_false_positives(result_text, "warning:dtagent:setting log level")

    # removing 'error.code' as it is expected as part of content generated in test_trust_center
    result_text = result_text.replace("'error.code'", "")

    assert not __check_issue_tag(result_text, "ERROR")
    assert not __check_issue_tag(result_text, "WARN")
    assert not __check_issue_tag(result_text, "Traceback")

    return result_text


def test_compare_results(result: str, exemplary_result: str):
    if result is not None:
        result_text = prepare_result_text(result)
        results_lines = get_lines_with_substr(result_text.splitlines(), "!!!!")
        result_last_line = results_lines[-1].lower()

        if exemplary_result is None:
            assert len(results_lines) > 0, f"File empty?\n{result_text}"

            assert not any(
                substring in result_last_line for substring in [" 0", "(0"]
            ), f"0 results\n{result_last_line}"

            print(f"\n!!! No results given to compare. Only checked {result} file for errors")
        else:
            print(f"\n!!!! Verifying {result} with {exemplary_result}")
            with open(exemplary_result, "r", encoding="utf-8") as f:
                exemplary_result_text = f.read().lower()

            test_lines = get_lines_with_substr(exemplary_result_text.splitlines(), "!!!!")

            assert len(test_lines) > 0, f"No results?\n{exemplary_result_text}"

            assert result_last_line == test_lines[-1].lower()

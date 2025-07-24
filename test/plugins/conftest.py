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
from pytest import fixture


def pytest_addoption(parser):
    parser.addoption(
        "--result",
        action="store",
        help="File name of the test result file.",
    )
    parser.addoption(
        "--exemplary_result",
        action="store",
        help="File name of the test exemplary result file.",
    )


@fixture(scope="session")
def result(request):
    return request.config.getoption("--result")


@fixture(scope="session")
def exemplary_result(request):
    return request.config.getoption("--exemplary_result")

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
        "--pickle_conf",
        action="store",
        help="Indicator if we want to download new config from Snowflake.",
    )


@fixture(scope="session")
def pickle_conf(request):
    return request.config.getoption("--pickle_conf")

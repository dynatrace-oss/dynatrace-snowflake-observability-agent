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
import json
import os
from typing import Any, Dict
from dtagent.agent import DynatraceSnowAgent
from dtagent.config import Configuration
from snowflake import snowpark

from _snowflake import read_secret

read_secret(
    secret_name="dtagent_token",
    from_field="_DTAGENT_API_KEY",
    from_file="conf/config-test.json",
    env_name="DTAGENT_TOKEN",
)


def _get_creds() -> Dict:
    """
    {
        "account": "<your snowflake account>",
        "user": "<your snowflake user>",
        "password": "<your snowflake password>",
        "role": "<your snowflake role>",  # Optional
        "warehouse": "<your snowflake warehouse>",  # Optional
        "database": "<your snowflake database>",  # Optional
        "schema": "<your snowflake schema>"  # Optional
    }
    """
    credentials = {}
    creds_path = "test/credentials.json"
    if os.path.isfile(creds_path):
        with open(creds_path, "r", encoding="utf-8") as f:
            credentials = json.loads(f.read())
    else:
        basic_creds_file = ".ci/test-creds.json"
        # this distinction is made to avoid loading files with tokens to jenkins pipeline, when running script locally it is recommended to create apropriate credentials file
        with open(basic_creds_file, "r", encoding="utf-8") as basic_creds:
            credentials = json.loads(basic_creds.read())

        credentials["account"] = os.environ.get("SNOWFLAKE_ACC_NAME")
        credentials["user"] = os.environ.get("SNOWFLAKE_USER_NAME")
        credentials["password"] = os.environ.get("SNOWFLAKE_USER_PASSWORD")

        tag = os.environ.get("TEST_TAG", None)
        if tag is not None:
            for key in ["role", "warehouse", "database"]:
                underscore_pos = credentials[key].find("_")
                credentials[key] = credentials[key][: underscore_pos + 1] + tag + "_" + credentials[key][underscore_pos + 1 :]

    return credentials


def _get_session() -> snowpark.Session:
    # Import the Session class from the snowflake.snowpark package
    from snowflake.snowpark import Session

    creds = _get_creds()
    session = Session.builder.configs(creds).create()
    session.use_warehouse(creds.get("warehouse"))

    return session


class TestConfiguration(Configuration):

    def get_last_measurement_update(self, session: snowpark.Session, source: str):
        from dtagent.util import _get_timestamp_in_sec

        return _get_timestamp_in_sec()


class TestDynatraceSnowAgent(DynatraceSnowAgent):

    def _get_config(self, session: snowpark.Session) -> Configuration:
        return _overwrite_plugin_local_config_key(
            TestConfiguration(session),
            "users",
            "roles_monitoring_mode",
            ["DIRECT_ROLES", "ALL_ROLES", "ALL_PRIVILEGES"],
        )


def _overwrite_plugin_local_config_key(test_conf: TestConfiguration, plugin_name: str, key_name: str, new_value: Any):
    # added to make sure we always run tests for each mode in users plugin
    test_conf._config["plugins"][plugin_name][key_name] = new_value
    return test_conf

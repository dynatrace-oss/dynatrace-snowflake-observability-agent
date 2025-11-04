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
from contextlib import contextmanager
import re
from typing import Any, Dict, List
import functools
import datetime
from unittest.mock import patch, Mock

from snowflake import snowpark

from _snowflake import read_secret
from dtagent.agent import DynatraceSnowAgent
from dtagent.config import Configuration

read_secret(
    secret_name="dtagent_token",
    from_field="_DTAGENT_API_KEY",
    from_file="conf/config-test.json",
    env_name="DTAGENT_TOKEN",
)


@functools.lru_cache(maxsize=1)
def _get_credentials() -> Dict:
    """
    {
        "account": "<your snowflake account>",
        "user": "<your snowflake user>",
        "password": "<your snowflake password>",
        "role": "<your snowflake role>",  # Optional
        "warehouse": "<your snowflake warehouse>",  # Optional
        "schema": "<your snowflake schema>"  # Optional
    }
    """
    credentials = {}
    credentials_path = "test/credentials.json"
    if os.path.isfile(credentials_path):
        with open(credentials_path, "r", encoding="utf-8") as f:
            credentials = json.loads(f.read())

    return credentials or {"local_testing": True}


def is_local_testing() -> bool:
    return _get_credentials().get("local_testing", False)


def _get_session() -> snowpark.Session:
    # Import the Session class from the snowflake.snowpark package
    from snowflake.snowpark import Session

    credentials = _get_credentials()
    session = Session.builder.configs(credentials).create()
    if "warehouse" in credentials:
        session.use_warehouse(credentials["warehouse"])

    return session


class TestConfiguration(Configuration):

    def get_last_measurement_update(self, session: snowpark.Session, source: str):
        from dtagent.util import _get_timestamp_in_sec

        return _get_timestamp_in_sec()


class TestDynatraceSnowAgent(DynatraceSnowAgent):

    def __init__(self, session: snowpark.Session, config: Configuration) -> None:
        self._local_configuration = config
        self._local_configuration._config["otel"]["spans"]["max_export_batch_size"] = 1
        self._local_configuration._config["otel"]["logs"]["max_export_batch_size"] = 1
        super().__init__(session)

    def _get_config(self, session: snowpark.Session) -> Configuration:
        return _overwrite_plugin_local_config_key(
            self._local_configuration,
            "users",
            "roles_monitoring_mode",
            ["DIRECT_ROLES", "ALL_ROLES", "ALL_PRIVILEGES"],
        )

    def process(
        self,
        sources: List,
        run_proc: bool = True,
        disabled_telemetry: List[str] = None,
    ) -> Dict:
        from dtagent.otel.otel_manager import OtelManager
        from test._mocks.telemetry import MockTelemetryClient

        process_results = {}

        OtelManager.reset_current_fail_count()

        if is_local_testing():
            mock_client = MockTelemetryClient(sources[0] if sources else None)
            with mock_client.mock_telemetry_sending():
                import time

                process_results = super().process(sources, run_proc)
                self._logs.flush_logs()
                self._spans.flush_traces()
                time.sleep(1)
            mock_client.store_or_test_results(disabled_telemetry=disabled_telemetry)
        else:
            process_results = super().process(sources, run_proc)

        return process_results

    def teardown(self) -> None:
        self._logs.flush_logs()
        self._spans.flush_traces()


def _overwrite_plugin_local_config_key(test_conf: TestConfiguration, plugin_name: str, key_name: str, new_value: Any):
    # added to make sure we always run tests for each mode in users plugin
    test_conf._config["plugins"][plugin_name][key_name] = new_value
    return test_conf

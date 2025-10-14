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
from typing import Any, Dict, List

from snowflake import snowpark

from _snowflake import read_secret
from dtagent.agent import DynatraceSnowAgent
from dtagent.config import Configuration
from dtagent.otel.events.generic import GenericEvents

read_secret(
    secret_name="dtagent_token",
    from_field="_DTAGENT_API_KEY",
    from_file="conf/config-test.json",
    env_name="DTAGENT_TOKEN",
)


def _get_credentials() -> Dict:
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
    credentials_path = "test/credentials.json"
    if os.path.isfile(credentials_path):
        with open(credentials_path, "r", encoding="utf-8") as f:
            credentials = json.loads(f.read())
    return credentials or {"local_testing": True}


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
    from unittest.mock import patch

    def __init__(self, session: snowpark.Session, config: Configuration) -> None:
        self._local_configuration = config
        super().__init__(session)

    def _get_config(self, session: snowpark.Session) -> Configuration:
        return _overwrite_plugin_local_config_key(
            self._local_configuration,
            "users",
            "roles_monitoring_mode",
            ["DIRECT_ROLES", "ALL_ROLES", "ALL_PRIVILEGES"],
        )

    @patch("dtagent.otel.otel_manager.CustomLoggingSession.send")
    @patch("dtagent.otel.metrics.requests.post")
    @patch("dtagent.otel.events.davis.requests.post")
    @patch("dtagent.otel.events.bizevents.requests.post")
    def process(
        self,
        sources: List,
        run_proc: bool = True,
        mock_bizevents_post=None,
        mock_events_post=None,
        mock_metrics_post=None,
        mock_otel_post=None,
    ) -> Dict:
        from dtagent.otel.otel_manager import OtelManager

        # FIXME we need to detect if we run the test against real endpoint or mock
        OtelManager.reset_current_fail_count()
        mock_events_post.side_effect = side_effect_function
        mock_bizevents_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function
        return super().process(sources, run_proc)


def _overwrite_plugin_local_config_key(test_conf: TestConfiguration, plugin_name: str, key_name: str, new_value: Any):
    # added to make sure we always run tests for each mode in users plugin
    test_conf._config["plugins"][plugin_name][key_name] = new_value
    return test_conf


def side_effect_function(*args, **kwargs):
    from unittest.mock import MagicMock
    from dtagent.otel.events.bizevents import BizEvents
    from dtagent.otel.events.davis import DavisEvents
    from dtagent.otel.logs import Logs
    from dtagent.otel.metrics import Metrics
    from dtagent.otel.spans import Spans

    mock_response = MagicMock()

    request_url = args[0].url if hasattr(args[0], "url") else str(args[0])

    mock_response.status_code = 500

    if (
        request_url.endswith(BizEvents.ENDPOINT_PATH)
        or request_url.endswith(GenericEvents.ENDPOINT_PATH)
        or request_url.endswith(Metrics.ENDPOINT_PATH)
    ):  # For BizEvents, OpenPipeline Events, and Metrics
        mock_response.status_code = 202

    if request_url.endswith(DavisEvents.ENDPOINT_PATH):  # For events
        mock_response.status_code = 201

    if request_url.endswith(Logs.ENDPOINT_PATH) or request_url.endswith(Spans.ENDPOINT_PATH):  # For logs and spans
        mock_response.status_code = 200

    return mock_response

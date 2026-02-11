#!/usr/bin/env python3
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
import uuid
import logging
from unittest.mock import patch

from dtagent import context
from dtagent.util import get_now_timestamp, get_now_timestamp_formatted
from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY
from test import _get_session, _utils
from test._utils import LocalTelemetrySender, read_clean_data_from_file, telemetry_test_sender
from test._mocks.telemetry import MockTelemetryClient
from snowflake import snowpark

LOG = logging.getLogger("DTAGENT_TEST")
LOG.setLevel(logging.DEBUG)


class TestTelemetrySender:
    """Testing TelemetrySender:

    * sending all data from a given (standard structure) view
    * sending data from a given (standard structure) view, excluding metrics
    * sending data from a given (standard structure) view, excluding events
    * sending data from a given (standard structure) view, excluding logs
    * sending all data from a given (standard structure) object
    * sending all data from a given (standard structure) list of objects
    * sending data from a given (standard structure) list of objects, excluding metrics
    * sending data from a given (standard structure) list of objects, excluding events
    * sending data from a given (standard structure) list of objects, excluding logs
    * sending all data from a given (custom structure) view as logs
    * sending all data from a given (custom structure) view as events
    * sending all data from a given (custom structure) view as bizevents
    * sending all data from a given (custom structure) view as logs, events, and bizevents
    """

    import pytest

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_viewsend(self):  # ):
        import random

        rows_cnt = random.randint(10, 20)

        session = _get_session()
        context_name = "test_viewsend"
        results = telemetry_test_sender(
            session,
            "APP.V_EVENT_LOG",
            {"auto_mode": False, "context": context_name, "logs": True, "events": True, "bizevents": True, "davis_events": True},
            limit_results=rows_cnt,
            config=_utils.get_config(),
        )

        assert RUN_RESULTS_KEY in results
        assert context_name in results[RUN_RESULTS_KEY]
        assert RUN_ID_KEY in results
        assert results[RUN_RESULTS_KEY][context_name]["entries"] == rows_cnt  # all
        assert results[RUN_RESULTS_KEY][context_name]["log_lines"] == rows_cnt  # logs
        assert results[RUN_RESULTS_KEY][context_name]["events"] == rows_cnt  # events
        assert results[RUN_RESULTS_KEY][context_name]["biz_events"] == rows_cnt  # biz_events
        assert results[RUN_RESULTS_KEY][context_name]["davis_events"] == rows_cnt  # davis_events

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_large_view_send_as_be(self):
        import random

        rows_cnt = random.randint(410, 500)

        LOG.debug("We will send %s rows as BizEvents", rows_cnt)

        session = _get_session()
        context_name = "test_large_view_send_as_be"
        results = telemetry_test_sender(
            session,
            "APP.V_EVENT_LOG",
            {"auto_mode": False, "context": context_name, "logs": False, "events": False, "bizevents": True},
            limit_results=rows_cnt,
            config=_utils.get_config(),
            test_source=None,  # we don to record tests with variable data size
        )

        assert RUN_RESULTS_KEY in results
        assert context_name in results[RUN_RESULTS_KEY]

        LOG.debug("We have sent %d rows as BizEvents", results[RUN_RESULTS_KEY][context_name]["biz_events"])

        assert RUN_ID_KEY in results
        assert results[RUN_RESULTS_KEY][context_name]["entries"] == rows_cnt  # all
        assert results[RUN_RESULTS_KEY][context_name]["log_lines"] == 0  # logs
        assert results[RUN_RESULTS_KEY][context_name]["events"] == 0  # events
        assert results[RUN_RESULTS_KEY][context_name]["biz_events"] == rows_cnt  # bizevents
        assert results[RUN_RESULTS_KEY][context_name]["davis_events"] == 0  # davis_events

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_connector_bizevents(self):
        session = _get_session()

        sender = LocalTelemetrySender(
            session,
            {"auto_mode": False, "logs": False, "events": False, "bizevents": True},
            config=_utils.get_config(),
            exec_id=str(uuid.uuid4().hex),
        )
        data = [
            {
                "event.provider": str(sender._configuration.get(context="resource.attributes", key="host.name")),
                "dsoa.task.exec.id": get_now_timestamp_formatted(),
                "dsoa.task.name": "test_events",
                "dsoa.task.exec.status": "FINISHED",
            }
        ]
        context_name = "telemetry_sender"
        mock_client = MockTelemetryClient("test_connector_bizevents")
        with mock_client.mock_telemetry_sending():
            results = sender.send_data(data)
            sender._logs.shutdown_logger()
            sender._spans.shutdown_tracer()
        mock_client.store_or_test_results()

        assert RUN_RESULTS_KEY in results
        assert context_name in results[RUN_RESULTS_KEY]
        assert RUN_ID_KEY in results
        assert results[RUN_RESULTS_KEY][context_name]["biz_events"] == 1

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_automode(self):
        session = _get_session()

        structured_test_data = read_clean_data_from_file("test/test_data/telemetry_structured.json")
        unstructured_test_data = read_clean_data_from_file("test/test_data/telemetry_unstructured.json")

        # Results are (Count of objects, log lines, metrics, events, bizevents, and davis events sent)

        # sending all data from a given (standard structure) view
        assert telemetry_test_sender(
            session,
            "APP.V_DATA_VOLUME",
            {"context": "test_automode/000"},
            config=_utils.get_config(),
            test_source="test_automode/000",
        )[RUN_RESULTS_KEY]["test_automode/000"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 7,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding metrics
        assert telemetry_test_sender(
            session,
            "APP.V_DATA_VOLUME",
            {"context": "test_automode/001", "metrics": False},
            config=_utils.get_config(),
            test_source="test_automode/001",
        )[RUN_RESULTS_KEY]["test_automode/001"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 0,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding events
        assert telemetry_test_sender(
            session,
            "APP.V_DATA_VOLUME",
            {"context": "test_automode/002", "events": False},
            config=_utils.get_config(),
            test_source="test_automode/002",
        )[RUN_RESULTS_KEY]["test_automode/002"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 7,
            "events": 0,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding logs
        assert telemetry_test_sender(
            session,
            "APP.V_DATA_VOLUME",
            {"context": "test_automode/003", "logs": False},
            config=_utils.get_config(),
            test_source="test_automode/003",
        )[RUN_RESULTS_KEY]["test_automode/003"] == {
            "entries": 2,
            "log_lines": 0,
            "metrics": 7,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }

        # sending all data from a given (standard structure) object
        assert telemetry_test_sender(
            session,
            structured_test_data[0],
            {"context": "test_automode/004"},
            config=_utils.get_config(),
            test_source="test_automode/004",
        )[RUN_RESULTS_KEY]["test_automode/004"] == {
            "entries": 1,
            "log_lines": 1,
            "metrics": 4,
            "events": 2,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending all data from a given (standard structure) view
        assert telemetry_test_sender(
            session,
            structured_test_data,
            {"context": "test_automode/005"},
            config=_utils.get_config(),
            test_source="test_automode/005",
        )[RUN_RESULTS_KEY]["test_automode/005"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 7,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding metrics
        assert telemetry_test_sender(
            session,
            structured_test_data,
            {"context": "test_automode/006", "metrics": False},
            config=_utils.get_config(),
            test_source="test_automode/006",
        )[RUN_RESULTS_KEY]["test_automode/006"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 0,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding events
        assert telemetry_test_sender(
            session,
            structured_test_data,
            {"context": "test_automode/007", "events": False},
            config=_utils.get_config(),
            test_source="test_automode/007",
        )[RUN_RESULTS_KEY]["test_automode/007"] == {
            "entries": 2,
            "log_lines": 2,
            "metrics": 7,
            "events": 0,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending data from a given (standard structure) view, excluding logs
        assert telemetry_test_sender(
            session,
            structured_test_data,
            {"context": "test_automode/008", "logs": False},
            config=_utils.get_config(),
            test_source="test_automode/008",
        )[RUN_RESULTS_KEY]["test_automode/008"] == {
            "entries": 2,
            "log_lines": 0,
            "metrics": 7,
            "events": 3,
            "biz_events": 0,
            "davis_events": 0,
        }

        # sending all data from a given (custom structure) view as logs
        assert telemetry_test_sender(
            session,
            unstructured_test_data,
            {"context": "test_automode/009", "auto_mode": False},
            config=_utils.get_config(),
            test_source="test_automode/009",
        )[RUN_RESULTS_KEY]["test_automode/009"] == {
            "entries": 3,
            "log_lines": 3,
            "metrics": 0,
            "events": 0,
            "biz_events": 0,
            "davis_events": 0,
        }
        # sending all data from a given (custom structure) view as events
        assert telemetry_test_sender(
            session,
            unstructured_test_data,
            {"context": "test_automode/010", "auto_mode": False, "logs": False, "events": True, "davis_events": True},
            config=_utils.get_config(),
            test_source="test_automode/010",
        )[RUN_RESULTS_KEY]["test_automode/010"] == {
            "entries": 3,
            "log_lines": 0,
            "metrics": 0,
            "events": 3,
            "biz_events": 0,
            "davis_events": 3,
        }
        # sending all data from a given (custom structure) view as bizevents
        assert telemetry_test_sender(
            session,
            unstructured_test_data,
            {"context": "test_automode/011", "auto_mode": False, "logs": False, "bizevents": True},
            config=_utils.get_config(),
            test_source="test_automode/011",
        )[RUN_RESULTS_KEY]["test_automode/011"] == {
            "entries": 3,
            "log_lines": 0,
            "metrics": 0,
            "events": 0,
            "biz_events": 3,
            "davis_events": 0,
        }
        # sending all data from a given (custom structure) view as logs, events, and bizevents
        assert telemetry_test_sender(
            session,
            unstructured_test_data,
            {"context": "test_automode/012", "auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
            test_source="test_automode/012",
        )[RUN_RESULTS_KEY]["test_automode/012"] == {
            "entries": 3,
            "log_lines": 3,
            "metrics": 0,
            "events": 3,
            "biz_events": 3,
            "davis_events": 0,
        }
        # sending single data point from a given (custom structure) view as logs, events, and bizevents
        assert telemetry_test_sender(
            session,
            unstructured_test_data[0],
            {"context": "test_automode/013", "auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
            test_source="test_automode/013",
        )[RUN_RESULTS_KEY]["test_automode/013"] == {
            "entries": 1,
            "log_lines": 1,
            "metrics": 0,
            "events": 1,
            "biz_events": 1,
            "davis_events": 0,
        }
        # sending single data point from a given (custom structure) with datetime objects view as logs, events, and bizevents
        assert telemetry_test_sender(
            session,
            unstructured_test_data[0] | {"observed_at": get_now_timestamp()},
            {"context": "test_automode/014", "auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
            test_source="test_automode/014",
        )[RUN_RESULTS_KEY]["test_automode/014"] == {
            "entries": 1,
            "log_lines": 1,
            "metrics": 0,
            "events": 1,
            "biz_events": 1,
            "davis_events": 0,
        }

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

import logging
from unittest.mock import patch

from dtagent.util import get_now_timestamp, get_now_timestamp_formatted
from test import _get_credentials, _get_session
from test import _utils, side_effect_function
from test._utils import LocalTelemetrySender, read_clean_json_from_file, telemetry_test_sender
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

    @patch("dtagent.otel.otel_manager.CustomLoggingSession.send")
    @patch("dtagent.otel.metrics.requests.post")
    @patch("dtagent.otel.events.generic.requests.post")
    @patch("dtagent.otel.events.davis.requests.post")
    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_viewsend(self, mock_bizevents_post, mock_davis_post, mock_events_post, mock_metrics_post, mock_otel_post):
        import random

        rows_cnt = random.randint(10, 20)
        mock_davis_post.side_effect = side_effect_function
        mock_events_post.side_effect = side_effect_function
        mock_bizevents_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function

        session = _get_session()
        results = telemetry_test_sender(
            session,
            "APP.V_EVENT_LOG",
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True, "davis_events": True},
            limit_results=rows_cnt,
            config=_utils.get_config(),
        )

        assert results[0] == rows_cnt  # all
        assert results[1] == rows_cnt  # logs
        assert results[-3] == rows_cnt  # events
        assert results[-2] == rows_cnt  # biz_events
        assert results[-1] == rows_cnt  # davis_events

    @patch("dtagent.otel.otel_manager.CustomLoggingSession.send")
    @patch("dtagent.otel.metrics.requests.post")
    @patch("dtagent.otel.events.generic.requests.post")
    @patch("dtagent.otel.events.davis.requests.post")
    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_large_view_send_as_be(self, mock_bizevents_post, mock_davis_post, mock_events_post, mock_metrics_post, mock_otel_post):
        import random

        rows_cnt = random.randint(410, 500)
        mock_davis_post.side_effect = side_effect_function
        mock_events_post.side_effect = side_effect_function
        mock_bizevents_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function

        LOG.debug("We will send %s rows as BizEvents", rows_cnt)

        session = _get_session()
        results = telemetry_test_sender(
            session,
            "APP.V_EVENT_LOG",
            {"auto_mode": False, "logs": False, "events": False, "bizevents": True},
            limit_results=rows_cnt,
            config=_utils.get_config(),
        )

        LOG.debug("We have sent %d rows as BizEvents", results[-1])

        assert results[0] == rows_cnt  # all
        assert results[1] == 0  # logs
        assert results[-3] == 0  # events
        assert results[-2] == rows_cnt  # bizevents
        assert results[-1] == 0  # bizevents

    @patch("dtagent.otel.otel_manager.CustomLoggingSession.send")
    @patch("dtagent.otel.metrics.requests.post")
    @patch("dtagent.otel.events.generic.requests.post")
    @patch("dtagent.otel.events.davis.requests.post")
    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_dtagent_bizevents(self, mock_bizevents_post, mock_davis_post, mock_events_post, mock_metrics_post, mock_otel_post):
        mock_davis_post.side_effect = side_effect_function
        mock_events_post.side_effect = side_effect_function
        mock_bizevents_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function
        session = _get_session()

        sender = LocalTelemetrySender(
            session,
            {"auto_mode": False, "logs": False, "events": False, "bizevents": True},
            config=_utils.get_config(),
        )
        results = sender.send_data(
            [
                {
                    "event.provider": str(sender._configuration.get(context="resource.attributes", key="host.name")),
                    "dsoa.task.exec.id": get_now_timestamp_formatted(),
                    "dsoa.task.name": "test_events",
                    "dsoa.task.exec.status": "FINISHED",
                }
            ]
        )
        sender.teardown()

        assert results[-2] == 1

    @patch("dtagent.otel.otel_manager.CustomLoggingSession.send")
    @patch("dtagent.otel.metrics.requests.post")
    @patch("dtagent.otel.events.generic.requests.post")
    @patch("dtagent.otel.events.davis.requests.post")
    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_automode(self, mock_bizevents_post, mock_davis_post, mock_events_post, mock_metrics_post, mock_otel_post):
        mock_davis_post.side_effect = side_effect_function
        mock_events_post.side_effect = side_effect_function
        mock_bizevents_post.side_effect = side_effect_function
        mock_metrics_post.side_effect = side_effect_function
        mock_otel_post.side_effect = side_effect_function
        session = _get_session()

        structured_test_data = read_clean_json_from_file("test/test_data/telemetry_structured.json")
        unstructured_test_data = read_clean_json_from_file("test/test_data/telemetry_unstructured.json")

        # sending all data from a given (standard structure) view
        assert (2, 2, 2, 3, 0, 0) == telemetry_test_sender(session, "APP.V_DATA_VOLUME", {}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding metrics
        assert (2, 2, 0, 3, 0, 0) == telemetry_test_sender(session, "APP.V_DATA_VOLUME", {"metrics": False}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding events
        assert (2, 2, 2, 0, 0, 0) == telemetry_test_sender(session, "APP.V_DATA_VOLUME", {"events": False}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding logs
        assert (2, 0, 2, 3, 0, 0) == telemetry_test_sender(session, "APP.V_DATA_VOLUME", {"logs": False}, config=_utils.get_config())

        # sending all data from a given (standard structure) object
        assert (1, 1, 1, 2, 0, 0) == telemetry_test_sender(session, structured_test_data[0], {}, config=_utils.get_config())
        # sending all data from a given (standard structure) view
        assert (2, 2, 2, 3, 0, 0) == telemetry_test_sender(session, structured_test_data, {}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding metrics
        assert (2, 2, 0, 3, 0, 0) == telemetry_test_sender(session, structured_test_data, {"metrics": False}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding events
        assert (2, 2, 2, 0, 0, 0) == telemetry_test_sender(session, structured_test_data, {"events": False}, config=_utils.get_config())
        # sending data from a given (standard structure) view, excluding logs
        assert (2, 0, 2, 3, 0, 0) == telemetry_test_sender(session, structured_test_data, {"logs": False}, config=_utils.get_config())

        # sending all data from a given (custom structure) view as logs
        assert (3, 3, 0, 0, 0, 0) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False}, config=_utils.get_config()
        )
        # sending all data from a given (custom structure) view as events
        assert (3, 0, 0, 3, 0, 0) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False, "logs": False, "events": True}, config=_utils.get_config()
        )
        # sending all data from a given (custom structure) view as bizevents
        assert (3, 0, 0, 0, 3, 0) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False, "logs": False, "bizevents": True}, config=_utils.get_config()
        )
        # sending all data from a given (custom structure) view as logs, events, and bizevents
        assert (3, 3, 0, 3, 3, 0) == telemetry_test_sender(
            session,
            unstructured_test_data,
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
        )
        # sending single data point from a given (custom structure) view as logs, events, and bizevents
        assert (1, 1, 0, 1, 1, 0) == telemetry_test_sender(
            session,
            unstructured_test_data[0],
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
        )
        # sending single data point from a given (custom structure) with datetime objects view as logs, events, and bizevents
        assert (1, 1, 0, 1, 1, 0) == telemetry_test_sender(
            session,
            unstructured_test_data[0] | {"observed_at": get_now_timestamp()},
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True},
            config=_utils.get_config(),
        )

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
from unittest.mock import patch

from dtagent.otel.events import EventType
from dtagent.context import get_context_by_name
from dtagent.util import get_now_timestamp, get_now_timestamp_formatted
from test import side_effect_function
from test._utils import get_config


class TestEvents:

    @classmethod
    def setup_class(cls):
        from test import _get_session, TestDynatraceSnowAgent

        cls._session = _get_session()
        cls._dtagent = TestDynatraceSnowAgent(cls._session, get_config())

    @classmethod
    def teardown_class(cls):
        cls._dtagent.teardown()
        cls._session.close()

    def test_eventtype_enum(self):
        t = EventType.CUSTOM_ALERT

        assert isinstance(t, EventType), "event type should be of EventType"
        assert str(t) == "CUSTOM_ALERT", "event type {t} should render in capital letters"

    @patch("dtagent.otel.events.davis.requests.post")
    def test_send_events_directly(self, mock_events_post):
        import time

        mock_events_post.side_effect = side_effect_function
        events = self._dtagent._get_davis_events()

        events_sent = events.send_events(
            events_data={},
            event_type=EventType.CUSTOM_INFO,
            title="Dynatrace Snowflake Observability Agent test event 1",
        )
        assert events_sent + events.flush_events() >= 0

        events_sent = events.send_events(
            # this will be reported as Availability problem
            events_data=[
                {
                    "test.event.dtagent.number": 10,
                    "test.event.dtagent.text": "some text",
                    "test.event.dtagent.bool": True,
                    "test.event.dtagent.list": [1, 2, 3],
                    "test.event.dtagent.dict": {"k1": "v1", "k2": 2},
                    "test.event.dtagent.datetime": get_now_timestamp(),
                }
            ],
            event_type=EventType.AVAILABILITY_EVENT,
            title="Dynatrace Snowflake Observability Agent test event 2",
            timeout=30,
        )
        assert events_sent + events.flush_events() >= 0

        events_sent = events.send_events(
            events_data=[
                {
                    "test.event.dtagent.info": "timeout",
                }
            ],
            event_type=EventType.CUSTOM_ANNOTATION,
            title="Dynatrace Snowflake Observability Agent test event 3",
            timeout=30,
        )
        assert events_sent + events.flush_events() >= 0

        current_time_ms = int(time.time() * 1000)
        ten_minutes_ago_ms = current_time_ms - (10 * 60 * 1000)
        fifteen_minutes_from_now_ms = current_time_ms + (15 * 60 * 1000)

        events_sent = events.send_events(
            # this will be reported as Custom problem
            events_data=[
                {
                    "test.event.dtagent.info": "10 min in the past",
                }
            ],
            event_type=EventType.CUSTOM_ALERT,
            title="Dynatrace Snowflake Observability Agent test event 4",
            start_time=ten_minutes_ago_ms,
            timeout=15,
        )
        assert events_sent + events.flush_events() >= 0

        events_sent = events.send_events(
            events_data=[
                {
                    "test.event.dtagent.info": "15 min in the future",
                }
            ],
            event_type=EventType.CUSTOM_DEPLOYMENT,
            title="Dynatrace Snowflake Observability Agent test event 5",
            end_time=fifteen_minutes_from_now_ms,
        )
        assert events_sent + events.flush_events() >= 0

        events_sent = events.send_events(
            events_data=[
                {
                    "test.event.dtagent.info": "15 min in the future",
                }
            ],
            event_type=EventType.CUSTOM_DEPLOYMENT,
            title="Dynatrace Snowflake Observability Agent test event 6",
            context=get_context_by_name("data_volume"),
            end_time=fifteen_minutes_from_now_ms,
        )
        assert events_sent + events.flush_events() >= 0

    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_send_bizevents_directly(self, mock_events_post):
        import time

        mock_events_post.side_effect = side_effect_function
        events = self._dtagent._get_biz_events()

        events_sent = events.send_events(
            [{"test.bizevent.message": "Dynatrace Snowflake Observability Agent test event 123", "test.ts": get_now_timestamp_formatted()}]
        )
        assert events_sent >= 0

        new_events_sent = events.send_events(
            [
                {
                    "test.event.dtagent.number": 10,
                    "test.event.dtagent.text": "some text",
                    "test.event.dtagent.bool": True,
                }
            ]
        )

        assert new_events_sent >= 0
        events_sent += new_events_sent

        current_time_ms = int(time.time() * 1000)
        ten_minutes_ago_ms = current_time_ms - (10 * 60 * 1000)
        fifteen_minutes_from_now_ms = current_time_ms + (15 * 60 * 1000)

        new_events_sent = events.send_events(
            [
                {"test.event.dtagent.info": "timeout", "event.type": str(EventType.CUSTOM_ANNOTATION)},
                {
                    "test.event.dtagent.info": "10 min in the past",
                    "test.event.dtagent.start_time": ten_minutes_ago_ms,
                },
                {
                    "test.event.dtagent.info": "15 min in the future",
                    "test.event.dtagent.start_time": ten_minutes_ago_ms,
                    "test.event.dtagent.end_time": fifteen_minutes_from_now_ms,
                    "test.event.dtagent.timeout": 15,
                },
            ]
        )
        assert new_events_sent >= 0
        events_sent += new_events_sent

        new_events_sent = events.flush_events()
        assert new_events_sent >= 0
        events_sent += new_events_sent

        assert events_sent == 5

    @patch("dtagent.otel.events.davis.requests.post")
    def test_send_results_as_events(self, mock_events_post):
        from test import _utils

        mock_events_post.side_effect = side_effect_function
        events = self._dtagent._get_davis_events()

        PICKLE_NAME = "test/test_data/data_volume.pkl"
        for row_dict in _utils._get_unpickled_entries(PICKLE_NAME, limit=2):

            events_sent = events.report_via_api(
                query_data=row_dict,
                event_type=EventType.CUSTOM_INFO,
                title="Test event for Data Volume",
            )
            assert events_sent + events.flush_events() > 0

    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_send_results_as_bizevents(self, mock_events_post):
        from test import _utils

        mock_events_post.side_effect = side_effect_function
        bizevents = self._dtagent._get_biz_events()

        PICKLE_NAME = "test/test_data/data_volume.pkl"

        events_sent = bizevents.report_via_api(
            query_data=_utils._get_unpickled_entries(PICKLE_NAME, limit=2),
            event_type=str(EventType.CUSTOM_INFO),
            context=get_context_by_name("data_volume"),
        )

        events_sent += bizevents.flush_events()

        assert events_sent == 2

    @patch("dtagent.otel.events.bizevents.requests.post")
    def test_dtagent_bizevents(self, mock_events_post):
        mock_events_post.side_effect = side_effect_function
        bizevents = self._dtagent._get_biz_events()

        cnt = bizevents.report_via_api(
            context=get_context_by_name("self-monitoring"),
            event_type="dsoa.task",
            query_data=[
                {
                    "event.provider": str(self._dtagent._configuration.get(context="resource.attributes", key="host.name")),
                    "dsoa.task.exec.id": get_now_timestamp_formatted(),
                    "dsoa.task.name": "test_events",
                    "dsoa.task.exec.status": "FINISHED",
                }
            ],
            is_data_structured=False,
        )

        cnt += bizevents.flush_events()

        assert cnt == 1

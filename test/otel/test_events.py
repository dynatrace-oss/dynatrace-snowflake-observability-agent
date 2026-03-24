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
from unittest.mock import patch

from dtagent.otel.events import EventType
from dtagent.context import get_context_name_and_run_id
from dtagent.util import get_now_timestamp, get_now_timestamp_formatted
from test._utils import get_config
from test._mocks.telemetry import MockTelemetryClient


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

    def test_send_events_directly(self):
        def _test_send_events_directly(test_mode="davis"):
            import time

            mock_client = MockTelemetryClient(f"test_send_{test_mode}_events_directly")
            with mock_client.mock_telemetry_sending():
                events = self._dtagent._get_davis_events() if test_mode == "davis" else self._dtagent._get_events()

                events_sent = events.send_events(
                    event_type=EventType.CUSTOM_INFO, title="Dynatrace Snowflake Observability Agent test event 1", events_data=[{}]
                )
                assert events_sent + events.flush_events() >= 0

                events_sent += events.send_events(
                    # this will be reported as Availability problem
                    event_type=EventType.AVAILABILITY_EVENT,
                    title="Dynatrace Snowflake Observability Agent test event 2",
                    events_data=[{}],
                    additional_payload={
                        "test.event.dtagent.number": 10,
                        "test.event.dtagent.text": "some text",
                        "test.event.dtagent.bool": True,
                        "test.event.dtagent.list": [1, 2, 3],
                        "test.event.dtagent.dict": {"k1": "v1", "k2": 2},
                        "test.event.dtagent.datetime": get_now_timestamp(),
                    },
                    timeout=30,
                )
                assert events_sent + events.flush_events() >= 0

                events_sent += events.send_events(
                    event_type=EventType.CUSTOM_ANNOTATION,
                    title="Dynatrace Snowflake Observability Agent test event 3",
                    events_data=[{}],
                    additional_payload={
                        "test.event.dtagent.info": "timeout",
                    },
                    timeout=30,
                )
                assert events_sent + events.flush_events() >= 0

                current_time_ms = int(time.time() * 1000)
                ten_minutes_ago_ms = current_time_ms - (10 * 60 * 1000)
                fifteen_minutes_from_now_ms = current_time_ms + (15 * 60 * 1000)

                events_sent += events.send_events(
                    # this will be reported as Custom problem
                    event_type=EventType.CUSTOM_ALERT,
                    title="Dynatrace Snowflake Observability Agent test event 4",
                    events_data=[{}],
                    additional_payload={
                        "test.event.dtagent.info": "10 min in the past",
                    },
                    start_time=ten_minutes_ago_ms,
                    timeout=15,
                )
                assert events_sent + events.flush_events() >= 0

                events_sent += events.send_events(
                    event_type=EventType.CUSTOM_DEPLOYMENT,
                    title="Dynatrace Snowflake Observability Agent test event 5",
                    events_data=[{}],
                    additional_payload={
                        "test.event.dtagent.info": "15 min in the future",
                    },
                    end_time=fifteen_minutes_from_now_ms,
                )
                assert events_sent + events.flush_events() >= 0

                events_sent += events.send_events(
                    event_type=EventType.CUSTOM_DEPLOYMENT,
                    title="Dynatrace Snowflake Observability Agent test event 6",
                    events_data=[{}],
                    additional_payload={
                        "test.event.dtagent.info": "15 min in the future",
                    },
                    context=get_context_name_and_run_id(
                        plugin_name="test_send_events_directly", context_name="data_volume", run_id=str(uuid.uuid4().hex)
                    ),
                    end_time=fifteen_minutes_from_now_ms,
                )
                assert events_sent + events.flush_events() >= 0

            mock_client.store_or_test_results()

        _test_send_events_directly(test_mode="davis")
        _test_send_events_directly(test_mode="generic")

    def test_send_bizevents_directly(self):
        import time

        events = self._dtagent._get_davis_events()

        mock_client = MockTelemetryClient("test_send_bizevents_directly")
        with mock_client.mock_telemetry_sending():
            events = self._dtagent._get_biz_events()

            events_sent = events.send_events(
                [
                    {
                        "test.bizevent.message": "Dynatrace Snowflake Observability Agent test event 123",
                        "test.ts": get_now_timestamp_formatted(),
                    }
                ]
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
        mock_client.store_or_test_results()

    def test_send_results_as_events(self):
        from test import _utils

        mock_client = MockTelemetryClient("test_send_results_as_events")
        with mock_client.mock_telemetry_sending():
            events = self._dtagent._get_events()

            FIXTURE_NAME = "test/test_data/data_volume.ndjson"
            for row_dict in _utils._get_fixture_entries(FIXTURE_NAME, limit=2):
                events_sent = events.report_via_api(
                    query_data=row_dict,
                    event_type=EventType.CUSTOM_INFO,
                    title="Test event for Data Volume",
                )
            assert events_sent + events.flush_events() > 0

        mock_client.store_or_test_results()

    def test_send_results_as_bizevents(self):
        from test import _utils

        mock_client = MockTelemetryClient("test_send_results_as_bizevents")
        with mock_client.mock_telemetry_sending():
            bizevents = self._dtagent._get_biz_events()

            FIXTURE_NAME = "test/test_data/data_volume.ndjson"

            events_sent = bizevents.report_via_api(
                query_data=_utils._get_fixture_entries(FIXTURE_NAME, limit=2),
                event_type=str(EventType.CUSTOM_INFO),
                context=get_context_name_and_run_id(
                    plugin_name="test_send_results_as_bizevents", context_name="data_volume", run_id=str(uuid.uuid4().hex)
                ),
            )

            events_sent += bizevents.flush_events()

            assert events_sent == 2
        mock_client.store_or_test_results()

    def test_dtagent_bizevents(self):
        mock_client = MockTelemetryClient("test_dtagent_bizevents")
        with mock_client.mock_telemetry_sending():
            bizevents = self._dtagent._get_biz_events()

            cnt = bizevents.report_via_api(
                context=get_context_name_and_run_id(
                    plugin_name="test_send_events_directly", context_name="self_monitoring", run_id=str(uuid.uuid4().hex)
                ),
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
        mock_client.store_or_test_results()


class TestEventPayloadPacking:
    """Unit tests for _pack_event_data / _add_data_to_payload serialisation contracts.

    These tests do NOT require a Snowflake session or HTTP calls.
    They verify that:
      - GenericEvents preserves rich values (dict, list) as native Python types
      - DavisEvents stringifies dict values (Davis API requires string-only properties)
      - BizEvents preserves rich values inside the ``data`` envelope
    """

    @classmethod
    def setup_class(cls):
        from test import TestConfiguration
        from dtagent.otel.events.generic import GenericEvents
        from dtagent.otel.events.davis import DavisEvents
        from dtagent.otel.events.bizevents import BizEvents
        from dtagent.config import Configuration

        dt_url = "dsoa-unit-test.live.dynatrace.com"
        minimal_conf = {
            "dt.token": "dt0c01.XXXXX.XXXXX",
            "events.http": f"https://{dt_url}{GenericEvents.ENDPOINT_PATH}",
            "davis_events.http": f"https://{dt_url}{DavisEvents.ENDPOINT_PATH}",
            "biz_events.http": f"https://{dt_url}{BizEvents.ENDPOINT_PATH}",
            "resource.attributes": Configuration.RESOURCE_ATTRIBUTES
            | {
                "host.name": "unit-test.snowflakecomputing.com",
                "service.name": "unit-test",
                "deployment.environment": "TEST",
                "telemetry.exporter.version": "0.0.0",
            },
            "otel": {},
            "plugins": {},
        }
        config = TestConfiguration(minimal_conf)
        cls._generic = GenericEvents(config)
        cls._davis = DavisEvents(config)
        cls._biz = BizEvents(config)

    # ------------------------------------------------------------------
    # GenericEvents: rich types must be preserved (no stringification)
    # ------------------------------------------------------------------

    def test_generic_preserves_dict_value(self):
        """Dict values must remain as dicts in GenericEvents payload."""
        from dtagent.otel.events import EventType

        payload = self._generic._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.nested": {"key": "value", "count": 42}},
        )
        assert isinstance(payload["field.nested"], dict), (
            f"Expected dict, got {type(payload['field.nested'])}: {payload['field.nested']!r}"
        )
        assert payload["field.nested"] == {"key": "value", "count": 42}

    def test_generic_preserves_list_value(self):
        """List values must remain as lists in GenericEvents payload."""
        from dtagent.otel.events import EventType

        payload = self._generic._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.items": [1, 2, 3], "field.tags": ["a", "b"]},
        )
        assert isinstance(payload["field.items"], list), (
            f"Expected list, got {type(payload['field.items'])}: {payload['field.items']!r}"
        )
        assert payload["field.items"] == [1, 2, 3]
        assert payload["field.tags"] == ["a", "b"]

    def test_generic_preserves_deeply_nested_object(self):
        """Deeply nested objects must be preserved in GenericEvents payload."""
        from dtagent.otel.events import EventType

        nested = {"level1": {"level2": {"level3": "deep_value"}}, "items": [{"k": "v"}]}
        payload = self._generic._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.complex": nested},
        )
        assert isinstance(payload["field.complex"], dict)
        assert payload["field.complex"]["level1"]["level2"]["level3"] == "deep_value"

    def test_generic_converts_datetime_value(self):
        """datetime values must be converted to ISO strings in GenericEvents payload (JSON-serialisable)."""
        import datetime
        import json
        from dtagent.otel.events import EventType

        dt = datetime.datetime(2026, 3, 24, 12, 0, 0, tzinfo=datetime.timezone.utc)
        payload = self._generic._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.ts": dt},
        )
        assert isinstance(payload["field.ts"], str), (
            f"Expected str ISO timestamp, got {type(payload['field.ts'])}: {payload['field.ts']!r}"
        )
        assert json.dumps(payload), "Payload with datetime field must be JSON-serialisable"

    def test_generic_unparses_json_string_to_dict(self):
        """A field whose value is a JSON-serialised string should be un-parsed to a dict by _cleanup_dict."""
        from dtagent.otel.events import EventType
        import json

        payload = self._generic._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.json_str": json.dumps({"parsed_key": "parsed_value"})},
        )
        assert isinstance(payload["field.json_str"], dict), (
            f"Expected dict after JSON un-parsing, got {type(payload['field.json_str'])}: {payload['field.json_str']!r}"
        )
        assert payload["field.json_str"]["parsed_key"] == "parsed_value"

    # ------------------------------------------------------------------
    # DavisEvents: dict values must be JSON strings in properties
    # ------------------------------------------------------------------

    def test_davis_stringifies_dict_value(self):
        """Dict values must be JSON-stringified in DavisEvents properties."""
        from dtagent.otel.events import EventType
        import json

        payload = self._davis._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.nested": {"key": "value", "count": 42}},
        )
        properties = payload["properties"]
        assert isinstance(properties["field.nested"], str), (
            f"Expected str in Davis properties, got {type(properties['field.nested'])}: {properties['field.nested']!r}"
        )
        assert json.loads(properties["field.nested"]) == {"key": "value", "count": 42}

    def test_davis_stringifies_list_of_dicts(self):
        """A list containing dict elements must have each dict stringified in Davis properties."""
        from dtagent.otel.events import EventType
        import json

        payload = self._davis._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.rows": [{"col": "a"}, {"col": "b"}]},
        )
        properties = payload["properties"]
        field_rows = properties["field.rows"]
        assert isinstance(field_rows, list), f"Expected list, got {type(field_rows)}"
        assert all(isinstance(item, str) for item in field_rows), (
            f"Expected all list elements to be strings in Davis properties, got: {field_rows!r}"
        )
        assert [json.loads(item) for item in field_rows] == [{"col": "a"}, {"col": "b"}]

    def test_davis_preserves_primitive_values(self):
        """Primitive values (str, int, bool) must not be altered in DavisEvents properties."""
        from dtagent.otel.events import EventType

        payload = self._davis._pack_event_data(
            event_type=EventType.CUSTOM_INFO,
            event_data={"field.str": "hello", "field.int": 42, "field.bool": True},
        )
        properties = payload["properties"]
        assert properties["field.str"] == "hello"
        assert properties["field.int"] == 42
        assert properties["field.bool"] is True

    # ------------------------------------------------------------------
    # BizEvents: rich types must be preserved inside the data envelope
    # ------------------------------------------------------------------

    def test_bizevents_preserves_dict_value(self):
        """Dict values must remain dicts inside the BizEvents data envelope."""
        payload = self._biz._pack_event_data(
            event_type="dsoa.test",
            event_data={"field.nested": {"key": "value", "count": 42}},
        )
        data = payload["data"]
        assert isinstance(data["field.nested"], dict), (
            f"Expected dict in BizEvents data, got {type(data['field.nested'])}: {data['field.nested']!r}"
        )
        assert data["field.nested"]["key"] == "value"

    def test_bizevents_preserves_list_value(self):
        """List values must remain lists inside the BizEvents data envelope."""
        payload = self._biz._pack_event_data(
            event_type="dsoa.test",
            event_data={"field.items": [10, 20, 30]},
        )
        data = payload["data"]
        assert isinstance(data["field.items"], list)
        assert data["field.items"] == [10, 20, 30]

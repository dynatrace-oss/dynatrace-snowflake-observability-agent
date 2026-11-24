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
"""Tests for the exporter hooks that feed ExportStatsCollector (attempted / delivered records per signal)."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from dtagent.otel.export_stats import ExportStatsCollector
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager


def _stats() -> dict:
    """Returns collected counts as {signal: (attempted, delivered)}."""
    return {row["signal"]: (row["attempted"], row["delivered"]) for row in ExportStatsCollector.get_stats()}


@pytest.fixture(autouse=True)
def _reset_collector():
    ExportStatsCollector.reset()
    ExportStatsCollector.set_plugin("test_plugin")
    OtelManager.set_max_fail_count(1000)  # failures in these tests must not abort the run
    OtelManager.set_current_fail_count(0)
    yield
    OtelManager.set_current_fail_count(0)
    ExportStatsCollector.reset()


def _json_response(status_code: int, body: dict) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = json.dumps(body).encode()  # pylint: disable=protected-access
    resp.headers["Content-Type"] = "application/json"
    resp.url = "https://tenant.example/api/v2/otlp/v1/logs"
    resp.request = MagicMock()
    return resp


def _mock_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


class TestRecordExport:
    """OtelManager.record_export_attempt / record_export_delivered"""

    def test_attempt_only(self):
        """An attempt without delivery counts only as attempted."""
        OtelManager.record_export_attempt("logs", 5)
        assert _stats() == {"logs": (5, 0)}

    def test_attempt_and_delivery(self):
        """An attempt followed by delivery counts both."""
        OtelManager.record_export_attempt("logs", 5)
        OtelManager.record_export_delivered("logs", 5)
        assert _stats() == {"logs": (5, 5)}

    def test_rejected_records_are_not_delivered(self):
        """Records rejected in a partially successful request are not delivered."""
        session = Mock(rejected_records=2)
        OtelManager.record_export_attempt("spans", 5)
        OtelManager.record_export_delivered("spans", 5, session)
        assert _stats() == {"spans": (5, 3)}

    def test_rejected_more_than_batch_does_not_go_negative(self):
        """Rejected records exceeding the batch size leave delivered at 0."""
        session = Mock(rejected_records=9)
        OtelManager.record_export_attempt("spans", 5)
        OtelManager.record_export_delivered("spans", 5, session)
        assert _stats() == {"spans": (5, 0)}


class TestSessionRejectedRecords:
    """CustomLoggingSession.rejected_records"""

    @staticmethod
    def _send(response: requests.Response) -> CustomLoggingSession:
        session = CustomLoggingSession()
        with patch.object(requests.Session, "send", return_value=response):
            session.send(MagicMock())
        return session

    def test_clean_response(self):
        """Test clean response."""
        assert self._send(_json_response(200, {})).rejected_records == 0

    def test_partial_success_logs_and_spans(self):
        """Test partial success logs and spans."""
        session = self._send(_json_response(200, {"partialSuccess": {"rejectedLogRecords": 3, "rejectedSpans": 2}}))
        assert session.rejected_records == 5

    def test_reset_on_next_request(self):
        """Test reset on next request."""
        session = CustomLoggingSession()
        with patch.object(requests.Session, "send", return_value=_json_response(200, {"partialSuccess": {"rejectedSpans": 4}})):
            session.send(MagicMock())
        assert session.rejected_records == 4
        with patch.object(requests.Session, "send", return_value=_json_response(200, {})):
            session.send(MagicMock())
        assert session.rejected_records == 0

    def test_failed_request(self):
        """Test failed request."""
        assert self._send(_json_response(500, {})).rejected_records == 0


class TestOtlpExporters:
    """The log and span exporter subclasses created in Logs._setup_logger / Spans._setup_tracer"""

    @staticmethod
    def _config() -> Mock:
        config = Mock()
        config.multitenancy_tag = None

        def _get(key=None, **kwargs):
            if key == "resource.attributes":
                return {"telemetry.exporter.name": "dsoa"}
            return kwargs.get("default_value", "http://test")

        config.get = Mock(side_effect=_get)
        return config

    def _log_exporter(self):
        from opentelemetry.sdk.resources import Resource
        from dtagent.otel.logs import Logs

        with patch("opentelemetry.sdk._logs.export.BatchLogRecordProcessor") as processor:
            Logs(Resource.create({}), self._config())
        return processor.call_args[0][0]

    def _span_exporter(self):
        from opentelemetry.sdk.resources import Resource
        from dtagent.otel.spans import Spans

        with patch("opentelemetry.sdk.trace.export.BatchSpanProcessor") as processor, patch("opentelemetry.trace.set_tracer_provider"):
            Spans(Resource.create({}), self._config())
        return processor.call_args.kwargs["span_exporter"]

    def test_logs_success(self):
        """Test logs success."""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import LogRecordExportResult

        exporter = self._log_exporter()
        with patch.object(OTLPLogExporter, "export", return_value=LogRecordExportResult.SUCCESS):
            assert exporter.export([1, 2, 3]) == LogRecordExportResult.SUCCESS
        assert _stats() == {"logs": (3, 3)}

    def test_logs_failure(self):
        """Test logs failure."""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import LogRecordExportResult

        exporter = self._log_exporter()
        with patch.object(OTLPLogExporter, "export", return_value=LogRecordExportResult.FAILURE):
            exporter.export([1, 2, 3])
        assert _stats() == {"logs": (3, 0)}

    def test_logs_partial_success(self):
        """Test logs partial success."""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import LogRecordExportResult

        exporter = self._log_exporter()

        def _export(self_, _batch):
            self_._session.rejected_records = 1  # pylint: disable=protected-access
            return LogRecordExportResult.SUCCESS

        with patch.object(OTLPLogExporter, "export", _export):
            exporter.export([1, 2, 3])
        assert _stats() == {"logs": (3, 2)}

    def test_logs_exception_still_counts_the_attempt(self):
        """If the underlying exporter raises (e.g. on a timeout) the batch is still counted as attempted, not delivered."""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        exporter = self._log_exporter()
        with patch.object(OTLPLogExporter, "export", side_effect=requests.exceptions.Timeout("timed out")):
            with pytest.raises(requests.exceptions.Timeout):
                exporter.export([1, 2, 3])
        assert _stats() == {"logs": (3, 0)}

    def test_spans_exception_still_counts_the_attempt(self):
        """If the underlying exporter raises (e.g. on a timeout) the spans are still counted as attempted, not delivered."""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = self._span_exporter()
        with patch.object(OTLPSpanExporter, "export", side_effect=requests.exceptions.Timeout("timed out")):
            with pytest.raises(requests.exceptions.Timeout):
                exporter.export([1, 2])
        assert _stats() == {"spans": (2, 0)}

    def test_spans_success_and_failure(self):
        """Test spans success and failure."""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import SpanExportResult

        exporter = self._span_exporter()
        with patch.object(OTLPSpanExporter, "export", return_value=SpanExportResult.SUCCESS):
            exporter.export([1, 2])
        with patch.object(OTLPSpanExporter, "export", return_value=SpanExportResult.FAILURE):
            exporter.export([1, 2, 3])
        assert _stats() == {"spans": (5, 2)}


class TestMetricsHook:
    """Metrics._send_metrics"""

    @staticmethod
    def _metrics(max_retries: int = 0):
        from dtagent.otel.metrics import Metrics

        m = Metrics.__new__(Metrics)
        m._max_retries = max_retries
        m._retry_delay_ms = 0
        m._max_batch_size = 10000
        m._api_post_timeout = 30
        m.PAYLOAD_CACHE = "metric.a,gauge,1\n# comment line\nmetric.b,gauge,2\n"

        def _cfg_get(key=None, **kwargs):
            return "mock-token" if key == "dt.token" else kwargs.get("default_value", "http://tenant.example/metrics")

        m._configuration = Mock()
        m._configuration.get.side_effect = _cfg_get
        return m

    def test_accepted(self):
        """Test accepted."""
        with patch("dtagent.otel.metrics.requests.post", return_value=_mock_response(202, {})):
            self._metrics()._send_metrics()
        assert _stats() == {"metrics": (2, 2)}

    def test_lines_invalid_are_not_delivered(self):
        """Test lines invalid are not delivered."""
        with patch("dtagent.otel.metrics.requests.post", return_value=_mock_response(202, {"linesInvalid": 1})):
            self._metrics()._send_metrics()
        assert _stats() == {"metrics": (2, 1)}

    def test_non_202(self):
        """Test non 202."""
        with patch("dtagent.otel.metrics.requests.post", return_value=_mock_response(400, {})):
            self._metrics()._send_metrics()
        assert _stats() == {"metrics": (2, 0)}

    def test_retried_payload_is_attempted_once(self):
        """Test retried payload is attempted once."""
        responses = [requests.exceptions.ConnectionError("down"), _mock_response(202, {})]
        with patch("dtagent.otel.metrics.requests.post", side_effect=responses), patch("dtagent.otel.metrics.time.sleep"):
            self._metrics(max_retries=2)._send_metrics()
        assert _stats() == {"metrics": (2, 2)}


class TestEventsHook:
    """AbstractEvents._send / _send_events and DavisEvents._send"""

    @staticmethod
    def _bizevents():
        from dtagent.otel.events.bizevents import BizEvents

        be = BizEvents.__new__(BizEvents)
        be._api_url = "https://tenant.example/api/v2/bizevents/ingest"
        be._max_retries = 0
        be._retry_delay_ms = 0
        be._max_payload_bytes = 5120000
        be._max_event_count = 1000
        be._api_post_timeout = 30
        be._api_event_type = "biz_events"
        be._api_content_type = "application/cloudevent-batch+json"
        be._ingest_retry_statuses = {429, 502, 503}
        be._resource_attributes = {}
        be.PAYLOAD_CACHE = []
        be._cache_byte_estimate = 0
        be._configuration = Mock()
        be._configuration.get.return_value = "mock-token"
        return be

    @staticmethod
    def _davis():
        from dtagent.otel.events.davis import DavisEvents

        de = DavisEvents.__new__(DavisEvents)
        de._api_url = "https://tenant.example/api/v2/events/ingest"
        de._max_retries = 0
        de._retry_delay_ms = 0
        de._api_event_type = "davis_events"
        de._configuration = Mock()
        de._configuration.get.return_value = "mock-token"
        return de

    def test_bizevents_delivered(self):
        """Test bizevents delivered."""
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(202, {})):
            self._bizevents()._send([{"a": 1}, {"a": 2}])
        assert _stats() == {"biz_events": (0, 2)}  # attempted is counted when events are enqueued

    def test_bizevents_rejected_not_delivered(self):
        """Test bizevents rejected not delivered."""
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(202, {"rejectedEventIngestInputCount": 1})):
            self._bizevents()._send([{"a": 1}, {"a": 2}])
        assert _stats() == {"biz_events": (0, 1)}

    def test_bizevents_failure_not_delivered(self):
        """Test bizevents failure not delivered."""
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(400, {})):
            self._bizevents()._send([{"a": 1}])
        assert _stats() == {}

    def test_enqueue_counts_attempted_once_even_if_resent(self):
        """Test enqueue counts attempted once even if resent."""
        be = self._bizevents()
        be._max_event_count = 1  # forces a send on every enqueue
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(503, {})):
            be._send_events([{"a": 1}])
            be._send_events([{"a": 2}])
        assert _stats() == {"biz_events": (2, 0)}
        assert len(be.PAYLOAD_CACHE) == 2  # kept for resend, but not counted as attempted again

    def test_flush_does_not_count_attempted(self):
        """Test flush does not count attempted."""
        be = self._bizevents()
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(202, {})):
            be._send_events([{"a": 1}, {"a": 2}, {"a": 3}])
            be._send_events(None)
        assert _stats() == {"biz_events": (3, 3)}

    def test_davis_delivered_per_event(self):
        """Test davis delivered per event."""
        with patch("dtagent.otel.events.davis.requests.post", return_value=_mock_response(201, {})):
            self._davis()._send([{"a": 1}, {"a": 2}])
        assert _stats() == {"davis_events": (0, 2)}

    def test_davis_failure_not_delivered(self):
        """Test davis failure not delivered."""
        with patch("dtagent.otel.events.davis.requests.post", return_value=_mock_response(500, {})), patch.object(
            OtelManager, "verify_communication"
        ):
            self._davis()._send([{"a": 1}])
        assert _stats() == {}


class TestRetainedEventsKeepTheirPlugin:
    """Events kept for resending are delivered while a later plugin is active, yet counted for the plugin that queued them"""

    @staticmethod
    def _by_plugin() -> dict:
        return {(r["plugin"], r["signal"]): (r["attempted"], r["delivered"]) for r in ExportStatsCollector.get_stats()}

    def test_bizevents_delivered_under_a_later_plugin(self):
        """Biz events queued by the first plugin and delivered during the second are counted for the first plugin."""
        be = TestEventsHook._bizevents()  # pylint: disable=protected-access
        be._max_event_count = 2  # pylint: disable=protected-access

        ExportStatsCollector.set_plugin("first", "run1")
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(503, {})):
            be._send_events([{"a": 1}, {"a": 2}])  # fails, stays queued
        assert len(be.PAYLOAD_CACHE) == 2

        ExportStatsCollector.set_plugin("second", "run2")
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(202, {})):
            be._send_events([{"b": 1}])  # triggers a send of the retained events and the new one
            be.flush_events()

        assert self._by_plugin() == {("first", "biz_events"): (2, 2), ("second", "biz_events"): (1, 1)}
        assert be.PAYLOAD_CACHE == []
        assert not be._event_attribution  # pylint: disable=protected-access

    def test_rejected_events_are_taken_from_the_end(self):
        """When Dynatrace rejects some events of a mixed request, the shortfall is taken from the last events."""
        be = TestEventsHook._bizevents()  # pylint: disable=protected-access
        ExportStatsCollector.set_plugin("first", "run1")
        be._send_events([{"a": 1}])  # pylint: disable=protected-access
        ExportStatsCollector.set_plugin("second", "run2")
        be._send_events([{"b": 1}])  # pylint: disable=protected-access

        with patch("dtagent.otel.events.bizevents.requests.post", return_value=_mock_response(202, {"rejectedEventIngestInputCount": 1})):
            be.flush_events()

        assert self._by_plugin() == {("first", "biz_events"): (1, 1), ("second", "biz_events"): (1, 0)}

    def test_davis_events_delivered_under_a_later_plugin(self):
        """Davis events resent in a later plugin are counted for the plugin that queued them."""
        de = TestEventsHook._davis()  # pylint: disable=protected-access
        de._max_event_count = 2  # pylint: disable=protected-access
        de._max_payload_bytes = 1000000  # pylint: disable=protected-access
        de._cache_byte_estimate = 0  # pylint: disable=protected-access
        de.PAYLOAD_CACHE = []

        ExportStatsCollector.set_plugin("first", "run1")
        # the first event hits a connection error and stays queued; the second one is refused outright and dropped (Davis keeps only
        # events that failed with an exception); a response is needed to report the failed attempt
        responses = [requests.exceptions.ConnectionError("down"), _mock_response(500, {})]
        with patch("dtagent.otel.events.davis.requests.post", side_effect=responses), patch.object(OtelManager, "verify_communication"):
            de._send_events([{"a": 1}, {"a": 2}])  # pylint: disable=protected-access
        assert de.PAYLOAD_CACHE == [{"a": 1}]

        ExportStatsCollector.set_plugin("second", "run2")
        with patch("dtagent.otel.events.davis.requests.post", return_value=_mock_response(201, {})):
            de.flush_events()

        assert self._by_plugin() == {("first", "davis_events"): (2, 1)}

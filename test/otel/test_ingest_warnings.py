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
"""Tests for IngestWarningCollector and ingest-quality warning detection in exporters."""

import json
import threading
from unittest.mock import MagicMock, patch

import requests

from dtagent.otel.ingest_warnings import IngestWarningCollector

##region ---------------------- IngestWarningCollector unit tests ---------------------------


class TestIngestWarningCollector:
    """Unit tests for the IngestWarningCollector static-method collector."""

    def setup_method(self):
        """Reset collector before each test."""
        IngestWarningCollector.reset()

    def teardown_method(self):
        """Reset collector after each test."""
        IngestWarningCollector.reset()

    def test_initially_empty(self):
        """Collector starts with no warnings."""
        assert not IngestWarningCollector.has_warnings()
        assert IngestWarningCollector.get_warnings() == []

    def test_add_single_warning(self):
        """A single warning is stored and retrievable."""
        IngestWarningCollector.add_warning("lines_invalid", "metrics", "5 lines invalid", 5)
        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert len(warnings) == 1
        assert warnings[0]["warning_type"] == "lines_invalid"
        assert warnings[0]["exporter"] == "metrics"
        assert warnings[0]["detail"] == "5 lines invalid"
        assert warnings[0]["count"] == 5

    def test_add_multiple_warnings(self):
        """Multiple warnings are all stored."""
        IngestWarningCollector.add_warning("lines_invalid", "metrics", "detail-a", 2)
        IngestWarningCollector.add_warning("partial_success", "logs", "detail-b", 3)
        IngestWarningCollector.add_warning("attr_trimmed", "metrics", "detail-c", 1)
        assert len(IngestWarningCollector.get_warnings()) == 3

    def test_reset_clears_warnings(self):
        """reset() clears all accumulated warnings."""
        IngestWarningCollector.add_warning("lines_invalid", "metrics", "detail", 1)
        IngestWarningCollector.reset()
        assert not IngestWarningCollector.has_warnings()
        assert IngestWarningCollector.get_warnings() == []

    def test_get_warnings_returns_snapshot(self):
        """get_warnings() returns a copy — mutating it does not affect the collector."""
        IngestWarningCollector.add_warning("lines_invalid", "metrics", "detail", 1)
        snapshot = IngestWarningCollector.get_warnings()
        snapshot.clear()
        assert IngestWarningCollector.has_warnings()

    def test_default_count_is_zero(self):
        """Count defaults to 0 when not supplied."""
        IngestWarningCollector.add_warning("partial_success", "logs", "detail")
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["count"] == 0

    def test_thread_safety(self):
        """Concurrent adds from multiple threads all land in the collector."""
        threads = []
        n_threads = 20

        def _add():
            IngestWarningCollector.add_warning("partial_success", "logs", "concurrent", 1)

        for _ in range(n_threads):
            t = threading.Thread(target=_add)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(IngestWarningCollector.get_warnings()) == n_threads


##endregion

##region --------- CustomLoggingSession OTLP partial_success detection tests ---------------


class TestCustomLoggingSessionPartialSuccess:
    """Tests that CustomLoggingSession.send() records OTLP partial_success warnings."""

    def setup_method(self):
        IngestWarningCollector.reset()

    def teardown_method(self):
        IngestWarningCollector.reset()

    def _make_response(self, status_code: int, body: dict) -> requests.Response:
        """Build a minimal requests.Response with a JSON body."""
        resp = requests.Response()
        resp.status_code = status_code
        resp._content = json.dumps(body).encode()  # pylint: disable=protected-access
        resp.headers["Content-Type"] = "application/json"
        resp.url = "https://tenant.example/api/v2/otlp/v1/logs"
        return resp

    def test_clean_200_no_warning(self):
        """A clean 200 response (no partialSuccess) produces no warnings."""
        from dtagent.otel.otel_manager import CustomLoggingSession

        session = CustomLoggingSession()
        clean_resp = self._make_response(200, {})
        with patch.object(requests.Session, "send", return_value=clean_resp):
            req = requests.Request("POST", "https://tenant.example/api/v2/otlp/v1/logs").prepare()
            session.send(req)

        assert not IngestWarningCollector.has_warnings()

    def test_partial_success_rejected_logs(self):
        """PartialSuccess.rejectedLogRecords > 0 adds a 'logs' warning."""
        from dtagent.otel.otel_manager import CustomLoggingSession

        session = CustomLoggingSession()
        partial_resp = self._make_response(200, {"partialSuccess": {"rejectedLogRecords": 3}})
        with patch.object(requests.Session, "send", return_value=partial_resp):
            req = requests.Request("POST", "https://tenant.example/api/v2/otlp/v1/logs").prepare()
            session.send(req)

        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["warning_type"] == "partial_success"
        assert warnings[0]["exporter"] == "logs"
        assert warnings[0]["count"] == 3

    def test_partial_success_rejected_spans(self):
        """PartialSuccess.rejectedSpans > 0 adds a 'spans' warning."""
        from dtagent.otel.otel_manager import CustomLoggingSession

        session = CustomLoggingSession()
        partial_resp = self._make_response(200, {"partialSuccess": {"rejectedSpans": 7}})
        with patch.object(requests.Session, "send", return_value=partial_resp):
            req = requests.Request("POST", "https://tenant.example/api/v2/otlp/v1/logs").prepare()
            session.send(req)

        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["warning_type"] == "partial_success"
        assert warnings[0]["exporter"] == "spans"
        assert warnings[0]["count"] == 7

    def test_malformed_json_body_no_crash(self):
        """A non-JSON response body must never crash the agent."""
        from dtagent.otel.otel_manager import CustomLoggingSession

        session = CustomLoggingSession()
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"not json at all"  # pylint: disable=protected-access
        resp.url = "https://tenant.example/api/v2/otlp/v1/logs"
        with patch.object(requests.Session, "send", return_value=resp):
            req = requests.Request("POST", "https://tenant.example/api/v2/otlp/v1/logs").prepare()
            session.send(req)  # must not raise

        assert not IngestWarningCollector.has_warnings()


##endregion

##region --------- Metrics API response parsing tests ---------------------------------------


class TestMetricsIngestWarnings:
    """Tests that Metrics._send_metrics() records DT Metrics API v2 ingest warnings."""

    def setup_method(self):
        IngestWarningCollector.reset()

    def teardown_method(self):
        IngestWarningCollector.reset()

    def _make_mock_response(self, status_code: int, body: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = body
        mock_resp.text = json.dumps(body)
        return mock_resp

    def _make_metrics_instance(self):
        """Build a minimal Metrics instance with mocked configuration."""
        from dtagent.otel.metrics import Metrics

        m = Metrics.__new__(Metrics)
        m._url = "https://tenant.example/api/v2/metrics/ingest"
        m._headers = {}
        m._max_retries = 0
        m._retry_delay_ms = 0
        m._max_batch_size = 10000
        m._api_post_timeout = 30
        m.PAYLOAD_CACHE = "metric.key,gauge,10\n"

        def _cfg_get(key=None, **kwargs):
            if key == "dt.token":
                return "mock-token"
            if key == "metrics.http":
                return "https://tenant.example/api/v2/metrics/ingest"
            return kwargs.get("default_value", "mock-value")

        mock_config = MagicMock()
        mock_config.get.side_effect = _cfg_get
        m._configuration = mock_config
        return m

    def test_clean_202_no_warning(self):
        """A clean 202 with linesInvalid=0 and no warnings produces no collector entry."""
        clean_body = {"linesOk": 10, "linesInvalid": 0, "error": None}
        mock_resp = self._make_mock_response(202, clean_body)
        with patch("dtagent.otel.metrics.requests.post", return_value=mock_resp):
            self._make_metrics_instance()._send_metrics()

        assert not IngestWarningCollector.has_warnings()

    def test_lines_invalid_adds_warning(self):
        """Metric lines_invalid > 0 in the 202 response adds a warning."""
        body = {"linesOk": 8, "linesInvalid": 2, "error": None}
        mock_resp = self._make_mock_response(202, body)
        with patch("dtagent.otel.metrics.requests.post", return_value=mock_resp):
            self._make_metrics_instance()._send_metrics()

        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["warning_type"] == "lines_invalid"
        assert warnings[0]["exporter"] == "metrics"
        assert warnings[0]["count"] == 2

    def test_attr_trimmed_adds_warning(self):
        """Non-persisted attribute keys in warnings list adds an 'attr_trimmed' warning."""
        body = {
            "linesOk": 10,
            "linesInvalid": 0,
            "error": None,
            "warnings": [{"non_persisted_attribute_keys": ["foo.bar", "baz.qux"]}],
        }
        mock_resp = self._make_mock_response(202, body)
        with patch("dtagent.otel.metrics.requests.post", return_value=mock_resp):
            self._make_metrics_instance()._send_metrics()

        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["warning_type"] == "attr_trimmed"
        assert warnings[0]["exporter"] == "metrics"
        assert warnings[0]["count"] == 2
        assert "foo.bar" in warnings[0]["detail"]

    def test_malformed_response_json_no_crash(self):
        """Non-JSON response body on 202 must not crash."""
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.side_effect = ValueError("not json")
        with patch("dtagent.otel.metrics.requests.post", return_value=mock_resp):
            self._make_metrics_instance()._send_metrics()  # must not raise

        assert not IngestWarningCollector.has_warnings()


##endregion

##region --------- Events API partial-rejection detection tests ----------------------------


class TestEventsIngestWarnings:
    """Tests that AbstractEvents._send() records partial-rejection warnings."""

    def setup_method(self):
        IngestWarningCollector.reset()

    def teardown_method(self):
        IngestWarningCollector.reset()

    def _make_bizevents_instance(self):
        """Build a minimal BizEvents instance with mocked configuration."""
        from dtagent.otel.events.bizevents import BizEvents

        be = BizEvents.__new__(BizEvents)
        be._url = "https://tenant.example/api/v2/bizevents/ingest"
        be._api_url = "https://tenant.example/api/v2/bizevents/ingest"
        be._headers = {}
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
        mock_config = MagicMock()
        mock_config.get.return_value = "mock-token"
        be._configuration = mock_config
        return be

    def test_clean_202_no_warning(self):
        """A clean 202 with no rejections produces no warning."""
        clean_resp = MagicMock()
        clean_resp.status_code = 202
        clean_resp.json.return_value = {}
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=clean_resp):
            self._make_bizevents_instance()._send([{"event.type": "dsoa.task", "data": {}}])

        assert not IngestWarningCollector.has_warnings()

    def test_rejected_event_count_adds_warning(self):
        """Rejected event count > 0 in 202 body adds a 'partial_success' warning."""
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {"rejectedEventIngestInputCount": 4}
        with patch("dtagent.otel.events.bizevents.requests.post", return_value=mock_resp):
            self._make_bizevents_instance()._send([{"event.type": "dsoa.task", "data": {}}])

        assert IngestWarningCollector.has_warnings()
        warnings = IngestWarningCollector.get_warnings()
        assert warnings[0]["warning_type"] == "partial_success"
        assert warnings[0]["count"] == 4


##endregion

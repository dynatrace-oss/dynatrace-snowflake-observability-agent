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
import time
import pytest
from unittest.mock import Mock, patch
from opentelemetry._logs import SeverityNumber


class TestLoggerNaming:
    """Tests for OTLP logger naming with TAG support"""

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_without_tag(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name returns DTAGENT_OTLP when no TAG is configured"""
        from dtagent.otel.logs import Logs

        mock_config = Mock()
        mock_config.multitenancy_tag = None

        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        logs = Logs(Mock(), mock_config)
        logger_name = logs._Logs__get_logger_name()

        assert logger_name == "DTAGENT_OTLP", f"Expected DTAGENT_OTLP but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_with_tag(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name returns DTAGENT_TAG_OTLP when TAG is configured"""
        from dtagent.otel.logs import Logs

        mock_config = Mock()
        mock_config.multitenancy_tag = "ENV01"

        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        logs = Logs(Mock(), mock_config)
        logger_name = logs._Logs__get_logger_name()

        assert logger_name == "DTAGENT_ENV01_OTLP", f"Expected DTAGENT_ENV01_OTLP but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_with_various_tags(self, mock_resource, mock_logger_provider):
        """Test __get_logger_name with various TAG values"""
        from dtagent.otel.logs import Logs

        test_cases = [
            ("TEST", "DTAGENT_TEST_OTLP"),
            ("PROD", "DTAGENT_PROD_OTLP"),
            ("TENANT_A", "DTAGENT_TENANT_A_OTLP"),
            ("ENV_123", "DTAGENT_ENV_123_OTLP"),
            ("SA080", "DTAGENT_SA080_OTLP"),
        ]

        for tag, expected in test_cases:
            mock_config = Mock()
            mock_config.multitenancy_tag = tag

            def mock_get(key=None, otel_module=None, **kwargs):
                if otel_module == "logs":
                    if kwargs.get("key") == "export_timeout_millis":
                        return 10000
                    if kwargs.get("key") == "max_export_batch_size":
                        return 100
                return kwargs.get("default_value", "http://test")

            mock_config.get = Mock(side_effect=mock_get)
            logs = Logs(Mock(), mock_config)
            logger_name = logs._Logs__get_logger_name()

            assert logger_name == expected, f"For TAG={tag}, expected {expected} but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_no_double_tagging(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name doesn't create double tags"""
        from dtagent.otel.logs import Logs

        mock_config = Mock()
        mock_config.multitenancy_tag = "TAG"

        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)
        logs = Logs(Mock(), mock_config)
        logger_name = logs._Logs__get_logger_name()

        assert logger_name == "DTAGENT_TAG_OTLP"
        assert "TAG_TAG" not in logger_name, f"Double tagging detected in {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_logger_name_matches_get_logger_call(self, mock_resource, mock_logger_provider):
        """Test that logger_provider.get_logger() is called with the name from __get_logger_name"""
        from dtagent.otel.logs import Logs

        mock_config = Mock()
        mock_config.multitenancy_tag = "PROD"

        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)
        logs = Logs(Mock(), mock_config)
        expected_name = logs._Logs__get_logger_name()

        mock_logger_provider.return_value.get_logger.assert_called_with(expected_name)
        assert expected_name == "DTAGENT_PROD_OTLP"


from dtagent.otel.logs import Logs, _SEVERITY_MAP  # noqa: E402


class TestSeverityMapping:
    """Tests for Python logging level → OTel SeverityNumber mapping"""

    def test_trace(self):
        assert _SEVERITY_MAP[5] == SeverityNumber.TRACE

    def test_debug(self):
        assert _SEVERITY_MAP[logging.DEBUG] == SeverityNumber.DEBUG

    def test_info(self):
        assert _SEVERITY_MAP[logging.INFO] == SeverityNumber.INFO

    def test_warning(self):
        assert _SEVERITY_MAP[logging.WARNING] == SeverityNumber.WARN

    def test_error(self):
        assert _SEVERITY_MAP[logging.ERROR] == SeverityNumber.ERROR

    def test_critical(self):
        assert _SEVERITY_MAP[logging.CRITICAL] == SeverityNumber.FATAL

    def test_unknown_level_defaults_to_info(self):
        assert _SEVERITY_MAP.get(99, SeverityNumber.INFO) == SeverityNumber.INFO


class TestEmitBoundary:
    """Tests that send_log() passes correct values to Logger.emit()"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("dtagent.otel.logs.LoggerProvider") as mock_lp, patch("dtagent.otel.logs.Resource"), patch(
            "dtagent.otel.logs.OtelManager"
        ):
            mock_config = Mock()
            mock_config.multitenancy_tag = None

            def mock_get(key=None, otel_module=None, **kwargs):
                if otel_module == "logs":
                    if kwargs.get("key") == "export_timeout_millis":
                        return 10000
                    if kwargs.get("key") == "max_export_batch_size":
                        return 100
                return kwargs.get("default_value", "http://test")

            mock_config.get = Mock(side_effect=mock_get)
            self.logs = Logs(Mock(), mock_config)
            self.mock_otel_logger = mock_lp.return_value.get_logger.return_value
            yield

    def _emit_kwargs(self):
        return self.mock_otel_logger.emit.call_args.kwargs

    def test_timestamp_ms_converted_to_ns(self):
        """Timestamp in extra (ms) — emit receives ns."""
        ts_ms = int(time.time() * 1000)
        self.logs.send_log("msg", extra={"timestamp": ts_ms})
        assert self._emit_kwargs()["timestamp"] == ts_ms * 1_000_000

    def test_no_timestamp_passes_none(self):
        """No timestamp in extra — emit receives timestamp=None."""
        self.logs.send_log("msg")
        assert self._emit_kwargs()["timestamp"] is None

    def test_observed_timestamp_ns_passed_through(self):
        """observed_timestamp already in ns → emit receives it unchanged"""
        ts_ns = int(time.time() * 1_000_000_000)
        self.logs.send_log("msg", extra={"observed_timestamp": ts_ns})
        assert self._emit_kwargs()["observed_timestamp"] == ts_ns

    def test_none_body_becomes_dash(self):
        """send_log(None) → emit body='-'"""
        self.logs.send_log(None)
        assert self._emit_kwargs()["body"] == "-"

    def test_timestamp_not_in_attributes(self):
        """Timestamp must not leak into attributes dict."""
        ts_ms = int(time.time() * 1000)
        self.logs.send_log("msg", extra={"timestamp": ts_ms})
        attrs = self._emit_kwargs().get("attributes") or {}
        assert "timestamp" not in attrs

    def test_observed_timestamp_not_in_attributes(self):
        """observed_timestamp must not leak into attributes dict"""
        ts_ns = int(time.time() * 1_000_000_000)
        self.logs.send_log("msg", extra={"observed_timestamp": ts_ns})
        attrs = self._emit_kwargs().get("attributes") or {}
        assert "observed_timestamp" not in attrs

    def test_severity_number_error(self):
        """log_level=ERROR → emit receives SeverityNumber.ERROR"""
        self.logs.send_log("msg", log_level=logging.ERROR)
        assert self._emit_kwargs()["severity_number"] == SeverityNumber.ERROR

    def test_severity_text_matches_level(self):
        """severity_text matches logging.getLevelName"""
        self.logs.send_log("msg", log_level=logging.WARNING)
        assert self._emit_kwargs()["severity_text"] == "WARNING"

    def test_extra_attribute_present(self):
        """Regular extra attributes survive into emit attributes."""
        self.logs.send_log("msg", extra={"foo": "bar"})
        attrs = self._emit_kwargs().get("attributes") or {}
        assert attrs.get("foo") == "bar"

    def test_multitenancy_scope_name(self):
        """multitenancy_tag is reflected in get_logger() instrumentation scope name"""
        with patch("dtagent.otel.logs.LoggerProvider") as mock_lp, patch("dtagent.otel.logs.Resource"), patch(
            "dtagent.otel.logs.OtelManager"
        ):
            mock_config = Mock()
            mock_config.multitenancy_tag = "T1"

            def mock_get(key=None, otel_module=None, **kwargs):
                return kwargs.get("default_value", "http://test")

            mock_config.get = Mock(side_effect=mock_get)
            Logs(Mock(), mock_config)
            mock_lp.return_value.get_logger.assert_called_with("DTAGENT_T1_OTLP")

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
import pytest
from dtagent.otel.otel_manager import OtelManager, _sanitize_ua_segment
from dtagent.otel import USER_AGENT
from test._utils import LocalTelemetrySender, get_config, read_clean_data_from_file
from test import _get_session
import os

ENV_VAR_NAME = "DTAGENT_TOKEN"


class TestUserAgentHeaders:
    """Unit tests for the dynamic User-Agent header logic in OtelManager."""

    def setup_method(self):
        """Reset class-level state before each test."""
        OtelManager._run_environment = None
        OtelManager._current_plugin = None

    def test_base_headers_only(self):
        """get_dsoa_headers() with no state returns bare version string."""
        headers = OtelManager.get_dsoa_headers()
        assert headers["User-Agent"] == USER_AGENT
        assert headers["X-Dynatrace-Attr"] == "dt.ingest.origin=snowflake-dsoa"

    def test_env_only(self):
        """set_run_environment() adds env= segment."""
        mgr = OtelManager()
        mgr.set_run_environment("PROD")
        assert OtelManager.get_dsoa_headers()["User-Agent"] == f"{USER_AGENT};env=PROD"

    def test_plugin_only(self):
        """set_current_plugin() adds plugin= segment."""
        mgr = OtelManager()
        mgr.set_current_plugin("query_history")
        assert OtelManager.get_dsoa_headers()["User-Agent"] == f"{USER_AGENT};plugin=query_history"

    def test_env_and_plugin(self):
        """Both set gives full three-part header."""
        mgr = OtelManager()
        mgr.set_run_environment("STAGING")
        mgr.set_current_plugin("data_volume")
        assert OtelManager.get_dsoa_headers()["User-Agent"] == f"{USER_AGENT};env=STAGING;plugin=data_volume"

    def test_none_env_omitted(self):
        """None deployment_environment means env= is omitted."""
        mgr = OtelManager()
        mgr.set_run_environment(None)
        mgr.set_current_plugin("shares")
        assert "env=" not in OtelManager.get_dsoa_headers()["User-Agent"]

    def test_empty_string_env_omitted(self):
        """Empty string deployment_environment is treated as absent."""
        mgr = OtelManager()
        mgr.set_run_environment("")
        mgr.set_current_plugin("shares")
        assert "env=" not in OtelManager.get_dsoa_headers()["User-Agent"]

    def test_class_level_state_shared(self):
        """State set on one instance is visible via class-level call (for metrics/events)."""
        mgr = OtelManager()
        mgr.set_run_environment("DEV")
        mgr.set_current_plugin("tasks")
        # metrics.py calls OtelManager.get_dsoa_headers() as a class-level call
        class_headers = OtelManager.get_dsoa_headers()
        assert "env=DEV" in class_headers["User-Agent"]
        assert "plugin=tasks" in class_headers["User-Agent"]

    def test_sanitize_strips_crlf(self):
        """_sanitize_ua_segment removes CR/LF characters."""
        assert _sanitize_ua_segment("val\r\nue") == "value"

    def test_sanitize_strips_control_chars(self):
        """_sanitize_ua_segment removes ASCII control characters."""
        assert _sanitize_ua_segment("val\x00ue") == "value"

    def test_sanitize_none_returns_none(self):
        assert _sanitize_ua_segment(None) is None

    def test_sanitize_blank_returns_none(self):
        assert _sanitize_ua_segment("  ") is None

    def test_injection_sanitized(self):
        """CRLF characters are removed so the value cannot split into new header lines."""
        mgr = OtelManager()
        mgr.set_current_plugin("evil\r\nX-Injected: header")
        ua = OtelManager.get_dsoa_headers()["User-Agent"]
        assert "\r" not in ua
        assert "\n" not in ua


class TestOtelManager:

    def test_otel_manager_throw_exception(self):
        original_env_var = os.environ.get(ENV_VAR_NAME)
        os.environ[ENV_VAR_NAME] = "invalid_token"

        try:
            max_fails_allowed = 5
            structured_test_data = read_clean_data_from_file("test/test_data/telemetry_structured.json")

            session = _get_session()
            sender = LocalTelemetrySender(
                session,
                {"auto_mode": False, "logs": False, "events": True, "bizevents": True, "metrics": True},
                config=get_config(),
                exec_id=str(uuid.uuid4().hex),
            )
            OtelManager.set_max_fail_count(max_fails_allowed)

            with pytest.raises(RuntimeError, match="Too many failed attempts to send data to Dynatrace \\(\\d+ / \\d+\\), aborting run"):
                i = 0
                while i < max_fails_allowed or max_fails_allowed <= OtelManager.get_current_fail_count():
                    sender.send_data(structured_test_data[0])
                    sender._flush_logs()
                    i += 1
                sender.teardown()
                assert max_fails_allowed <= OtelManager.get_current_fail_count()
                OtelManager.verify_communication()
        finally:
            if original_env_var:
                os.environ[ENV_VAR_NAME] = original_env_var

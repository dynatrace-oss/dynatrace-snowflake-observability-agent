"""Tests of the dynamic User-Agent built by OtelManager."""

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

from unittest.mock import Mock, patch

import pytest
import requests

from dtagent.otel import USER_AGENT
from dtagent.otel.otel_manager import MAX_USER_AGENT_LENGTH, USER_AGENT_REPORT_PAYLOAD, OtelManager, SessionUserAgentMixin


@pytest.fixture(autouse=True)
def _clean_state():
    """Resets the class-level User-Agent state around each test."""
    OtelManager.set_run_environment(None)
    OtelManager.set_current_plugin(None)
    OtelManager.reset_current_fail_count()
    yield
    OtelManager.set_run_environment(None)
    OtelManager.set_current_plugin(None)


def _ua(segments=None) -> str:
    return OtelManager.get_dsoa_headers(segments)["User-Agent"]


class TestUserAgent:
    """Dynamic User-Agent construction, sanitization, size cap and session refresh."""

    def test_default_is_bare_version(self):
        """Default is bare version."""
        assert _ua() == USER_AGENT
        assert OtelManager.get_dsoa_headers()["X-Dynatrace-Attr"] == "dt.ingest.origin=snowflake-dsoa"

    def test_env_plugin_and_extra_segments(self):
        """Env plugin and extra segments."""
        OtelManager.set_run_environment("PROD")
        OtelManager.set_current_plugin("heartbeat")
        assert _ua({"hb": "t", "exp": 10}) == f"{USER_AGENT};env=PROD;plugin=heartbeat;hb=t;exp=10"

    def test_segments_are_sanitized(self):
        """Segments are sanitized."""
        OtelManager.set_run_environment("a;b\r\nX-Evil: 1")
        ua = _ua({"k;": "v\n", "empty": ""})
        assert "\r" not in ua and "\n" not in ua
        assert ua == f"{USER_AGENT};env=abX-Evil: 1;k=v"

    def test_blank_values_are_omitted(self):
        """Blank values are omitted."""
        OtelManager.set_run_environment("  ")
        OtelManager.set_current_plugin(None)
        assert _ua() == USER_AGENT

    def test_user_agent_never_exceeds_the_limit(self):
        """User agent never exceeds the limit."""
        OtelManager.set_run_environment("e" * 500)
        OtelManager.set_current_plugin("heartbeat")
        ua = _ua({"first": "1", "huge": "x" * MAX_USER_AGENT_LENGTH, "last": "2"})
        assert len(ua) <= MAX_USER_AGENT_LENGTH
        assert ua.endswith(";plugin=heartbeat")  # the plugin has priority over a long environment, which is truncated

    def test_segments_that_do_not_fit_are_dropped_not_truncated(self):
        """Segments that do not fit are dropped not truncated."""
        OtelManager.set_run_environment("PROD")
        ua = _ua({"first": "1", "huge": "x" * MAX_USER_AGENT_LENGTH, "last": "2"})
        assert ua == f"{USER_AGENT};env=PROD;first=1;last=2"

    def test_plugin_name_too_long_is_dropped(self):
        """Plugin name too long is dropped."""
        OtelManager.set_current_plugin("p" * 300)
        assert _ua() == USER_AGENT

    def test_normal_user_agent_has_no_summary_state(self):
        """Segments are given per call and never remembered."""
        _ua({"hb": "t"})
        assert _ua() == USER_AGENT

    def test_report_sends_a_minimal_request_with_the_segments(self):
        """Report sends a minimal request with the segments."""
        OtelManager.set_run_environment("PROD")
        OtelManager.set_current_plugin("heartbeat")
        with patch("dtagent.otel.otel_manager.requests.post", return_value=Mock(status_code=202, text="")) as post:
            assert OtelManager.send_user_agent_report("https://t/metrics", "tok", {"hb": "l", "exp": 5}) is True
        kwargs = post.call_args.kwargs
        assert kwargs["data"] == USER_AGENT_REPORT_PAYLOAD
        assert kwargs["headers"]["User-Agent"] == f"{USER_AGENT};env=PROD;hb=l;exp=5"  # no plugin segment in a report
        assert kwargs["headers"]["Authorization"] == "Api-Token tok"

    def test_report_environment_is_cut_to_keep_the_segments(self):
        """Report environment is cut to keep the segments."""
        OtelManager.set_run_environment("E" * 100)
        segments = {"hb": "m", "exp": 1234567, "dlv": 1234567}
        ua = OtelManager.build_user_agent(segments, report=True)
        assert len(ua) <= MAX_USER_AGENT_LENGTH
        assert ua.endswith(";hb=m;exp=1234567;dlv=1234567")

    def test_report_segment_that_does_not_fit_is_dropped_whole(self):
        """Report segment that does not fit is dropped whole, never cut."""
        OtelManager.set_run_environment("E" * 100)
        ua = OtelManager.build_user_agent({"hb": "t", "exp": 1234567, "ok": 1234567, "fail": 1234567}, report=True)
        assert len(ua) <= MAX_USER_AGENT_LENGTH
        assert ua.endswith(";hb=t;exp=1234567;ok=1234567")

    def test_report_fits_the_observed_environment(self):
        """The reports seen on the tenant are no longer truncated."""
        OtelManager.set_run_environment("TEST_MJAK")
        OtelManager.set_current_plugin("heartbeat")
        for segments in ({"hb": "t", "exp": 1002, "ok": 613, "fail": 389}, {"hb": "m", "exp": 81841, "dlv": 81840}):
            assert OtelManager.build_user_agent(segments, report=True) == (
                f"{USER_AGENT};env=TEST_MJAK;" + ";".join(f"{k}={v}" for k, v in segments.items())
            )

    def test_shrink_key_shortens_the_name_so_the_counts_fit(self):
        """Shrink key shortens the name so the counts fit."""
        OtelManager.set_run_environment("E" * 100)
        segments = {"tk": "table_health_clustering", "exp": 288, "ok": 287}
        ua = OtelManager.build_user_agent(segments, report=True, shrink_key="tk")
        assert len(ua) <= MAX_USER_AGENT_LENGTH
        assert ua.endswith(";exp=288;ok=287") and ";tk=table_health" in ua

    def test_shrink_key_leaves_a_name_that_fits_untouched(self):
        """Shrink key leaves a name that fits untouched."""
        OtelManager.set_run_environment("TEST_MJAK")
        ua = OtelManager.build_user_agent({"tk": "table_health_clustering", "exp": 48, "ok": 47}, report=True, shrink_key="tk")
        assert ua == f"{USER_AGENT};env=TEST_MJAK;tk=table_health_clustering;exp=48;ok=47"

    def test_shrink_key_is_dropped_when_nothing_fits(self):
        """Shrink key is dropped when nothing fits."""
        OtelManager.set_run_environment("E" * 100)
        ua = OtelManager.build_user_agent({"tk": "x", "exp": "9" * 30, "ok": "9" * 12}, report=True, shrink_key="tk")
        assert len(ua) <= MAX_USER_AGENT_LENGTH and "tk=" not in ua

    def test_report_answered_with_any_status_counts_as_sent(self):
        """Report answered with any status counts as sent, as only its User-Agent matters."""
        for status in (202, 400, 401, 500):
            with patch("dtagent.otel.otel_manager.requests.post", return_value=Mock(status_code=status, text="bad")):
                assert OtelManager.send_user_agent_report("https://t/metrics", "tok", {"hb": "l"}) is True
        assert OtelManager.get_current_fail_count() == 0  # a rejected report does not count as a failed export

    def test_report_that_cannot_be_sent_is_swallowed(self):
        """Report that cannot be sent is swallowed and reported as not sent."""
        with patch("dtagent.otel.otel_manager.requests.post", side_effect=requests.ConnectionError("down")):
            assert OtelManager.send_user_agent_report("https://t/metrics", "tok", {"hb": "l"}) is False

    def test_mixin_refreshes_session_headers(self):
        """Mixin refreshes session headers."""

        class _Exporter(SessionUserAgentMixin):
            def __init__(self):
                self._session = requests.Session()

        exporter = _Exporter()
        OtelManager.set_current_plugin("query_history")
        exporter.refresh_user_agent()
        assert exporter._session.headers["User-Agent"] == f"{USER_AGENT};plugin=query_history"
        OtelManager.set_current_plugin("heartbeat")
        exporter.refresh_user_agent()
        assert exporter._session.headers["User-Agent"].endswith("plugin=heartbeat")

    def test_mixin_without_session_is_noop(self):
        """Mixin without session is noop."""
        SessionUserAgentMixin().refresh_user_agent()

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
class TestTrustCenter:
    import pytest

    FIXTURES = {
        "APP.V_TRUST_CENTER_METRICS": "test/test_data/trust_center_metrics.ndjson",
        "APP.V_TRUST_CENTER_INSTRUMENTED": "test/test_data/trust_center_instrumented.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_trust_center(self):

        from typing import Generator, Dict
        import logging
        from unittest.mock import patch
        from test import TestDynatraceSnowAgent, _get_session
        import test._utils as utils
        from dtagent.plugins.trust_center import TrustCenterPlugin
        from dtagent import plugins

        # -----------------------------------------------------

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestTrustCenterPlugin(TrustCenterPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestTrustCenter.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestTrustCenterPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        # trust_center has one CRITICAL finding (routed as a Davis event) and one non-critical
        # finding (routed as a log). Disabling "logs" alone drops the non-critical row entirely
        # (it is never logged nor evented), rather than falling back to another channel.
        # Disabling "events" alone routes both rows through logs instead.
        trust_center_default = {"entries": 2, "log_lines": 1, "events": 1}
        trust_center_logs_disabled = {"entries": 1, "log_lines": 0, "events": 1}
        trust_center_events_disabled = {"entries": 2, "log_lines": 2, "events": 0}
        metrics_enabled = {"entries": 2, "metrics": 2}
        metrics_disabled = {"entries": 0, "metrics": 0}

        # the CRITICAL row now logs instead of eventing when events are disabled, so "logs"
        # content diverges from the fixture recorded with events enabled; counts are still checked.
        skip_logs_content = ["logs"]

        disabled_combinations_and_counts = [
            ([], {"trust_center": trust_center_default, "trust_center_metrics": metrics_enabled}, None),
            (["metrics"], {"trust_center": trust_center_default, "trust_center_metrics": metrics_disabled}, None),
            (["logs"], {"trust_center": trust_center_logs_disabled, "trust_center_metrics": metrics_enabled}, None),
            (["events"], {"trust_center": trust_center_events_disabled, "trust_center_metrics": metrics_enabled}, skip_logs_content),
            (
                ["metrics", "logs"],
                {"trust_center": trust_center_logs_disabled, "trust_center_metrics": metrics_disabled},
                None,
            ),
            (
                ["metrics", "events"],
                {"trust_center": trust_center_events_disabled, "trust_center_metrics": metrics_disabled},
                skip_logs_content,
            ),
            (["logs", "events"], {"trust_center": trust_center_default, "trust_center_metrics": metrics_enabled}, None),
            (
                ["metrics", "logs", "events"],
                {"trust_center": trust_center_default, "trust_center_metrics": metrics_disabled},
                None,
            ),
        ]

        for disabled_telemetry, base_count, skip_content_check in disabled_combinations_and_counts:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_trust_center",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count=base_count,
                skip_content_check=skip_content_check,
            )


if __name__ == "__main__":
    test_class = TestTrustCenter()
    test_class.test_trust_center()

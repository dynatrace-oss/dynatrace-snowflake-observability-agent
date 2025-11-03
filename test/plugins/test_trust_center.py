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

    PICKLES = {
        "APP.V_TRUST_CENTER_METRICS": "test/test_data/trust_center_metrics.pkl",
        "APP.V_TRUST_CENTER_INSTRUMENTED": "test/test_data/trust_center_instr.pkl",
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

        utils._pickle_all(_get_session(), self.PICKLES)

        class TestTrustCenterPlugin(TrustCenterPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestTrustCenter.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestTrustCenterPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["metrics"],
            ["logs"],
            ["events"],
            ["metrics", "logs"],
            ["metrics", "events"],
            ["logs", "events"],
            ["metrics", "logs", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_trust_center",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "trust_center": {"entries": 2, "log_lines": 2, "events": 0},
                    "trust_center_metrics": {"entries": 2, "metrics": 2},
                },
            )


if __name__ == "__main__":
    test_class = TestTrustCenter()
    test_class.test_trust_center()

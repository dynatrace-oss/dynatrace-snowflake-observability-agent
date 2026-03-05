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
class TestLoginHist:
    import pytest

    FIXTURES = {
        "APP.V_LOGIN_HISTORY": "test/test_data/login_history.ndjson",
        "APP.V_SESSIONS": "test/test_data/login_history_sessions.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_login_hist(self):
        import logging
        from unittest.mock import patch
        from typing import Dict, Generator
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.login_history import LoginHistoryPlugin

        # ======================================================================

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestLoginHistoryPlugin(LoginHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestLoginHist.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestLoginHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["logs"],
            ["events"],
            ["logs", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_login_history",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "events"],
                base_count={
                    "login_history": {"entries": 2, "log_lines": 2, "metrics": 0, "events": 0},
                    "sessions": {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0},
                },
            )


if __name__ == "__main__":
    test_class = TestLoginHist()
    test_class.test_login_hist()

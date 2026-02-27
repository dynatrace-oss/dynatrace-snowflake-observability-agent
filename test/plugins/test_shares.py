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
class TestShares:
    import pytest

    FIXTURES = {
        "APP.V_INBOUND_SHARE_TABLES": "test/test_data/shares_inbound.ndjson",
        "APP.V_OUTBOUND_SHARE_TABLES": "test/test_data/shares_outbound.ndjson",
        "APP.V_SHARE_EVENTS": "test/test_data/shares_events.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_shares(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.shares import SharesPlugin

        # ======================================================================

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_GET_SHARES", log_on_exception=True)
            utils._generate_all_fixtures(session, self.FIXTURES, force=True)

        class TestSharesPlugin(SharesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
<<<<<<< dev/skruk/fix-inbound-shares-db
                limit = 3 if t_data == "APP.V_INBOUND_SHARE_TABLES" else 2
                return utils._safe_get_fixture_entries(TestShares.FIXTURES, t_data, limit=limit)
=======
                return utils._safe_get_fixture_entries(TestShares.FIXTURES, t_data, limit=2)
>>>>>>> release/0.9.4

        def __local_get_plugin_class(source: str):
            return TestSharesPlugin

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
                test_name="test_shares",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "events"],  # there is not test data for events
                base_count={
                    "outbound_shares": {"entries": 2, "log_lines": 2, "metrics": 0, "events": 2},
                    "inbound_shares": {"entries": 3, "log_lines": 3, "metrics": 0, "events": 0},
                    "shares": {"entries": 2, "log_lines": 0, "metrics": 0, "events": 2},
                },
            )


if __name__ == "__main__":
    test_class = TestShares()
    test_class.test_shares()

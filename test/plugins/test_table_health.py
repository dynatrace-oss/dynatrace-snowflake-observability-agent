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
class TestTableHealth:
    import pytest

    FIXTURES = {"APP.V_TABLE_STORAGE": "test/test_data/table_health_storage.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health(self):
        from typing import Dict, Generator
        from dtagent.plugins.table_health import TableHealthPlugin
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        # ======================================================================

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestTableHealthPlugin(TableHealthPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestTableHealth.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestTableHealthPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        import logging

        disabled_combinations = [
            [],
            ["metrics"],
            ["biz_events"],
            ["metrics", "biz_events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_table_health",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["metrics", "biz_events"],
                base_count={"table_health": {"entries": 2, "log_lines": 0, "metrics": 10, "events": 0}},
            )


if __name__ == "__main__":
    test_class = TestTableHealth()
    test_class.test_table_health()

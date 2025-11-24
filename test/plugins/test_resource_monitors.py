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
class TestResMon:
    import pytest

    T_DATA_RESMON = "APP.V_RESOURCE_MONITORS"
    T_DATA_WHS = "APP.V_WAREHOUSES"
    PICKLES = {T_DATA_RESMON: "test/test_data/resource_monitors.pkl", T_DATA_WHS: "test/test_data/warehouses.pkl"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_res_mon(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        # ======================================================================

        if utils.should_pickle(self.PICKLES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RESOURCE_MONITORS", log_on_exception=True)
            utils._pickle_data_history(
                session, self.T_DATA_RESMON, self.PICKLES[self.T_DATA_RESMON], lambda df: df.sort("IS_ACCOUNT_LEVEL", ascending=False)
            )
            utils._pickle_data_history(session, self.T_DATA_WHS, self.PICKLES[self.T_DATA_WHS])

        class TestResourceMonitorsPlugin(ResourceMonitorsPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestResMon.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestResourceMonitorsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["logs"],
            ["metrics"],
            ["events"],
            ["logs", "metrics"],
            ["logs", "events"],
            ["metrics", "events"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_resource_monitors",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "resource_monitors": {"entries": 2, "log_lines": 0, "metrics": 10, "events": 4},
                    "warehouses": {"entries": 2, "log_lines": 0, "metrics": 12, "events": 6},
                },
            )


if __name__ == "__main__":
    test_class = TestResMon()
    test_class.test_res_mon()

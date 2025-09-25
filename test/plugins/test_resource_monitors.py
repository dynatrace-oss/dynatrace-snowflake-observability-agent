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
    T_DATA_RESMON = "APP.V_RESOURCE_MONITORS"
    T_DATA_WHS = "APP.V_WAREHOUSES"
    PICKLES = {T_DATA_RESMON: "test/test_data/resource_monitors.pkl", T_DATA_WHS: "test/test_data/warehouses.pkl"}

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

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session, utils.get_config()), "test_resource_monitors", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestResMon()
    test_class.test_res_mon()

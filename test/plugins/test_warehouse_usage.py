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
class TestWhUsage:
    PICKLES = {
        "APP.V_WAREHOUSE_EVENT_HISTORY": "test/test_data/wh_usage_events.pkl",
        "APP.V_WAREHOUSE_LOAD_HISTORY": "test/test_data/wh_usage_loads.pkl",
        "APP.V_WAREHOUSE_METERING_HISTORY": "test/test_data/wh_usage_metering.pkl",
    }

    def test_wh_usage(self):
        from dtagent.plugins.warehouse_usage import WarehouseUsagePlugin
        from dtagent import plugins
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from unittest.mock import patch
        import logging

        # -----------------------------------------------------

        utils._pickle_all(_get_session(), self.PICKLES)

        class TestWarehouseUsagePlugin(WarehouseUsagePlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestWhUsage.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestWarehouseUsagePlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session, utils.get_config()), "test_warehouse_usage", logging.INFO, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestWhUsage()
    test_class.test_wh_usage()

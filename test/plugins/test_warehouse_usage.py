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
    def test_wh_usage(self):
        from dtagent.plugins.warehouse_usage import WarehouseUsagePlugin
        from dtagent import plugins
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        import logging

        T_WH_EVENTS = "APP.V_WAREHOUSE_EVENT_HISTORY"
        T_WH_LOADS = "APP.V_WAREHOUSE_LOAD_HISTORY"
        T_WH_METERING = "APP.V_WAREHOUSE_METERING_HISTORY"

        pkl_dict = {
            T_WH_EVENTS: "test/test_data/wh_usage_events.pkl",
            T_WH_LOADS: "test/test_data/wh_usage_loads.pkl",
            T_WH_METERING: "test/test_data/wh_usage_metering.pkl",
        }

        # -----------------------------------------------------

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            utils._pickle_data_history(session, T_WH_EVENTS, pkl_dict[T_WH_EVENTS])
            utils._pickle_data_history(session, T_WH_LOADS, pkl_dict[T_WH_LOADS])
            utils._pickle_data_history(session, T_WH_METERING, pkl_dict[T_WH_METERING])

        class TestWarehouseUsagePlugin(WarehouseUsagePlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestWarehouseUsagePlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_warehouse_usage", logging.INFO, show_detailed_logs=1)


if __name__ == "__main__":
    test_class = TestWhUsage()
    test_class.test_wh_usage()

#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
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
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_warehouse_usage", logging.INFO, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestWhUsage()
    test_class.test_wh_usage()

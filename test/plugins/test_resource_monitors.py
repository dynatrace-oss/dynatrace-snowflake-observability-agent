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
class TestResMon:
    def test_res_mon(self):
        import logging

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        T_DATA_RESMON = "APP.V_RESOURCE_MONITORS"
        T_DATA_WHS = "APP.V_WAREHOUSES"
        pkl_dict = {T_DATA_RESMON: "test/test_data/resource_monitors.pkl", T_DATA_WHS: "test/test_data/warehouses.pkl"}

        # ======================================================================

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            session.call("APP.P_REFRESH_RESOURCE_MONITORS", log_on_exception=True)
            utils._pickle_data_history(
                session, T_DATA_RESMON, pkl_dict[T_DATA_RESMON], lambda df: df.sort("IS_ACCOUNT_LEVEL", ascending=False)
            )
            utils._pickle_data_history(session, T_DATA_WHS, pkl_dict[T_DATA_WHS])

        class TestResourceMonitorsPlugin(ResourceMonitorsPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestResourceMonitorsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_resource_monitors", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestResMon()
    test_class.test_res_mon()

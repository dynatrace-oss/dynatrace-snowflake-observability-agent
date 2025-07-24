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
class TestDataVol:
    def test_data_vol(self):
        from typing import Dict, Generator
        from dtagent.plugins.data_volume import DataVolumePlugin
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        PICKLE_NAME = "test/test_data/data_volume.pkl"
        T_DATA = "APP.V_DATA_VOLUME"
        # ======================================================================

        if utils.should_pickle([PICKLE_NAME]):
            utils._pickle_data_history(_get_session(), T_DATA, PICKLE_NAME)

        class TestDataVolumePlugin(DataVolumePlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME, limit=2)

        def __local_get_plugin_class(source: str):
            return TestDataVolumePlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        import logging

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_data_volume", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestDataVol()
    test_class.test_data_vol()

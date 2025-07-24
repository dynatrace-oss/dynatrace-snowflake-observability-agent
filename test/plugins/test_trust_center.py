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
class TestTrustCenter:
    def test_trust_center(self):

        from typing import Generator, Dict
        import logging
        from test import TestDynatraceSnowAgent, _get_session
        import test._utils as utils
        from dtagent.plugins.trust_center import TrustCenterPlugin
        from dtagent import plugins

        T_DATA_TRUST_CENTER = "APP.V_TRUST_CENTER"
        PICKLE_NAME_TRUST_CENTER = "test/test_data/trust_center_hist.pkl"
        # -----------------------------------------------------

        if utils.should_pickle([PICKLE_NAME_TRUST_CENTER]):
            utils._pickle_data_history(_get_session(), T_DATA_TRUST_CENTER, PICKLE_NAME_TRUST_CENTER)

        class TestTrustCenterPlugin(TrustCenterPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME_TRUST_CENTER, limit=2)

        def __local_get_plugin_class(source: str):
            return TestTrustCenterPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_trust_center", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestTrustCenter()
    test_class.test_trust_center()

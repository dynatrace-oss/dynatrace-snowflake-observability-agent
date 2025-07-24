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
class TestShares:
    def test_shares(self):
        import logging

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.shares import SharesPlugin

        T_DATA_INBOUND = "APP.V_INBOUND_SHARE_TABLES"
        T_DATA_OUTBOUND = "APP.V_OUTBOUND_SHARE_TABLES"
        T_SHARE_DATA = "APP.V_SHARE_EVENTS"
        pkl_dict = {
            T_DATA_INBOUND: "test/test_data/inbound_shares.pkl",
            T_DATA_OUTBOUND: "test/test_data/outbound_shares.pkl",
            T_SHARE_DATA: "test/test_data/shares.pkl",
        }

        # ======================================================================

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            session.call("APP.P_GET_SHARES", log_on_exception=True)
            utils._pickle_data_history(session, T_DATA_INBOUND, pkl_dict[T_DATA_INBOUND])
            utils._pickle_data_history(session, T_DATA_OUTBOUND, pkl_dict[T_DATA_OUTBOUND])
            utils._pickle_data_history(session, T_SHARE_DATA, pkl_dict[T_SHARE_DATA])

        class TestSharesPlugin(SharesPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestSharesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_shares", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestShares()
    test_class.test_shares()

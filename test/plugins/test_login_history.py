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
class TestLoginHist:
    def test_login_hist(self):
        import logging
        from typing import Dict, Generator
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.login_history import LoginHistoryPlugin

        T_DATA_LOGINH = "APP.V_LOGIN_HISTORY"
        T_DATA_SESSIONS = "APP.V_SESSIONS"
        pkl_dict = {T_DATA_LOGINH: "test/test_data/login_history.pkl", T_DATA_SESSIONS: "test/test_data/sessions.pkl"}

        # ======================================================================

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            utils._pickle_data_history(session, T_DATA_LOGINH, pkl_dict[T_DATA_LOGINH])
            utils._pickle_data_history(session, T_DATA_SESSIONS, pkl_dict[T_DATA_SESSIONS])

        class TestLoginHistoryPlugin(LoginHistoryPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestLoginHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_login_history", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestLoginHist()
    test_class.test_login_hist()

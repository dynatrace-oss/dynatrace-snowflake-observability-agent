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
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_shares", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestShares()
    test_class.test_shares()

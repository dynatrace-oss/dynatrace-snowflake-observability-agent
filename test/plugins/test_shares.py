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
    import pytest

    PICKLES = {
        "APP.V_INBOUND_SHARE_TABLES": "test/test_data/inbound_shares.pkl",
        "APP.V_OUTBOUND_SHARE_TABLES": "test/test_data/outbound_shares.pkl",
        "APP.V_SHARE_EVENTS": "test/test_data/shares.pkl",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_shares(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.shares import SharesPlugin

        # ======================================================================

        if utils.should_pickle(self.PICKLES.values()):
            session = _get_session()
            session.call("APP.P_GET_SHARES", log_on_exception=True)
            utils._pickle_all(session, self.PICKLES, force=True)

        class TestSharesPlugin(SharesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestShares.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestSharesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session, utils.get_config()), "test_shares", logging.INFO, False)


if __name__ == "__main__":
    test_class = TestShares()
    test_class.test_shares()

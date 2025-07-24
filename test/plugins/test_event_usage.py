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
class TestEventUsage:
    def test_event_usage(self):
        import test._utils as utils
        import logging
        from test import _get_session, TestDynatraceSnowAgent

        from dtagent.plugins.event_usage import EventUsagePlugin
        from typing import Generator, Dict

        T_EVENT_USAGE_HIST = "APP.V_EVENT_USAGE_HISTORY"
        PICKLE_NAME = "test/test_data/event_usage.pkl"

        # ======================================================================

        if utils.should_pickle([PICKLE_NAME]):
            utils._pickle_data_history(_get_session(), T_EVENT_USAGE_HIST, PICKLE_NAME)

        class TestEventUsagePlugin(EventUsagePlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME, limit=2)

        def __local_get_plugin_class(source: str):
            return TestEventUsagePlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_event_usage", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestEventUsage()
    test_class.test_event_usage()

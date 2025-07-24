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
class TestEventLog:
    def test_event_log(self):
        import logging
        from typing import Dict, Generator

        from test import _get_session, TestDynatraceSnowAgent

        from dtagent.plugins.event_log import EventLogPlugin
        import test._utils as utils

        PICKLE_NAME = "test/test_data/event_log.pkl"
        PICKLE_NAME_METRICS = "test/test_data/event_log_metrics.pkl"
        PICKLE_NAME_SPANS = "test/test_data/event_log_spans.pkl"

        T_DATA = "APP.V_EVENT_LOG"
        T_DATA_METRICS = "APP.V_EVENT_LOG_METRICS_INSTRUMENTED"
        T_DATA_SPANS = "APP.V_EVENT_LOG_SPANS_INSTRUMENTED"

        pkl_dict = {T_DATA: PICKLE_NAME, T_DATA_METRICS: PICKLE_NAME_METRICS, T_DATA_SPANS: PICKLE_NAME_SPANS}
        # ======================================================================

        if utils.should_pickle([PICKLE_NAME, PICKLE_NAME_METRICS, PICKLE_NAME_SPANS]):
            utils._pickle_data_history(_get_session(), T_DATA, PICKLE_NAME)
            utils._pickle_data_history(_get_session(), T_DATA_METRICS, PICKLE_NAME_METRICS)
            utils._pickle_data_history(_get_session(), T_DATA_SPANS, PICKLE_NAME_SPANS)

        class TestEventLogPlugin(EventLogPlugin):

            def _get_events(self) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME, limit=2)

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

            def process(self, run_proc: bool = True) -> int:
                logging.debug("EXECUTING TestEventLogPlugin.process()")
                return super().process(run_proc)

        def __local_get_plugin_class(source: str):
            return TestEventLogPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_event_log", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestEventLog()
    test_class.test_event_log()

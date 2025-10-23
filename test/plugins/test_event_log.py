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
    import pytest

    PICKLES = {
        "APP.V_EVENT_LOG": "test/test_data/event_log.pkl",
        "APP.V_EVENT_LOG_METRICS_INSTRUMENTED": "test/test_data/event_log_metrics.pkl",
        "APP.V_EVENT_LOG_SPANS_INSTRUMENTED": "test/test_data/event_log_spans.pkl",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_event_log(self):
        import logging
        from unittest.mock import patch
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Dict, Generator

        from dtagent.plugins.event_log import EventLogPlugin

        # ======================================================================

        utils._pickle_all(_get_session(), self.PICKLES)

        class TestEventLogPlugin(EventLogPlugin):
            def _get_events(self) -> Generator[Dict, None, None]:
                return self._get_table_rows("APP.V_EVENT_LOG")

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestEventLog.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestEventLogPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session, utils.get_config()), "test_event_log", logging.INFO, False)


if __name__ == "__main__":
    test_class = TestEventLog()
    test_class.test_event_log()

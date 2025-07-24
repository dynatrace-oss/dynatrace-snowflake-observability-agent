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
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_event_log", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestEventLog()
    test_class.test_event_log()

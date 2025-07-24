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
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_event_usage", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestEventUsage()
    test_class.test_event_usage()

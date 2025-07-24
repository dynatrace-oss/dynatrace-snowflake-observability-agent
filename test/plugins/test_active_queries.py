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
class TestActiveQueries:
    def test_active_queries(self):
        import logging

        from typing import Dict, Generator
        from dtagent.plugins.active_queries import ActiveQueriesPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        T_ACTIVE_QUERIES = "SELECT * FROM TABLE(APP.F_ACTIVE_QUERIES_INSTRUMENTED())"
        PKL_ACTIVE_QUERIES = "test/test_data/active_queries.pkl"

        # ======================================================================

        if utils.should_pickle([PKL_ACTIVE_QUERIES]):
            session = _get_session()
            utils._pickle_data_history(session, T_ACTIVE_QUERIES, PKL_ACTIVE_QUERIES)

        class TestActiveQueriesPlugin(ActiveQueriesPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PKL_ACTIVE_QUERIES, limit=2)

        def __local_get_plugin_class(source: str):
            return TestActiveQueriesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_active_queries", logging.DEBUG, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestActiveQueries()
    test_class.test_active_queries()

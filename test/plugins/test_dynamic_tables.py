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
class TestDynamicTables:
    def test_dynamic_tables(self):
        import logging

        from typing import Dict, Generator
        from dtagent.plugins.dynamic_tables import DynamicTablesPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        T_DYNAMIC_TABLES = "APP.V_DYNAMIC_TABLES_INSTRUMENTED"
        T_DYNAMIC_TABLE_REFRESH_HISTORY = "APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED"
        T_DYNAMIC_TABLE_GRAPH_HISTORY = "APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED"

        pkl_dict = {
            T_DYNAMIC_TABLES: "test/test_data/dynamic_tables.pkl",
            T_DYNAMIC_TABLE_REFRESH_HISTORY: "test/test_data/dynamic_table_refresh_history.pkl",
            T_DYNAMIC_TABLE_GRAPH_HISTORY: "test/test_data/dynamic_table_graph_history.pkl",
        }

        # ======================================================================

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            utils._pickle_data_history(session, T_DYNAMIC_TABLES, pkl_dict[T_DYNAMIC_TABLES])
            utils._pickle_data_history(
                session, T_DYNAMIC_TABLE_REFRESH_HISTORY, pkl_dict[T_DYNAMIC_TABLE_REFRESH_HISTORY]
            )
            utils._pickle_data_history(session, T_DYNAMIC_TABLE_GRAPH_HISTORY, pkl_dict[T_DYNAMIC_TABLE_GRAPH_HISTORY])

        class TestDynamicTablesPlugin(DynamicTablesPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestDynamicTablesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_dynamic_tables", logging.DEBUG, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestDynamicTables()
    test_class.test_dynamic_tables()

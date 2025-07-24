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
            utils._pickle_data_history(session, T_DYNAMIC_TABLE_REFRESH_HISTORY, pkl_dict[T_DYNAMIC_TABLE_REFRESH_HISTORY])
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

        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_dynamic_tables", logging.DEBUG, show_detailed_logs=1)


if __name__ == "__main__":
    test_class = TestDynamicTables()
    test_class.test_dynamic_tables()

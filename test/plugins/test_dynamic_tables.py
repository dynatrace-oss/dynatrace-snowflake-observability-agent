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
    import pytest

    PICKLES = {
        "APP.V_DYNAMIC_TABLES_INSTRUMENTED": "test/test_data/dynamic_tables.pkl",
        "APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED": "test/test_data/dynamic_table_refresh_history.pkl",
        "APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED": "test/test_data/dynamic_table_graph_history.pkl",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_dynamic_tables(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator
        from dtagent.plugins.dynamic_tables import DynamicTablesPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        # ======================================================================

        utils._pickle_all(_get_session(), self.PICKLES)

        class TestDynamicTablesPlugin(DynamicTablesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestDynamicTables.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestDynamicTablesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        utils._logging_findings(session, TestDynatraceSnowAgent(session, utils.get_config()), "test_dynamic_tables", logging.DEBUG, True)


if __name__ == "__main__":
    test_class = TestDynamicTables()
    test_class.test_dynamic_tables()

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
class TestBudgets:
    def test_budgets(self):
        from typing import Dict, Generator
        from dtagent.plugins.budgets import BudgetsPlugin
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        T_BUDGET_DATA = "APP.V_BUDGET_DETAILS"
        T_SPENDINGS_DATA = "APP.V_BUDGET_SPENDINGS"
        pkl_dict = {
            T_BUDGET_DATA: "test/test_data/budgets.pkl",
            T_SPENDINGS_DATA: "test/test_data/budget_spendings.pkl",
        }

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            session.call("APP.P_GET_BUDGETS", log_on_exception=True)
            utils._pickle_data_history(session, T_BUDGET_DATA, pkl_dict[T_BUDGET_DATA])
            utils._pickle_data_history(session, T_SPENDINGS_DATA, pkl_dict[T_SPENDINGS_DATA])

        class TestBudgetsPlugin(BudgetsPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name])

        def __local_get_plugin_class(source: str):
            return TestBudgetsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        import logging

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_budget", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestBudgets()
    test_class.test_budgets()

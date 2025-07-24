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
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_budget", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestBudgets()
    test_class.test_budgets()

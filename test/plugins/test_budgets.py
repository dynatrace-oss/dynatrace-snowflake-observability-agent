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
    PICKLES = {
        "APP.V_BUDGET_DETAILS": "test/test_data/budgets.pkl",
        "APP.V_BUDGET_SPENDINGS": "test/test_data/budget_spendings.pkl",
    }

    def test_budgets(self):
        from unittest.mock import patch
        from typing import Dict, Generator
        from dtagent.plugins.budgets import BudgetsPlugin
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        if utils.should_pickle(self.PICKLES.values()):
            session = _get_session()
            session.call("APP.P_GET_BUDGETS", log_on_exception=True)
            utils._pickle_all(session, self.PICKLES, force=True)

        class TestBudgetsPlugin(BudgetsPlugin):
            @patch("dtagent.otel.events.requests.post")
            @patch("dtagent.otel.bizevents.requests.post")
            def process(self, run_proc: bool = True, mock_bizevents_post=None, mock_events_post=None) -> int:
                from dtagent.otel.otel_manager import OtelManager

                OtelManager.reset_current_fail_count()
                mock_events_post.side_effect = utils.side_effect_function
                mock_bizevents_post.side_effect = utils.side_effect_function
                logging.debug("EXECUTING TestBudgetsPlugin.process()")
                return super().process(run_proc)

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestBudgets.PICKLES, t_data)

        def __local_get_plugin_class(source: str):
            return TestBudgetsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        import logging

        session = _get_session()
        utils._logging_findings(
            session, TestDynatraceSnowAgent(session, utils.get_config()), "test_budget", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestBudgets()
    test_class.test_budgets()

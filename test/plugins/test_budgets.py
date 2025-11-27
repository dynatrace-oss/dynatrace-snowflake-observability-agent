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
    import pytest

    PICKLES = {
        "APP.V_BUDGET_DETAILS": "test/test_data/budgets.pkl",
        "APP.V_BUDGET_SPENDINGS": "test/test_data/budget_spendings.pkl",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
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

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestBudgets.PICKLES, t_data)

        def __local_get_plugin_class(source: str):
            return TestBudgetsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        disabled_combinations = [
            [],
            ["metrics"],
            ["logs"],
            ["events"],
            ["logs", "metrics"],
            ["logs", "spans", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_budget",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "budgets": {"entries": 1, "log_lines": 1, "metrics": 1, "events": 1},
                    "spendings": {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0},
                },
            )


if __name__ == "__main__":
    test_class = TestBudgets()
    test_class.test_budgets()

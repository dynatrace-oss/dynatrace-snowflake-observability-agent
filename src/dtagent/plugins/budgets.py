"""
Plugin file for processing budgets plugin data.
"""

##region ------------------------------ IMPORTS  -----------------------------------------
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

from typing import Tuple, Dict
from snowflake.snowpark.functions import current_timestamp
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE


##region ------------------ MEASUREMENT SOURCE: BUDGETS --------------------------------
class BudgetsPlugin(Plugin):
    """
    Budgets plugin class.
    """

    def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        Processes data for budgets plugin.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
                {
                "dsoa.run.results": {
                    "budgets":
                    {
                        "entries": budgets_cnt,
                        "log_lines": logs_budgets_cnt,
                        "metrics": budgets_metrics_cnt,
                        "events": budgets_events_cnt,
                    },
                    "spendings":
                    {
                        "entries": spendings_cnt,
                        "log_lines": logs_spendings_cnt,
                        "metrics": spending_metrics_cnt,
                        "events": spending_events_cnt,
                    },
                },
                "dsoa.run.id": "uuid_string"
                }
        """

        budgets_cnt = 0
        p_refresh_budgets = "APP.P_GET_BUDGETS"

        t_get_budgets = "APP.V_BUDGET_DETAILS"
        t_budget_spending = "APP.V_BUDGET_SPENDINGS"

        if run_proc:
            # this procedure ensures that the budgets and spendings tables are up to date
            self._session.call(p_refresh_budgets)

        budgets_cnt, logs_budgets_cnt, budgets_metrics_cnt, budgets_events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_get_budgets),
            "budgets",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=False,
        )

        spendings_cnt, logs_spendings_cnt, spending_metrics_cnt, spending_events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_budget_spending),
            "budgets",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=False,
        )

        results_dict = {
            "budgets": {
                "entries": budgets_cnt,
                "log_lines": logs_budgets_cnt,
                "metrics": budgets_metrics_cnt,
                "events": budgets_events_cnt,
            },
            "spendings": {
                "entries": spendings_cnt,
                "log_lines": logs_spendings_cnt,
                "metrics": spending_metrics_cnt,
                "events": spending_events_cnt,
            },
        }

        if run_proc:
            self._report_execution("budgets", current_timestamp(), None, results_dict, run_id=run_id)

        return {RUN_PLUGIN_KEY: "budgets", RUN_RESULTS_KEY: results_dict, RUN_ID_KEY: run_id}

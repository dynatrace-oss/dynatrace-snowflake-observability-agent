"""
Plugin file for processing budgets plugin data.
"""

##region ------------------------------ IMPORTS  -----------------------------------------
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

import uuid
from typing import Tuple
from snowflake.snowpark.functions import current_timestamp
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE


##region ------------------ MEASUREMENT SOURCE: BUDGETS --------------------------------
class BudgetsPlugin(Plugin):
    """
    Budgets plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes data for budgets plugin.
        Returns:
            processed_budgets [int]: number of entries reported from APP.V_BUDGET_DETAILS,
            processed_spendings [int]: number of entries reported from APP.V_BUDGET_SPENDINGS,
            processed_budgets_metrics [int]: number of metrics reported from APP.V_BUDGET_DETAILS,
            processed_spending_metrics [int]: number of metrics reported from APP.V_BUDGET_SPENDINGS.
        """

        processed_budgets = 0
        processed_spendings = 0
        processed_budgets_metrics = 0
        processed_spending_metrics = 0
        p_refresh_budgets = "APP.P_GET_BUDGETS"

        t_get_budgets = "APP.V_BUDGET_DETAILS"
        t_budget_spending = "APP.V_BUDGET_SPENDINGS"

        if run_proc:
            # this procedure ensures that the budgets and spendings tables are up to date
            self._session.call(p_refresh_budgets)

        run_id = str(uuid.uuid4().hex)

        processed_budgets, _, processed_budgets_metrics, processed_budgets_events = self._log_entries(
            lambda: self._get_table_rows(t_get_budgets),
            "budgets",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=False,
        )

        processed_spendings, _, processed_spending_metrics, processed_spending_events = self._log_entries(
            lambda: self._get_table_rows(t_budget_spending),
            "budgets",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=False,
        )
        if run_proc:
            self._report_execution(
                "budgets",
                current_timestamp(),
                None,
                {
                    "processed_budgets": processed_budgets,
                    "processed_spending_entries": processed_spendings,
                    "processed_budgets_metrics": processed_budgets_metrics,
                    "processed_spending_metrics": processed_spending_metrics,
                    "processed_budgets_events": processed_budgets_events,
                    "processed_spending_events": processed_spending_events,
                },
            )

        return processed_budgets, processed_spendings, processed_budgets_metrics, processed_spending_metrics

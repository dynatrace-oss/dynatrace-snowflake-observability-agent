"""
Plugin file for processing active queries plugin data.
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
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: ACTIVE QUERIES --------------------------------


class ActiveQueriesPlugin(Plugin):
    """
    Active queries plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes the measures on active queries
        """
        t_active_queries = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED())"

        active_queries_cnt = self._log_entries(
            lambda: self._get_table_rows(t_active_queries),
            "active_queries",
            report_timestamp_events=False,
            report_metrics=True,
            log_completion=run_proc,
        )[0]

        return active_queries_cnt


##endregion

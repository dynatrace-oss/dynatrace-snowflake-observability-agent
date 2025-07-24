"""
Plugin file for processing dynamic tables plugin data.
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

##region ------------------ MEASUREMENT SOURCE: DYNAMIC TABLES --------------------------------


class DynamicTablesPlugin(Plugin):
    """
    Dynamic tables plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes the measures on dynamic tables
        """
        t_dynamic_tables = "APP.V_DYNAMIC_TABLES_INSTRUMENTED"
        t_dynamic_table_refresh_history = "APP.V_DYNAMIC_TABLE_REFRESH_HISTORY_INSTRUMENTED"
        t_dynamic_table_graph_history = "APP.V_DYNAMIC_TABLE_GRAPH_HISTORY_INSTRUMENTED"

        run_id = str(uuid.uuid4().hex)

        (entries_cnt, logs_cnt, metrics_cnt, event_cnt) = self._log_entries(
            lambda: self._get_table_rows(t_dynamic_tables),
            "dynamic_tables",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        (entries_refresh_cnt, logs_refresh_cnt, metrics_refresh_cnt, event_refresh_cnt) = self._log_entries(
            lambda: self._get_table_rows(t_dynamic_table_refresh_history),
            "dynamic_table_refresh_history",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        (entries_graph_cnt, logs_graph_cnt, metrics_graph_cnt, event_graph_cnt) = self._log_entries(
            lambda: self._get_table_rows(t_dynamic_table_graph_history),
            "dynamic_table_graph_history",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        return (
            entries_cnt + entries_refresh_cnt + entries_graph_cnt,
            logs_cnt + logs_refresh_cnt + logs_graph_cnt,
            metrics_cnt + metrics_refresh_cnt + metrics_graph_cnt,
            event_cnt + event_refresh_cnt + event_graph_cnt,
        )


##endregion

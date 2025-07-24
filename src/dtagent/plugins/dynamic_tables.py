"""
Plugin file for processing dynamic tables plugin data.
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

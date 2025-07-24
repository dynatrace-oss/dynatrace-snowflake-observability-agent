"""
Plugin file for processing tasks plugin data.
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
from src.dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: SERVERLESS TASKS --------------------------------


class TasksPlugin(Plugin):
    """
    Tasks plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes the measures on serverless tasks, task history and task versions.
        Returns number of processed: serverless tasks, serverless task metrics, entries in task history, entries in task versions - in this order.
        """

        task_history_entries_cnt = 0
        task_versions_entries_cnt = 0
        serverless_task_history_entries_cnt = 0

        t_serverless_task = "APP.V_SERVERLESS_TASKS"
        t_task_hist = "APP.V_TASK_HISTORY"
        t_task_versions = "APP.V_TASK_VERSIONS"

        run_id = str(uuid.uuid4().hex)

        (
            serverless_task_history_entries_cnt,
            _,
            serverless_tasks_metrics_cnt,
            _,
        ) = self._log_entries(
            lambda: self._get_table_rows(t_serverless_task),
            "serverless_tasks",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        task_versions_entries_cnt = self._log_entries(
            lambda: self._get_table_rows(t_task_versions),
            "task_versions",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        task_history_entries_cnt = self._log_entries(
            lambda: self._get_table_rows(t_task_hist),
            "task_history",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        return (
            serverless_task_history_entries_cnt,
            serverless_tasks_metrics_cnt,
            task_history_entries_cnt,
            task_versions_entries_cnt,
        )


##endregion

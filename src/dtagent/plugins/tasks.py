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
from typing import Tuple, Dict
from src.dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: SERVERLESS TASKS --------------------------------


class TasksPlugin(Plugin):
    """
    Tasks plugin class.
    """

    def process(self, run_proc: bool = True) -> Dict[str, int]:
        """
        Processes the measures on serverless tasks, task history and task versions.
        Returns:
            Dict[str,int]: A dictionary with telemetry counts for tasks.

            Example:
            {
                "serverless_tasks": {
                    "entries": serverless_tasks_entries_cnt,
                    "logs": serverless_task_logs_cnt,
                    "metrics": serverless_tasks_metrics_cnt,
                    "events": serverless_tasks_events_cnt,
                },
                "task_versions": {
                    "entries": task_versions_entries_cnt,
                    "logs": task_versions_logs_cnt,
                    "metrics": task_versions_metrics_cnt,
                    "events": task_versions_events_cnt,
                },
                "task_history": {
                    "entries": task_history_entries_cnt,
                    "logs": task_history_logs_cnt,
                    "metrics": task_history_metrics_cnt,
                    "events": task_history_events_cnt,
                },
            }
        """

        t_serverless_task = "APP.V_SERVERLESS_TASKS"
        t_task_hist = "APP.V_TASK_HISTORY"
        t_task_versions = "APP.V_TASK_VERSIONS"

        run_id = str(uuid.uuid4().hex)

        (
            serverless_tasks_entries_cnt,
            serverless_task_logs_cnt,
            serverless_tasks_metrics_cnt,
            serverless_tasks_events_cnt,
        ) = self._log_entries(
            lambda: self._get_table_rows(t_serverless_task),
            "serverless_tasks",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        (
            task_versions_entries_cnt,
            task_versions_logs_cnt,
            task_versions_metrics_cnt,
            task_versions_events_cnt,
        ) = self._log_entries(
            lambda: self._get_table_rows(t_task_versions),
            "task_versions",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        (
            task_history_entries_cnt,
            task_history_logs_cnt,
            task_history_metrics_cnt,
            task_history_events_cnt,
        ) = self._log_entries(
            lambda: self._get_table_rows(t_task_hist),
            "task_history",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        return {
            "serverless_tasks": {
                "entries": serverless_tasks_entries_cnt,
                "logs": serverless_task_logs_cnt,
                "metrics": serverless_tasks_metrics_cnt,
                "events": serverless_tasks_events_cnt,
            },
            "task_versions": {
                "entries": task_versions_entries_cnt,
                "logs": task_versions_logs_cnt,
                "metrics": task_versions_metrics_cnt,
                "events": task_versions_events_cnt,
            },
            "task_history": {
                "entries": task_history_entries_cnt,
                "logs": task_history_logs_cnt,
                "metrics": task_history_metrics_cnt,
                "events": task_history_events_cnt,
            },
        }


##endregion

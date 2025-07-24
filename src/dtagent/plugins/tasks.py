"""
Plugin file for processing tasks plugin data.
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

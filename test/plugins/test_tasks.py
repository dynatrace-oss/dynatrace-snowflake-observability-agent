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
class TestTasks:
    def test_tasks(self):
        from typing import Generator, Dict

        from test import TestDynatraceSnowAgent, _get_session
        import test._utils as utils

        from dtagent.plugins.tasks import TasksPlugin
        from dtagent import plugins

        T_SERVERLESS_TASKS = "APP.V_SERVERLESS_TASKS"
        T_TASK_HISTORY = "APP.V_TASK_HISTORY"
        T_TASK_VERSIONS = "APP.V_TASK_VERSIONS"

        pkl_dict = {
            T_SERVERLESS_TASKS: "test/test_data/tasks_serverless.pkl",
            T_TASK_HISTORY: "test/test_data/tasks_history.pkl",
            T_TASK_VERSIONS: "test/test_data/tasks_versions.pkl",
        }
        # -----------------------------------------------------

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            utils._pickle_data_history(session, T_SERVERLESS_TASKS, pkl_dict[T_SERVERLESS_TASKS])
            utils._pickle_data_history(session, T_TASK_HISTORY, pkl_dict[T_TASK_HISTORY])
            utils._pickle_data_history(session, T_TASK_VERSIONS, pkl_dict[T_TASK_VERSIONS])

        class TestTasksPlugin(TasksPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestTasksPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        import logging

        utils._logging_findings(
            session, TestDynatraceSnowAgent(session), "test_tasks", logging.INFO, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestTasks()
    test_class.test_tasks()

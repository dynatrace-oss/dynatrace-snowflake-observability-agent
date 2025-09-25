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
class TestTasks:
    PICKLES = {
        "APP.V_SERVERLESS_TASKS": "test/test_data/tasks_serverless.pkl",
        "APP.V_TASK_HISTORY": "test/test_data/tasks_history.pkl",
        "APP.V_TASK_VERSIONS": "test/test_data/tasks_versions.pkl",
    }

    def test_tasks(self):
        from typing import Generator, Dict

        from unittest.mock import patch
        from test import TestDynatraceSnowAgent, _get_session
        import test._utils as utils

        from dtagent.plugins.tasks import TasksPlugin
        from dtagent import plugins

        # -----------------------------------------------------

        utils._pickle_all(_get_session(), self.PICKLES)

        class TestTasksPlugin(TasksPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestTasks.PICKLES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestTasksPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        session = _get_session()

        import logging

        utils._logging_findings(
            session, TestDynatraceSnowAgent(session, utils.get_config()), "test_tasks", logging.INFO, show_detailed_logs=1
        )


if __name__ == "__main__":
    test_class = TestTasks()
    test_class.test_tasks()

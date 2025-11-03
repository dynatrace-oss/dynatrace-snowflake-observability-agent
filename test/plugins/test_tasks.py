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
    import pytest

    PICKLES = {
        "APP.V_SERVERLESS_TASKS": "test/test_data/tasks_serverless.pkl",
        "APP.V_TASK_HISTORY": "test/test_data/tasks_history.pkl",
        "APP.V_TASK_VERSIONS": "test/test_data/tasks_versions.pkl",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
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

        disabled_combinations = [
            [],
            ["logs"],
            ["events"],
            ["metrics"],
            ["logs", "events"],
            ["metrics", "events"],
            ["logs", "events", "metrics"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_tasks",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "serverless_tasks": {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0},
                    "task_versions": {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0},
                    "task_history": {"entries": 2, "log_lines": 2, "metrics": 0, "events": 0},
                },
            )


if __name__ == "__main__":
    test_class = TestTasks()
    test_class.test_tasks()

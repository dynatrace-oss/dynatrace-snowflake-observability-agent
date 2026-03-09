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
class TestUsers:
    import pytest

    FIXTURES = {
        "APP.V_USERS_INSTRUMENTED": "test/test_data/users_history.ndjson",
        "APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED": "test/test_data/users_all_privileges.ndjson",
        "APP.V_USERS_ALL_ROLES_INSTRUMENTED": "test/test_data/users_all_roles.ndjson",
        "APP.V_USERS_DIRECT_ROLES_INSTRUMENTED": "test/test_data/users_roles_direct.ndjson",
        "APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED": "test/test_data/users_roles_direct_removed.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_users(self):

        import logging

        from unittest.mock import patch
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from dtagent.plugins.users import UsersPlugin
        from dtagent import plugins
        import test._utils as utils

        # -----------------------------------------------------

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_GET_USERS", log_on_exception=True)
            utils._generate_all_fixtures(session, self.FIXTURES, force=True)

        class TestUsersPlugin(UsersPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                for r in utils._safe_get_fixture_entries(TestUsers.FIXTURES, t_data, limit=2):
                    print(f"USER DATA at {t_data}: {r}")
                    yield r

        def __local_get_plugin_class(source: str):
            return TestUsersPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["logs"],
            ["events"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_users",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs"],
                base_count={
                    "users": {"entries": 2, "events": 5, "log_lines": 2},
                    "users_direct_roles": {"entries": 2, "events": 2, "log_lines": 2},
                    "users_removed_direct_roles": {"entries": 2, "events": 2, "log_lines": 2},
                    "users_all_roles": {"entries": 2, "events": 2, "log_lines": 2},
                    "users_all_privileges": {"entries": 2, "events": 2, "log_lines": 2},
                },
            )


if __name__ == "__main__":
    test_class = TestUsers()
    test_class.test_users()

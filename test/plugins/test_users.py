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

    PICKLES = {
        "APP.V_USERS_INSTRUMENTED": "test/test_data/users_hist.pkl",
        "APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED": "test/test_data/users_all_privileges.pkl",
        "APP.V_USERS_ALL_ROLES_INSTRUMENTED": "test/test_data/users_all_roles.pkl",
        "APP.V_USERS_DIRECT_ROLES_INSTRUMENTED": "test/test_data/users_roles_direct.pkl",
        "APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED": "test/test_data/users_roles_direct_removed.pkl",
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

        if utils.should_pickle(self.PICKLES.values()):
            session = _get_session()
            session.call("APP.P_GET_USERS", log_on_exception=True)
            utils._pickle_all(session, self.PICKLES, force=True)

        class TestUsersPlugin(UsersPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                for r in utils._safe_get_unpickled_entries(TestUsers.PICKLES, t_data, limit=2):
                    print(f"USER DATA at {t_data}: {r}")
                    yield r

        def __local_get_plugin_class(source: str):
            return TestUsersPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session, utils.get_config()), "test_users", logging.INFO, False)


if __name__ == "__main__":
    test_class = TestUsers()
    test_class.test_users()

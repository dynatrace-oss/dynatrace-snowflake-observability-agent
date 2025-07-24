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
    def test_users(self):

        import logging

        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from dtagent.plugins.users import UsersPlugin
        from dtagent import plugins
        import test._utils as utils

        BASE_PATH = "test/test_data"

        T_USERS_CORE = "APP.V_USERS_INSTRUMENTED"
        T_USERS_ALL_PRIVILEGES = "APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED"
        T_USERS_ALL_ROLES = "APP.V_USERS_ALL_ROLES_INSTRUMENTED"
        T_USERS_ROLE_DIRECT = "APP.V_USERS_DIRECT_ROLES_INSTRUMENTED"
        T_USERS_ROLE_DIRECT_REMOVED = "APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED"

        pkl_dict = {
            T_USERS_CORE: f"{BASE_PATH}/users_hist.pkl",
            T_USERS_ROLE_DIRECT_REMOVED: f"{BASE_PATH}/users_roles_direct_removed.pkl",
            T_USERS_ROLE_DIRECT: f"{BASE_PATH}/users_roles_direct.pkl",
            T_USERS_ALL_PRIVILEGES: f"{BASE_PATH}/users_all_privileges.pkl",
            T_USERS_ALL_ROLES: f"{BASE_PATH}/users_all_roles.pkl",
        }

        # -----------------------------------------------------

        if utils.should_pickle(list(pkl_dict.values())):
            session = _get_session()
            session.call("APP.P_GET_USERS", log_on_exception=True)
            for key, value in pkl_dict.items():
                utils._pickle_data_history(_get_session(), key, value)

        class TestUsersPlugin(UsersPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(pkl_dict[table_name], limit=2)

        def __local_get_plugin_class(source: str):
            return TestUsersPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_users", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestUsers()
    test_class.test_users()

"""
Plugin file for processing users plugin data.
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
from snowflake.snowpark.functions import current_timestamp
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: USERS --------------------------------

ROLE_REPORTING_MODES_VIEWS = {
    "DIRECT_ROLES": ["APP.V_USERS_DIRECT_ROLES_INSTRUMENTED", "APP.V_USERS_REMOVED_DIRECT_ROLES_INSTRUMENTED"],
    "ALL_ROLES": ["APP.V_USERS_ALL_ROLES_INSTRUMENTED"],
    "ALL_PRIVILEGES": ["APP.V_USERS_ALL_PRIVILEGES_INSTRUMENTED"],
}


class UsersPlugin(Plugin):
    """
    Users plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int]:
        """
        Processes data for users plugin.
        Returns
            processed_entries_cnt [int]: number of entries reported from desired views,
            processed_logs_cnt [int]: number of logs sent.
        """

        modes = self._configuration.get(plugin_name="users", key="roles_monitoring_mode", default_value=[])
        processed_entries_cnt = 0
        processed_logs_cnt = 0
        run_id = str(uuid.uuid4().hex)

        views_list = ["APP.V_USERS_INSTRUMENTED"]

        if run_proc:
            # this stored procedure will ensure that APP.TMP_USERS table is up to date
            self._session.call("APP.P_GET_USERS", log_on_exception=True)

        for mode in modes:
            views_list.extend(ROLE_REPORTING_MODES_VIEWS[str(mode).upper()])

        for view in views_list:
            entries, logs, _, _ = self._log_entries(
                lambda view=view: self._get_table_rows(view),
                "users",
                run_uuid=run_id,
                log_completion=False,
                report_timestamp_events=False,
            )

            processed_entries_cnt += entries
            processed_logs_cnt += logs

        if run_proc:
            self._report_execution(
                "users",
                current_timestamp() if processed_entries_cnt > 0 else None,
                None,
                {"processed_entries_cnt": processed_entries_cnt, "processed_logs_cnt": processed_logs_cnt},
            )

        return processed_entries_cnt, processed_logs_cnt


##endregion

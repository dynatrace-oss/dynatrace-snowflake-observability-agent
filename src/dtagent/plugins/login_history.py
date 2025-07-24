"""
Plugin file for processing login history plugin data.
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
from dtagent.otel.events import EventType
from dtagent.util import _unpack_payload
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: LOGIN HISTORY --------------------------------


class LoginHistoryPlugin(Plugin):
    """
    Login history plugin class.
    """

    def _prepare_event_payload_failed_login(self, row_dict: dict) -> Tuple[EventType, str, Dict]:
        """Defines what payload should be sent once error.code column is present in the row"""

        properties = _unpack_payload(row_dict)
        user = properties.get("db.user")
        error_message = properties.get("status.message")
        error_code = row_dict.get("error.code")
        payload = {
            "event.name": f"Detected failed logins to Snowflake by {user}",
            "event.description": f"We have detected a failed login attempt due to f{error_message} (code: {error_code}), by {user}",
            "db.user": properties.get("db.user"),
            "timeout": 360,
            "ad.source": "snowflake_security",
        }
        return EventType.CUSTOM_ALERT, "Failed login attempt", payload

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes the measures on login history.
        """
        t_sessions = "APP.V_SESSIONS"
        t_login_history = "APP.V_LOGIN_HISTORY"

        run_id = str(uuid.uuid4().hex)

        login_history_entries_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_login_history),
            context_name="login_history",
            run_uuid=run_id,
            log_completion=run_proc,
            start_time="TIMESTAMP",
            event_column_to_check="error.code",
            event_payload_prepare=self._prepare_event_payload_failed_login,
        )[0]

        sessions_entries_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_sessions),
            context_name="sessions",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        return login_history_entries_cnt, sessions_entries_cnt


##endregion

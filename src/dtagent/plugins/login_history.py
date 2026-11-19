"""Plugin file for processing login history plugin data."""

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

from typing import Dict, Optional, List
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: LOGIN HISTORY --------------------------------


class LoginHistoryPlugin(Plugin):
    """Login history plugin class."""

    PLUGIN_NAME = "login_history"
    PLUGIN_CONTEXTS: tuple = ("login_history", "sessions")

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes the measures on login history.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
            {
            "dsoa.run.results": {
                "login_history": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": event_cnt,
                },
                "sessions": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": event_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        results = {}

        if not contexts or "login_history" in contexts:
            t_login_history = "APP.V_LOGIN_HISTORY"
            login_history_entries_cnt, login_history_logs_cnt, login_history_metrics_cnt, login_history_events_cnt = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows(t_login_history),
                context_name="login_history",
                run_uuid=run_id,
                log_completion=run_proc,
                start_time="TIMESTAMP",
            )
            results["login_history"] = {
                "entries": login_history_entries_cnt,
                "log_lines": login_history_logs_cnt,
                "metrics": login_history_metrics_cnt,
                "events": login_history_events_cnt,
            }

        if not contexts or "sessions" in contexts:
            t_sessions = "APP.V_SESSIONS"
            sessions_entries_cnt, session_logs_cnt, session_metrics_cnt, session_events_cnt = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows(t_sessions),
                context_name="sessions",
                run_uuid=run_id,
                log_completion=run_proc,
            )
            results["sessions"] = {
                "entries": sessions_entries_cnt,
                "log_lines": session_logs_cnt,
                "metrics": session_metrics_cnt,
                "events": session_events_cnt,
            }

        return self._report_results(
            results,
            run_id,
        )


##endregion

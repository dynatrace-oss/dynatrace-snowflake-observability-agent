"""
Plugin file for processing shares plugin data.
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
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: SHARES --------------------------------


class SharesPlugin(Plugin):
    """
    Shares plugin class.
    """

    def process(self, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        Processes data for shares plugin.
        Returns:
            Dict[str,int]: A dictionary with telemetry counts for shares.

            Example:
            {
                "outbound_shares": {
                    "entries": outbound_share_entries_cnt,
                    "log_lines": outbound_share_logs_cnt,
                    "metrics": outbound_share_metrics_cnt,
                    "events": outbound_share_events_cnt,
                },
                "inbound_shares": {
                    "entries": inbound_share_entries_cnt,
                    "log_lines": inbound_share_logs_cnt,
                    "metrics": inbound_share_metrics_cnt,
                    "events": inbound_share_events_cnt,
                },
                "shares": {
                    "entries": shares_entries_cnt,
                    "log_lines": shares_logs_cnt,
                    "metrics": shares_metrics_cnt,
                    "events": shares_events_cnt,
                },
            }
        """

        t_outbound_shares = "APP.V_OUTBOUND_SHARE_TABLES"
        t_inbound_shares = "APP.V_INBOUND_SHARE_TABLES"
        t_share_events = "APP.V_SHARE_EVENTS"
        run_id = str(uuid.uuid4().hex)

        if run_proc:
            # call to list inbound and outbound shares to temporary tables
            self._session.call("APP.P_GET_SHARES", log_on_exception=True)

        (
            outbound_share_entries_cnt,
            outbound_share_logs_cnt,
            outbound_share_metrics_cnt,
            outbound_share_events_cnt,
        ) = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_outbound_shares),
            context_name="outbound_shares",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        (
            inbound_share_entries_cnt,
            inbound_share_logs_cnt,
            inbound_share_metrics_cnt,
            inbound_share_events_cnt,
        ) = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_inbound_shares),
            context_name="inbound_shares",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        (
            shares_entries_cnt,
            shares_logs_cnt,
            shares_metrics_cnt,
            shares_events_cnt,
        ) = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_share_events),
            context_name="shares",
            run_uuid=run_id,
            log_completion=run_proc,
            report_logs=False,
            report_metrics=False,
            report_timestamp_events=True,
        )

        return {
            "outbound_shares": {
                "entries": outbound_share_entries_cnt,
                "log_lines": outbound_share_logs_cnt,
                "metrics": outbound_share_metrics_cnt,
                "events": outbound_share_events_cnt,
            },
            "inbound_shares": {
                "entries": inbound_share_entries_cnt,
                "log_lines": inbound_share_logs_cnt,
                "metrics": inbound_share_metrics_cnt,
                "events": inbound_share_events_cnt,
            },
            "shares": {
                "entries": shares_entries_cnt,
                "log_lines": shares_logs_cnt,
                "metrics": shares_metrics_cnt,
                "events": shares_events_cnt,
            },
            "dsoa.run.id": run_id,
        }

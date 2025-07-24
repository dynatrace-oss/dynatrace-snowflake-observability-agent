"""
Plugin file for processing event usage plugin data.
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

from typing import Tuple
from dtagent.util import _unpack_json_dict
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: EVENT USAGE HISTORY --------------------------------


class EventUsagePlugin(Plugin):
    """
    Event usage plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int]:
        """
        Processes data for event usage plugin.
        Returns
            processed_entries_cnt [int]: number of entries reported from APP.V_EVENT_USAGE_HISTORY,
            processed_event_metrics_cnt [int]: number of metrics reported from APP.V_EVENT_USAGE_HISTORY.
        """

        t_event_usage = "APP.V_EVENT_USAGE_HISTORY"

        _context_name = "event_usage"
        __context = get_context_by_name(_context_name)

        processed_entries_cnt = 0
        processed_event_metrics_cnt = 0
        processed_timestamp = self._configuration.get_last_measurement_update(self._session, _context_name)

        for row_dict in self._get_table_rows(t_event_usage):
            unpacked_dict = _unpack_json_dict(row_dict, ["DIMENSIONS", "METRICS"])
            start_ts = row_dict.get("START_TIME")
            processed_timestamp = row_dict.get("END_TIME")
            self._logs.send_log(
                "Event Usage",
                extra={
                    "timestamp": start_ts,
                    "event.start": start_ts,
                    "event.end": processed_timestamp,
                    **unpacked_dict,
                },
                context=__context,
            )

            processed_entries_cnt += 1
            if self._metrics.discover_report_metrics(row_dict):
                processed_event_metrics_cnt += 1

        if run_proc:
            self._report_execution(
                "event_usage",
                str(processed_timestamp),
                None,
                {
                    "processed_event_usage_count": processed_entries_cnt,
                    "metrics_sent_count": processed_event_metrics_cnt,
                },
            )

        return processed_entries_cnt, processed_event_metrics_cnt

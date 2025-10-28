"""
Plugin file for processing warehouse usage plugin data.
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
from src.dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: WAREHOUSE USAGE --------------------------------


class WarehouseUsagePlugin(Plugin):
    """
    Warehouse usage plugin class.
    """

    def process(self, run_proc: bool = True) -> Dict[str, int]:
        """
        Processes data for warehouse usage plugin.
        Returns:
            Dict[str,int]: A dictionary with telemetry counts for warehouse usage.

            Example:
            {
                "warehouse_usage": {
                    "entries": entries_wh_events_cnt,
                    "logs": logs_wh_events_cnt,
                    "metrics": metrics_wh_events_cnt,
                    "events": events_wh_events_cnt,
                },
                "warehouse_usage_load": {
                    "entries": entries_wh_load_cnt,
                    "logs": logs_wh_load_cnt,
                    "metrics": metrics_wh_load_cnt,
                    "events": events_wh_load_cnt,
                },
                "warehouse_usage_metering": {
                    "entries": entries_wh_metering_cnt,
                    "logs": logs_wh_metering_cnt,
                    "metrics": metrics_wh_metering_cnt,
                    "events": events_wh_metering_cnt,
                },
            }
        """

        t_wh_events = "APP.V_WAREHOUSE_EVENT_HISTORY"
        t_wh_load_hist = "APP.V_WAREHOUSE_LOAD_HISTORY"
        t_wh_metering_hist = "APP.V_WAREHOUSE_METERING_HISTORY"

        run_id = str(uuid.uuid4().hex)

        entries_wh_events_cnt, logs_wh_events_cnt, metrics_wh_events_cnt, events_wh_events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_wh_events),
            "warehouse_usage",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        entries_wh_load_cnt, logs_wh_load_cnt, metrics_wh_load_cnt, events_wh_load_cnt = self._log_entries(
            lambda: self._get_table_rows(t_wh_load_hist),
            "warehouse_usage_load",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        entries_wh_metering_cnt, logs_wh_metering_cnt, metrics_wh_metering_cnt, events_wh_metering_cnt = self._log_entries(
            lambda: self._get_table_rows(t_wh_metering_hist),
            "warehouse_usage_metering",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        return {
            "warehouse_usage": {
                "entries": entries_wh_events_cnt,
                "logs": logs_wh_events_cnt,
                "metrics": metrics_wh_events_cnt,
                "events": events_wh_events_cnt,
            },
            "warehouse_usage_load": {
                "entries": entries_wh_load_cnt,
                "logs": logs_wh_load_cnt,
                "metrics": metrics_wh_load_cnt,
                "events": events_wh_load_cnt,
            },
            "warehouse_usage_metering": {
                "entries": entries_wh_metering_cnt,
                "logs": logs_wh_metering_cnt,
                "metrics": metrics_wh_metering_cnt,
                "events": events_wh_metering_cnt,
            },
        }

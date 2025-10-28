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

    def process(self, run_proc: bool = True) -> Dict[str, int]:  # FIXME
        """
        Processes data for warehouse usage plugin.
        Returns
            processed_wh_events_cnt [int]: number of entries reported from APP.V_WAREHOUSE_EVENT_HISTORY,
            processed_wh_load_cnt [int]: number of entries reported from APP.V_WAREHOUSE_LOAD_HISTORY,
            processed_wh_metering_cnt [int]: number of entries reported from APP.V_WAREHOUSE_METERING_HISTORY,
            wh_metering_metrics_cnt [int]: number of metrics reported from APP.V_WAREHOUSE_METERING_HISTORY.
        """

        processed_wh_events_cnt = 0
        processed_wh_load_cnt = 0
        processed_wh_metering_cnt = 0

        t_wh_events = "APP.V_WAREHOUSE_EVENT_HISTORY"
        t_wh_load_hist = "APP.V_WAREHOUSE_LOAD_HISTORY"
        t_wh_metering_hist = "APP.V_WAREHOUSE_METERING_HISTORY"

        run_id = str(uuid.uuid4().hex)

        processed_wh_events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_wh_events),
            "warehouse_usage",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        processed_wh_load_cnt, _, wh_load_metrics_cnt, _ = self._log_entries(
            lambda: self._get_table_rows(t_wh_load_hist),
            "warehouse_usage_load",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        processed_wh_metering_cnt, _, wh_metering_metrics_cnt, _ = self._log_entries(
            lambda: self._get_table_rows(t_wh_metering_hist),
            "warehouse_usage_metering",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        return (
            processed_wh_events_cnt,
            processed_wh_load_cnt,
            wh_load_metrics_cnt,
            processed_wh_metering_cnt,
            wh_metering_metrics_cnt,
        )

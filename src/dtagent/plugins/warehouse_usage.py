"""
Plugin file for processing warehouse usage plugin data.
"""

##region ------------------------------ IMPORTS  -----------------------------------------
#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
#
#

import uuid
from typing import Tuple
from src.dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: WAREHOUSE USAGE --------------------------------


class WarehouseUsagePlugin(Plugin):
    """
    Warehouse usage plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int, int]:
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

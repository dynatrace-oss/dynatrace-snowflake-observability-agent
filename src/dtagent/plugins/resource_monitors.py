"""
Plugin file for processing resource monitors plugin data.
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
import logging
from typing import Tuple, Dict
from snowflake.snowpark.functions import current_timestamp
from dtagent.util import _unpack_json_dict
from dtagent.plugins import Plugin
from dtagent.context import get_context_name_and_run_id
from dtagent.otel.events import EventType

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: RESOURCE MONITORS --------------------------------


class ResourceMonitorsPlugin(Plugin):
    """
    Resource monitors plugin class.
    """

    unattached_rms: int = 0
    unmonitored_wh: int = 0
    has_account_rm: bool = False

    def _prepare_event_timestamps_payload_rm(self, key, ts, row_dict):
        """prepares event timestamp payload for resource monitors"""
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS"])
        return (
            f"Resource monitor {payload.get('snowflake.resource_monitor.name', '')} event: {key}",
            {
                "timestamp": ts,
                "snowflake.resource_monitor.event": key,
            },
            EventType.CUSTOM_INFO,
        )

    def _process_log_rm(self, row_dict, __context, log_level):  # pylint: disable=unused-argument
        """processes logging for resource monitors"""
        if not row_dict.get("IS_ACTIVE", False):
            self.unattached_rms += 1

        self.has_account_rm |= row_dict.get("IS_ACCOUNT_LEVEL", False)
        # we only send a single log per execution if there is no account level monitor set up, so no logging here is necessary
        return False

    def _prepare_event_timestamps_payload_wh(self, key, ts, row_dict):
        """Prepares event timestamp payloads for warehouses in resource monitors plugin"""
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS"])

        return (
            f"Warehouse {payload.get('snowflake.warehouse.name', '')} is not monitored",
            {
                "timestamp": ts,
                "snowflake.warehouse.event": key,
            },
            EventType.CUSTOM_INFO,
        )

    def _process_log_wh(self, row_dict, __context, log_level):  # pylint: disable=unused-argument
        """Processes logs for warehouses view in resource monitors"""
        # we use custom log level here, so passed log_level remains unused
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])

        if payload.get("snowflake.warehouse.is_unmonitored", False):
            self._logs.send_log(
                message=f"Warehouse {payload.get('snowflake.warehouse.name', '')} is not monitored",
                extra=payload,
                log_level=logging.WARN,
                context=__context,
            )
            self.unmonitored_wh += 1
            return True

        return False

    def process(self, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        Processes the measures on resource monitors.
        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
            {
                "resource_monitors": {
                    "entries": entries_cnt,
                    "logs": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
                "warehouses": {
                    "entries": entries_cnt,
                    "logs": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
            }
        """
        run_id = str(uuid.uuid4().hex)
        context_name = "resource_monitors"

        if run_proc:
            # we need to refresh the temporary tables with resource monitors and warehouse telemetry
            self._session.call("APP.P_REFRESH_RESOURCE_MONITORS")

        (
            resource_monitors_entries_cnt,
            resource_monitors_logs_cnt,
            resource_monitors_metrics_cnt,
            resource_monitors_events_cnt,
        ) = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_RESOURCE_MONITORS"),
            context_name=context_name,
            run_uuid=run_id,
            f_event_timestamp_payload_prepare=self._prepare_event_timestamps_payload_rm,
            f_report_log=self._process_log_rm,
            log_completion=False,
        )

        if not self.has_account_rm:
            # we do not seem to have a account level resource monitor setup - send a warning
            self._logs.send_log(
                "There is no ACCOUNT level resource monitor setup",
                log_level=logging.ERROR,
                context=get_context_name_and_run_id(context_name, run_id),
            )

        (
            warehouses_entries_cnt,
            warehouses_logs_cnt,
            warehouses_metrics_cnt,
            warehouses_events_cnt,
        ) = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_WAREHOUSES"),
            context_name=context_name,
            run_uuid=run_id,
            f_event_timestamp_payload_prepare=self._prepare_event_timestamps_payload_wh,
            f_report_log=self._process_log_wh,
            log_completion=False,
        )

        results_dict = {
            "resource_monitors": {
                "entries": resource_monitors_entries_cnt,
                "logs": resource_monitors_logs_cnt,
                "metrics": resource_monitors_metrics_cnt,
                "events": resource_monitors_events_cnt,
            },
            "warehouses": {
                "entries": warehouses_entries_cnt,
                "logs": warehouses_logs_cnt,
                "metrics": warehouses_metrics_cnt,
                "events": warehouses_events_cnt,
            },
        }

        if run_proc:
            self._report_execution(
                "resource_monitors",
                current_timestamp(),
                None,
                results_dict,
            )

        return results_dict


##endregion

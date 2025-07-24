"""
Plugin file for processing resource monitors plugin data.
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
import logging
from typing import Tuple
from snowflake.snowpark.functions import current_timestamp
from dtagent.util import _unpack_json_dict, _get_timestamp_in_sec, NANOSECOND_CONVERSION_RATE
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name
from dtagent.otel.events import EventType
from dtagent import LOG

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: RESOURCE MONITORS --------------------------------


class ResourceMonitorsPlugin(Plugin):
    """
    Resource monitors plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """
        Processes the measures on resource monitors.
        Returns number of (processed resources monitors, unattached resource monitors, processed warehouses, unmonitored warehouses)
        """

        __context = get_context_by_name("resource_monitors")

        # get the timestamp of the last processed log entry
        last_timestamp = self._configuration.get_last_measurement_update(self._session, "resource_monitors")

        processed_rm = 0
        unattached_rms = 0
        processed_wh = 0
        unmonitored_wh = 0
        has_account_rm = False
        t_resource_monitors = "APP.V_RESOURCE_MONITORS"

        if run_proc:
            # we need to refresh the temporary tables with resource monitors and warehouse telemetry
            self._session.call("APP.P_REFRESH_RESOURCE_MONITORS")

        for row_dict in self._get_table_rows(t_resource_monitors):
            is_active = row_dict.get("IS_ACTIVE", False)
            has_account_rm |= row_dict.get("IS_ACCOUNT_LEVEL", False)

            if not is_active:
                unattached_rms += 1

            # sending information on each resource monitor as metrics
            if self._metrics.discover_report_metrics(row_dict):
                processed_rm += 1

            # in case there were some new events for given monitor - we will log them
            for key, ts in _unpack_json_dict(row_dict, ["EVENT_TIMESTAMPS"]).items():

                ts_dt = _get_timestamp_in_sec(ts, NANOSECOND_CONVERSION_RATE)  # converting from nanoseconds to seconds
                if ts_dt >= last_timestamp:
                    payload = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])
                    if not self._events.report_via_api(
                        query_data=row_dict,
                        title=f"Resource monitor {payload.get('snowflake.resource_monitor.name', '')} event: {key}",
                        additional_payload={
                            "timestamp": ts,
                            "snowflake.resource_monitor.event": key,
                        },
                        event_type=EventType.CUSTOM_INFO,
                        context=__context,
                    ):

                        LOG.warning("Could not send event for resource monitors")

        if not has_account_rm:
            # we do not seem to have a account level resource monitor setup - send a warning
            self._logs.send_log(
                "There is no ACCOUNT level resource monitor setup",
                log_level=logging.ERROR,
                context=__context,
            )

        # analyzing warehouses
        t_data_volume = "APP.V_WAREHOUSES"

        for row_dict in self._get_table_rows(t_data_volume):
            payload = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])
            wh_name = payload.get("snowflake.warehouse.name", "")
            is_unmonitored = payload.get("snowflake.warehouse.is_unmonitored", False)

            if is_unmonitored:
                # we do not seem to be monitoring this warehouse
                self._logs.send_log(
                    message=f"Warehouse {wh_name} is not monitored",
                    extra=payload,
                    log_level=logging.WARN,
                    context=__context,
                )
                unmonitored_wh += 1

            # sending information on each resource monitor as metrics
            if self._metrics.discover_report_metrics(row_dict):
                processed_wh += 1

            for key, ts in _unpack_json_dict(row_dict, ["EVENT_TIMESTAMPS"]).items():
                ts_dt = _get_timestamp_in_sec(ts, NANOSECOND_CONVERSION_RATE)  # converting from nanoseconds to seconds

                if ts_dt >= last_timestamp:
                    if (
                        self._events.report_via_api(
                            query_data=row_dict,
                            title=f"Warehouse {wh_name} event: {key}",
                            additional_payload={
                                "timestamp": ts,
                                "snowflake.warehouse.event": key,
                            },
                            event_type=EventType.CUSTOM_INFO,
                            context=__context,
                        )
                        != 1
                    ):
                        LOG.warning("Could not send event for warehouses")

        self._metrics.flush_metrics()

        if run_proc:
            self._report_execution(
                "resource_monitors",
                current_timestamp(),
                None,
                {
                    "resource_monitors.count": processed_rm,
                    "resource_monitors.unattached": unattached_rms,
                    "warehouses.count": processed_wh,
                    "warehouses.unmonitored": unmonitored_wh,
                },
            )

        return processed_rm, unattached_rms, processed_wh, unmonitored_wh


##endregion

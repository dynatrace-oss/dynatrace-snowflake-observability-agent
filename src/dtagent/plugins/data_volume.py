"""
Plugin file for processing data volume plugin data.
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

from snowflake.snowpark.functions import current_timestamp
from dtagent.util import (
    _unpack_json_dict,
    _get_timestamp_in_sec,
    NANOSECOND_CONVERSION_RATE,
    EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME,
)
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name
from dtagent.otel.events import EventType
from dtagent import LOG

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: DATA VOLUME --------------------------------


class DataVolumePlugin(Plugin):
    """
    Data volume plugin class.
    """

    def process(self, run_proc: bool = True) -> int:
        """
        Processes the measures on data volume
        """

        t_data_volume = "APP.V_DATA_VOLUME"
        __context = get_context_by_name("data_volume")

        # get the timestamp of the last processed log entry
        last_timestamp = self._configuration.get_last_measurement_update(self._session, "data_volume")

        processed_tables = 0

        for row_dict in self._get_table_rows(t_data_volume):
            if self._metrics.discover_report_metrics(row_dict):
                processed_tables += 1

            for key, ts in _unpack_json_dict(row_dict, ["EVENT_TIMESTAMPS"]).items():
                ts_dt = _get_timestamp_in_sec(ts, NANOSECOND_CONVERSION_RATE)  # converting from nanoseconds to seconds
                if ts_dt >= last_timestamp:
                    if not self._events.report_via_api(
                        row_dict,
                        EventType.CUSTOM_INFO,
                        title=f"Table event {key}.",
                        additional_payload={
                            "timestamp": ts,
                            EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME: key,
                        },
                        context=__context,
                    ):
                        LOG.warning("Could not send event from data volume plugin")

        self._metrics.flush_metrics()

        if run_proc:
            self._report_execution(
                "data_volume",
                current_timestamp(),
                None,
                {"tables": processed_tables},
            )

        return processed_tables


##endregion

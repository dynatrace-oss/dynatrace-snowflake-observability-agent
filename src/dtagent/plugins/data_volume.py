"""
Plugin file for processing data volume plugin data.
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

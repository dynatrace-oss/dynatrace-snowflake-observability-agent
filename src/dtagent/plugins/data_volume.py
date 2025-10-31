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
from dtagent.plugins import Plugin
from typing import Dict

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: DATA VOLUME --------------------------------


class DataVolumePlugin(Plugin):
    """
    Data volume plugin class.
    """

    def process(self, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        Processes the measures on data volume

        Returns:
            Dict[str,int]: A dictionary with telemetry counts for data volume.

            Example:
            {
                "data_volume": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                }
            }
        """

        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_DATA_VOLUME"),
            context_name="data_volume",
            report_logs=False,
            log_completion=False,
        )
        processed_tables = {
            "data_volume": {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,
            }
        }
        if run_proc:
            self._report_execution(
                "data_volume",
                current_timestamp(),
                None,
                processed_tables,
            )

        return processed_tables


##endregion

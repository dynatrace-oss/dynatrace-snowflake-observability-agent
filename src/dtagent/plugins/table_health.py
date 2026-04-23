"""Plugin file for processing table health plugin data."""

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
from typing import Dict, Optional, List
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------- MEASUREMENT SOURCE: TABLE HEALTH --------------------------------


class TableHealthPlugin(Plugin):
    """Table health plugin class."""

    PLUGIN_NAME = "table_health"

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes the measures on table storage health.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with telemetry counts for table health.

            Example:
            {
            "dsoa.run.results": {
                "table_health": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                }
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_TABLE_STORAGE"),
            context_name="table_storage",
            run_uuid=run_id,
            report_logs=False,
            log_completion=False,
        )
        results_dict = {
            "table_health": {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,  # pylint: disable=duplicate-code
            }
        }
        if run_proc:
            self._report_execution("table_health", current_timestamp(), None, results_dict, run_id=run_id)

        return self._report_results(results_dict, run_id)


##endregion

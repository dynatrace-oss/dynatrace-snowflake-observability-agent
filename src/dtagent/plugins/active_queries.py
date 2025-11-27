"""Plugin file for processing active queries plugin data."""

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
<<<<<<< HEAD

from typing import Tuple
=======
from typing import Tuple, Dict
>>>>>>> main
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: ACTIVE QUERIES --------------------------------


class ActiveQueriesPlugin(Plugin):
    """Active queries plugin class."""

    PLUGIN_NAME = "active_queries"

    def process(self, run_id: str, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """Processes the measures on active queries

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
            {
            "dsoa.run.results": {
                "active_queries":
                {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt
                }
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        t_active_queries = "SELECT * FROM TABLE(DTAGENT_DB.APP.F_ACTIVE_QUERIES_INSTRUMENTED())"

        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_active_queries),
            "active_queries",
            run_uuid=run_id,
            report_timestamp_events=False,
            report_metrics=True,
            log_completion=run_proc,
        )

        return self._report_results(
            {"active_queries": {"entries": entries_cnt, "log_lines": logs_cnt, "metrics": metrics_cnt, "events": events_cnt}},
            run_id,
        )


##endregion

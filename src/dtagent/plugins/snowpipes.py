"""Plugin file for processing snowpipes plugin data."""

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

from typing import Dict, List, Optional
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: SNOWPIPES --------------------------------


class SnowpipesPlugin(Plugin):
    """Snowpipes monitoring plugin class."""

    PLUGIN_NAME = "snowpipes"

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes the measures on snowpipes using dual-schedule architecture.

        Fast mode (context: snowpipes): SHOW PIPES + SYSTEM$PIPE_STATUS — real-time status, backlog, latency.
        Deep mode (context: snowpipes_copy_history): ACCOUNT_USAGE.COPY_HISTORY — per-file details, errors.
        Deep mode (context: snowpipes_usage_history): PIPE_USAGE_HISTORY — cost, volume.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed
            contexts (Optional[List[str]]): optional list of context names to process;
                                            None means all contexts are processed

        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
            {
            "dsoa.run.results": {
                "snowpipes": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": event_cnt,
                },
                "snowpipes_copy_history": {
                    "entries": entries_copy_cnt,
                    "log_lines": logs_copy_cnt,
                    "metrics": metrics_copy_cnt,
                    "events": event_copy_cnt,
                },
                "snowpipes_usage_history": {
                    "entries": entries_usage_cnt,
                    "log_lines": logs_usage_cnt,
                    "metrics": metrics_usage_cnt,
                    "events": event_usage_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        t_snowpipes = "call DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED()"
        t_copy_history = "APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED"
        t_usage_history = "APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED"

        results = {}

        if not contexts or "snowpipes" in contexts:
            entries_cnt, logs_cnt, metrics_cnt, event_cnt = self._log_entries(
                lambda: self._get_table_rows(t_snowpipes),
                "snowpipes",
                run_uuid=run_id,
                report_timestamp_events=True,
                report_metrics=True,
                log_completion=run_proc,
            )
            results["snowpipes"] = {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": event_cnt,
            }

        if not contexts or "snowpipes_copy_history" in contexts:
            entries_copy_cnt, logs_copy_cnt, metrics_copy_cnt, event_copy_cnt = self._log_entries(
                lambda: self._get_table_rows(t_copy_history),
                "snowpipes_copy_history",
                run_uuid=run_id,
                report_metrics=True,
                log_completion=run_proc,
            )
            results["snowpipes_copy_history"] = {
                "entries": entries_copy_cnt,
                "log_lines": logs_copy_cnt,
                "metrics": metrics_copy_cnt,
                "events": event_copy_cnt,
            }

        if not contexts or "snowpipes_usage_history" in contexts:
            entries_usage_cnt, logs_usage_cnt, metrics_usage_cnt, event_usage_cnt = self._log_entries(
                lambda: self._get_table_rows(t_usage_history),
                "snowpipes_usage_history",
                run_uuid=run_id,
                report_metrics=True,
                log_completion=run_proc,
            )
            results["snowpipes_usage_history"] = {
                "entries": entries_usage_cnt,
                "log_lines": logs_usage_cnt,
                "metrics": metrics_usage_cnt,
                "events": event_usage_cnt,
            }

        return self._report_results(results, run_id)


##endregion

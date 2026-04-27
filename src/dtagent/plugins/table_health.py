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
    """Table health plugin class.

    Provides three contexts:

    - ``table_storage``: storage metrics (active bytes, time-travel bytes, failsafe bytes,
      retained-for-clone bytes, row count) sourced from
      ``SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS``.

    - ``table_clustering``: clustering depth metrics (average depth, average overlaps,
      constant partition ratio, total partitions) sourced from the
      ``APP.TABLE_CLUSTERING_RESULTS`` staging table populated by
      ``APP.P_COLLECT_CLUSTERING_INFO()``.  Only processed when
      ``plugins.table_health.clustering_enabled`` is ``true`` (default).

    - ``table_health_derived``: period-over-period growth and clustering degradation signals
      computed from ``APP.V_TABLE_HEALTH_DERIVED``, which compares the two latest snapshots
      from ``APP.TABLE_HEALTH_HISTORY`` using a ``ROW_NUMBER``-based selection.
      Only processed when ``plugins.table_health.history_retention_days`` is greater than 0
      (default 0 = disabled).
    """

    PLUGIN_NAME = "table_health"

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes the measures on table storage health, clustering depth, and derived growth metrics.

        Args:
            run_id (str):                    unique run identifier
            run_proc (bool):                 indicator whether processing should be logged as completed
            contexts (Optional[List[str]]): optional list of context names to process;
                                            ``None`` means all enabled contexts are processed

        Returns:
            Dict[str, Dict[str, int]]: A dictionary with telemetry counts per context.

            Example:
            {
            "dsoa.run.results": {
                "table_health": {
                    "table_storage": {
                        "entries": entries_cnt,
                        "log_lines": logs_cnt,
                        "metrics": metrics_cnt,
                        "events": events_cnt,
                    },
                    "table_clustering": {
                        "entries": clust_entries_cnt,
                        "log_lines": clust_logs_cnt,
                        "metrics": clust_metrics_cnt,
                        "events": clust_events_cnt,
                    },
                    "table_health_derived": {
                        "entries": derived_entries_cnt,
                        "log_lines": derived_logs_cnt,
                        "metrics": derived_metrics_cnt,
                        "events": derived_events_cnt,
                    },
                }
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        results: Dict[str, Dict[str, int]] = {}

        if not contexts or "table_storage" in contexts:
            entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows("APP.V_TABLE_STORAGE"),
                context_name="table_storage",
                run_uuid=run_id,
                report_logs=False,
                log_completion=False,
            )
            results["table_storage"] = {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,  # pylint: disable=duplicate-code
            }

        clustering_enabled = self._configuration.get(plugin_name="table_health", key="clustering_enabled", default_value=True)
        if clustering_enabled and (not contexts or "table_clustering" in contexts):
            clust_entries, clust_logs, clust_metrics, clust_events = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows("APP.V_TABLE_CLUSTERING"),
                context_name="table_clustering",
                run_uuid=run_id,
                report_logs=False,
                log_completion=False,
            )
            results["table_clustering"] = {
                "entries": clust_entries,
                "log_lines": clust_logs,
                "metrics": clust_metrics,
                "events": clust_events,
            }

        history_retention_days = self._configuration.get(plugin_name="table_health", key="history_retention_days", default_value=0)
        if history_retention_days and history_retention_days > 0 and (not contexts or "table_health_derived" in contexts):
            derived_entries, derived_logs, derived_metrics, derived_events = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows("APP.V_TABLE_HEALTH_DERIVED"),
                context_name="table_health_derived",
                run_uuid=run_id,
                report_logs=False,
                log_completion=False,
            )
            results["table_health_derived"] = {
                "entries": derived_entries,
                "log_lines": derived_logs,
                "metrics": derived_metrics,
                "events": derived_events,
            }

        if run_proc:
            self._report_execution("table_health", current_timestamp(), None, results, run_id=run_id)

        return self._report_results(results, run_id)


##endregion

"""Plugin file for processing org costs plugin data."""

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

from typing import Dict, Optional, List
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: ORG COSTS --------------------------------


class OrgCostsPlugin(Plugin):
    """Org costs plugin class."""

    PLUGIN_NAME = "org_costs"

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes data for org costs plugin.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed
            contexts (Optional[List[str]]): optional list of contexts to process; all if None

        Returns:
            Dict[str, Dict[str, int]]: A dictionary with telemetry counts for org costs.

            Example:
            {
            "dsoa.run.results": {
                "org_costs_metering": {
                    "entries": entries_metering_cnt,
                    "log_lines": logs_metering_cnt,
                    "metrics": metrics_metering_cnt,
                    "events": events_metering_cnt,
                },
                "org_costs_storage": {
                    "entries": entries_storage_cnt,
                    "log_lines": logs_storage_cnt,
                    "metrics": metrics_storage_cnt,
                    "events": events_storage_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """

        results = {}

        if not contexts or "org_costs_metering" in contexts:
            t_org_metering = "APP.V_ORG_METERING_DAILY"
            entries_metering_cnt, logs_metering_cnt, metrics_metering_cnt, events_metering_cnt = self._log_entries(
                lambda: self._get_table_rows(t_org_metering),
                "org_costs_metering",
                run_uuid=run_id,
                log_completion=run_proc,
            )
            results["org_costs_metering"] = {
                "entries": entries_metering_cnt,
                "log_lines": logs_metering_cnt,
                "metrics": metrics_metering_cnt,
                "events": events_metering_cnt,
            }

        if not contexts or "org_costs_storage" in contexts:
            t_org_storage = "APP.V_ORG_STORAGE_DAILY"
            entries_storage_cnt, logs_storage_cnt, metrics_storage_cnt, events_storage_cnt = self._log_entries(
                lambda: self._get_table_rows(t_org_storage),
                "org_costs_storage",
                run_uuid=run_id,
                log_completion=run_proc,
            )
            results["org_costs_storage"] = {
                "entries": entries_storage_cnt,
                "log_lines": logs_storage_cnt,
                "metrics": metrics_storage_cnt,
                "events": events_storage_cnt,
            }

        return self._report_results(results, run_id)


##endregion

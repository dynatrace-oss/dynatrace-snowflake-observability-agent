"""
Plugin file for processing data schemas plugin data.
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
from typing import Any, Dict

from dtagent.plugins import Plugin
from dtagent.otel.events import EventType
from dtagent.util import _from_json, _pack_values_to_json_strings

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: DATA SCHEMAS --------------------------------


class DataSchemasPlugin(Plugin):
    """
    Data schemas plugin class.
    """

    def _compress_properties(self, properties_value: Dict) -> Dict:
        """Ensures that snowflake.object.ddl.properties is compressed in the 'columns' object"""
        from collections import defaultdict

        def __process(k: str, v: Any) -> Any:
            if k == "columns":
                result = defaultdict(list)
                for column, details in v.items():
                    result[details["subOperationType"]].append(column)
                return dict(result)
            if k == "creationMode":
                return v.get("value", v)
            return v

        return {k: __process(k, v) for k, v in properties_value.items()}

    def _prepare_event_payload(self, row_dict):
        """defines event type, title and additional payload"""
        return (
            EventType.CUSTOM_INFO,
            row_dict.get("_MESSAGE"),
            {
                "timestamp": row_dict.get("TIMESTAMP"),
                "snowflake.object.event": "snowflake.object.ddl",
            },
        )

    def _report_all_entries_as_events(
        self, row_dict, event_type, title, *, start_time, end_time, properties, context
    ) -> int:  # pylint: disable=unused-argument
        """
        Defines how all entries as events should be reported
        Args:
            row_dict (Dict): row dictionary
            event_type (str): event type
            title (str): event title
            start_time (str): start time key in row_dict
            end_time (str): end time key in row_dict
            properties (Dict): additional properties to be added to event payload
            context (Optional[Dict]): additional context to be added to event payload
        Returns:
            int: number of events reported (1+ if successful, 0 otherwise)
        """

        _attributes = _from_json(row_dict["ATTRIBUTES"])
        _attributes["snowflake.object.ddl.properties"] = self._compress_properties(_attributes.get("snowflake.object.ddl.properties", {}))
        row_dict["ATTRIBUTES"] = _pack_values_to_json_strings(_attributes)
        return self._events.report_via_api(
            title=title,
            query_data=row_dict,
            additional_payload=properties,
            start_time_key=start_time,
            event_type=event_type,
            context=context,
        )

    def process(self, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        Processes data for data schemas plugin.
        Returns:
            Dict[str,Dict[str,int]]: A dictionary with telemetry counts for data schemas.

            Example:
            {
                "data_schemas": {
                    "entries": entries_cnt,
                    "logs": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                }
            }
        """

        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_DATA_SCHEMAS"),
            context_name="data_schemas",
            report_logs=False,
            report_timestamp_events=False,
            report_metrics=False,
            log_completion=run_proc,
            report_all_as_events=True,
            start_time="TIMESTAMP",
            event_payload_prepare=self._prepare_event_payload,
            f_report_event=self._report_all_entries_as_events,
        )

        return {
            "data_schemas": {
                "entries": entries_cnt,
                "logs": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,
            }
        }

"""
Plugin file for processing data schemas plugin data.
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
from typing import Any, Dict

from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name
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

    def process(self, run_proc: bool = True) -> int:
        """
        Processes data for data schemas plugin.
        Returns:
            processed_spending_metrics [int]: number of events reported from APP.V_DATA_SCHEMAS.
        """

        t_data_schemas = "APP.V_DATA_SCHEMAS"

        __context = get_context_by_name("data_schemas")

        processed_events_cnt = 0
        last_processed_timestamp = self._configuration.get_last_measurement_update(self._session, "data_schemas")

        for row_dict in self._get_table_rows(t_data_schemas):
            last_processed_timestamp = row_dict.get("TIMESTAMP")
            _attributes = _from_json(row_dict["ATTRIBUTES"])
            _attributes["snowflake.object.ddl.properties"] = self._compress_properties(
                _attributes.get("snowflake.object.ddl.properties", {})
            )
            row_dict["ATTRIBUTES"] = _pack_values_to_json_strings(_attributes)
            if self._events.report_via_api(
                title=row_dict.get("_MESSAGE"),
                query_data=row_dict,
                additional_payload={
                    "timestamp": last_processed_timestamp,
                    "snowflake.object.event": "snowflake.object.ddl",
                },
                start_time_key="TIMESTAMP",
                event_type=EventType.CUSTOM_INFO,
                context=__context,
            ):
                processed_events_cnt += 1

        if run_proc:
            self._report_execution(
                "data_schemas",
                str(last_processed_timestamp),
                None,
                {
                    "processed_data_schemas_count": processed_events_cnt,
                },
            )

        return processed_events_cnt

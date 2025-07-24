"""
Plugin file for processing query history plugin data.
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

import logging
from typing import Any, Tuple, Dict, List
from snowflake.snowpark.functions import current_timestamp
from dtagent import LOG, LL_TRACE
from dtagent.util import (
    _from_json,
    _unpack_json_dict,
    _unpack_json_list,
    _pack_values_to_json_strings,
)
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: QUERY HISTORY --------------------------------


class QueryHistoryPlugin(Plugin):
    """
    Query history plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int, int]:
        """
        The actual function to process query history:

        Returns:
            - number of queries
            - number of problems
            - number of span events created
        """
        __context = get_context_by_name("query_history")

        def __get_query_operator_event_name(operator: Dict) -> str:
            """Returns string with query operator event."""

            return f"{operator['snowflake.query.operator.type']} {operator['snowflake.query.id']}:{operator['snowflake.query.operator.id']}"

        def __f_span_events(d_span: Dict[str, any]) -> Tuple[List[Dict[str, any]], int]:
            """Extracts span events, returns list of them and list of failed attempts."""

            failed_events = 0
            span_events = []
            query_operator_stats = _from_json(d_span.get("QUERY_OPERATOR_STATS", None))

            LOG.log(LL_TRACE, "query_operator_stats = %r", query_operator_stats)

            if query_operator_stats:
                for operator in query_operator_stats:
                    try:
                        span_event = {
                            "name": __get_query_operator_event_name(operator),
                            "attributes": _pack_values_to_json_strings(operator),
                            "timestamp": operator["timestamp"],
                        }
                        span_events.append(span_event)
                    except TypeError as e:
                        failed_events += 1
                        raise ValueError(f"query_id = {d_span['QUERY_ID']}; operator = {str(operator)}; e = {e}") from e

            return span_events, failed_events

        def __f_log_events(query_dict: Dict[str, Any]):
            """Logs events for query history."""

            log_dict = _unpack_json_dict(
                query_dict,
                ["DIMENSIONS", "ATTRIBUTES", "METRICS"],
            )

            self._logs.send_log(
                log_dict.get("db.query.text", "Snowflake Query"),
                extra={
                    "timestamp": query_dict["START_TIME"],
                    "end_time": query_dict["END_TIME"],
                    **log_dict,
                },
                context=__context,
            )
            for operator in _unpack_json_list(query_dict, ["QUERY_OPERATOR_STATS"]):
                self._logs.send_log(
                    f"Query operator: {__get_query_operator_event_name(operator)}",
                    extra=operator,
                    log_level=logging.INFO,
                    context=__context,
                )

        # initialize the recent queries cache
        processed_query_ids: list[str] = []
        processing_errors: list[str] = []
        span_events_added = 0

        t_recent_queries = "APP.V_RECENT_QUERIES"

        if run_proc:
            # getting list of recent queries with their query operator stats (query profile)
            self._session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            # getting slow queries and checking if they would benefit from acceleration
            self._session.call("APP.P_GET_ACCELERATION_ESTIMATES", log_on_exception=True)

        for row_dict in self._get_table_rows(t_recent_queries):
            query_id = row_dict.get("QUERY_ID", None)
            if query_id is None:
                LOG.warning("Problem with given row in query history: %r", row_dict)
            else:
                LOG.log(LL_TRACE, "Processing query history for %r", query_id)
                span_events_added += self._process_row(
                    row=row_dict,
                    processed_ids=processed_query_ids,
                    processing_errors=processing_errors,
                    row_id_col="QUERY_ID",
                    parent_row_id_col="PARENT_QUERY_ID",
                    view_name="APP.V_RECENT_QUERIES",
                    f_span_events=__f_span_events,
                    f_log_events=__f_log_events,
                    context=__context,
                )

        joint_processed_query_ids = "|".join(processed_query_ids)

        if not self._metrics.flush_metrics():
            processing_errors.append("Problem flushing metrics cache")

        if not self._spans.flush_traces():
            processing_errors.append("Problem flushing traces")

        processing_errors_count = len(processing_errors)
        if processing_errors_count > 0:
            LOG.warning("Following problems where discovered when processing query history: %s", str(processing_errors))

        if run_proc:
            self._report_execution(
                "query_history",
                current_timestamp(),
                None,
                {
                    "joint_processed_query_ids": joint_processed_query_ids,
                    "processing_errors_count": processing_errors_count,
                    "span_events_added_count": span_events_added,
                },
            )

            self._session.call(
                "STATUS.UPDATE_PROCESSED_QUERIES",
                joint_processed_query_ids,
                processing_errors_count,
                span_events_added,
            )

        return (
            len(processed_query_ids),
            processing_errors_count,
            span_events_added,
        )


##endregion

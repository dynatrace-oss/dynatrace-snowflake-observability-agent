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
from dtagent import LOG, LL_TRACE
from dtagent.otel import logs, spans
from dtagent.util import (
    _from_json,
    _unpack_json_dict,
    _unpack_json_list,
    _pack_values_to_json_strings,
)
from dtagent.plugins import Plugin
from dtagent.context import get_context_name_and_run_id

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: QUERY HISTORY --------------------------------


class QueryHistoryPlugin(Plugin):
    """
    Query history plugin class.
    """

    def process(self, run_proc: bool = True) -> Dict[str, Dict[str, int]]:
        """
        The actual function to process query history:

        Returns:
            Dict[str,Dict[str,int]]: A dictionary with telemetry counts for query history.

            Example:
            {
                "query_history": {
                    "entries": processed_query_count,
                    "logs": logs_sent,
                    "metrics": metrics_sent,
                    "spans": spans_sent,
                    "span_events": span_events_added,
                    "errors": processing_errors_count,
                }
            }
        """
        __context = get_context_name_and_run_id("query_history")

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

        def __f_log_events(query_dict: Dict[str, Any]) -> int:
            """
            Logs events for query history.

            Returns:
                int: Number of log lines sent."""

            log_dict = _unpack_json_dict(
                query_dict,
                ["DIMENSIONS", "ATTRIBUTES", "METRICS"],
            )

            if not getattr(self._logs, "NOT_ENABLED", False):
                self._logs.send_log(
                    log_dict.get("db.query.text", "Snowflake Query"),
                    extra={
                        "timestamp": query_dict["START_TIME"],
                        "end_time": query_dict["END_TIME"],
                        **log_dict,
                    },
                    context=__context,
                )
                logs_sent = 1

                for operator in _unpack_json_list(query_dict, ["QUERY_OPERATOR_STATS"]):
                    self._logs.send_log(
                        f"Query operator: {__get_query_operator_event_name(operator)}",
                        extra=operator,
                        log_level=logging.INFO,
                        context=__context,
                    )
                    logs_sent += 1
            else:
                logs_sent = 0

            return logs_sent

        if run_proc:
            # getting list of recent queries with their query operator stats (query profile)
            self._session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            # getting slow queries and checking if they would benefit from acceleration
            self._session.call("APP.P_GET_ACCELERATION_ESTIMATES", log_on_exception=True)

        t_recent_queries = "APP.V_RECENT_QUERIES"

        processed_query_ids, processing_errors_count, span_events_added, spans_sent, logs_sent, metrics_sent = self._process_span_rows(
            f_entry_generator=lambda: self._get_table_rows(t_recent_queries),
            view_name=t_recent_queries,
            context_name="query_history",
            log_completion=run_proc,
            report_status=run_proc,
            f_span_events=__f_span_events,
            f_log_events=__f_log_events,
        )

        # return (len(processed_query_ids), processing_errors_count, span_events_added, metrics_sent)
        return {
            "query_history": {
                "entries": len(processed_query_ids),
                "log_lines": logs_sent,
                "metrics": metrics_sent,
                "spans": spans_sent,
                "span_events": span_events_added,
                "errors": processing_errors_count,
            }
        }


##endregion

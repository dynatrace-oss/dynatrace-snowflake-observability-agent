"""Plugin file for processing query history plugin data."""

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
import re
from typing import Any, Tuple, Dict, List, Optional
from dtagent import LOG, LL_TRACE
from dtagent.otel import logs, spans
from dtagent.util import (
    _from_json,
    _unpack_json_dict,
    _unpack_json_list,
    _pack_values_to_json_strings,
    get_now_timestamp_formatted,
)
from dtagent.plugins import Plugin
from dtagent.context import get_context_name_and_run_id, RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: QUERY HISTORY --------------------------------


class QueryHistoryPlugin(Plugin):
    """Query history plugin class."""

    PLUGIN_NAME = "query_history"
    PLUGIN_CONTEXTS: tuple = ("query_history",)

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """The actual function to process query history:

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,Dict[str,int]]: A dictionary with telemetry counts for query history.

            Example:
            {
            "dsoa.run.results": {
                "query_history": {
                    "entries": processed_query_count,
                    "log_lines": logs_sent,
                    "metrics": metrics_sent,
                    "spans": spans_sent,
                    "span_events": span_events_added,
                    "errors": processing_errors_count,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        __context = get_context_name_and_run_id(plugin_name=self._plugin_name, context_name="query_history", run_id=run_id)

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
            """Logs events for query history.

            Returns:
                int: Number of log lines sent.
            """

            log_dict = _unpack_json_dict(
                query_dict,
                ["DIMENSIONS", "ATTRIBUTES", "METRICS"],
            )

            if not getattr(self._logs, "NOT_ENABLED", False):
                log_extra = {
                    "timestamp": query_dict["START_TIME"],
                    "end_time": query_dict["END_TIME"],
                    **log_dict,
                }
                log_extra["db.query.text"] = self._obfuscate_query_text(log_extra.get("db.query.text", ""))
                if log_extra.get("snowflake.error.message"):
                    log_extra["snowflake.error.message"] = self._obfuscate_query_text(log_extra["snowflake.error.message"])
                self._logs.send_log(
                    self._obfuscate_query_text(log_dict.get("db.query.text", "Snowflake Query")),
                    extra=log_extra,
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
            refresh_result = self._call_refresh_recent_queries()
            # getting slow queries and checking if they would benefit from acceleration
            self._session.call("APP.P_GET_ACCELERATION_ESTIMATES", log_on_exception=True)
            # emit self-monitoring event if signal protection was applied
            self._emit_overload_protection_event(refresh_result, __context)

        t_recent_queries = "APP.V_RECENT_QUERIES"
        processed_query_ids, processing_errors_count, span_events_added, spans_sent, logs_sent, metrics_sent = self._process_span_rows(
            f_entry_generator=lambda: self._get_table_rows(t_recent_queries),
            view_name=t_recent_queries,
            context_name="query_history",
            run_uuid=run_id,
            log_completion=run_proc,
            report_status=run_proc,
            f_span_events=__f_span_events,
            f_log_events=__f_log_events,
        )

        # return (len(processed_query_ids), processing_errors_count, span_events_added, metrics_sent)
        return self._report_results(
            {
                "query_history": {
                    "entries": len(processed_query_ids),
                    "log_lines": logs_sent,
                    "metrics": metrics_sent,
                    "spans": spans_sent,
                    "span_events": span_events_added,
                    "errors": processing_errors_count,
                },
            },
            run_id,
        )

    def _obfuscate_query_text(self, text: str) -> str:
        """Apply query text obfuscation based on the configured obfuscation_mode.

        This is a Python-side fallback — primary obfuscation is applied in the SQL view layer.
        It ensures no unobfuscated text leaks through the log message body path.

        Args:
            text (str): The query text or error message to obfuscate.

        Returns:
            str: Obfuscated text according to the configured mode.
                 Mode 'full'     → '[OBFUSCATED]'
                 Mode 'literals' → string/numeric literals replaced with '?'
                 Mode 'off' or unknown → text returned unchanged
        """
        mode = self._configuration.get(plugin_name=self._plugin_name, key="obfuscation_mode", default_value="off")
        if mode == "full":
            return "[OBFUSCATED]"
        if mode == "literals":
            text = re.sub(r"'[^']*'", "'?'", text)
            text = re.sub(r"\b[0-9]+\.?[0-9]*\b", "?", text)
            return text
        return text

    def _call_refresh_recent_queries(self) -> Dict[str, Any]:
        """Call P_REFRESH_RECENT_QUERIES and return the result object.

        Returns:
            Dict[str, Any]: Result object from the procedure with status, counts, and config info.
        """
        try:
            df = self._session.sql("call APP.P_REFRESH_RECENT_QUERIES()")
            rows = df.collect()
            if rows:
                result_value = rows[0][0]
                if isinstance(result_value, dict):
                    return result_value
                if isinstance(result_value, str):
                    result = _from_json(result_value)
                    if isinstance(result, dict):
                        return result
                try:
                    result = dict(result_value)
                    if isinstance(result, dict):
                        return result
                except (TypeError, ValueError):
                    pass
            return {"status": "success", "total_processed": 0, "total_available": 0, "max_entries_applied": False}
        except Exception as e:  # pylint: disable=broad-exception-caught
            LOG.warning("Failed to execute or parse P_REFRESH_RECENT_QUERIES result: %s", str(e))
            return {"status": "error", "total_processed": 0, "total_available": 0, "max_entries_applied": False}

    def _emit_overload_protection_event(self, refresh_result: Dict[str, Any], context: str) -> None:
        """Emit self-monitoring log and bizevent if signal protection was applied.

        Args:
            refresh_result (Dict[str, Any]): Result from P_REFRESH_RECENT_QUERIES
            context (str): Context name for logging
        """
        if not refresh_result.get("max_entries_applied", False):
            return

        total_processed = refresh_result.get("total_processed", 0)
        total_available = refresh_result.get("total_available", 0)
        max_entries = refresh_result.get("max_entries_value", 0)

        if total_available > total_processed:
            dropped_count = total_available - total_processed
            message = (
                f"Signal overload protection active: processed {total_processed} of {total_available} "
                f"available queries (max_entries={max_entries}, dropped={dropped_count})"
            )

            # Emit self-monitoring warning log
            if not getattr(self._logs, "NOT_ENABLED", False):
                self._logs.send_log(
                    message,
                    extra={
                        "timestamp": get_now_timestamp_formatted(),
                        "dsoa.overload_protection.active": True,
                        "dsoa.overload_protection.total_available": total_available,
                        "dsoa.overload_protection.total_processed": total_processed,
                        "dsoa.overload_protection.dropped_count": dropped_count,
                        "dsoa.overload_protection.max_entries": max_entries,
                    },
                    log_level=logging.WARNING,
                    context=context,
                )

            # Emit self-monitoring bizevent
            if not getattr(self._events, "NOT_ENABLED", False):
                self._events.send_event(
                    event_type="dsoa.signal_overload_protection",
                    title=message,
                    properties={
                        "total_available": total_available,
                        "total_processed": total_processed,
                        "dropped_count": dropped_count,
                        "max_entries": max_entries,
                    },
                    context=context,
                )


##endregion

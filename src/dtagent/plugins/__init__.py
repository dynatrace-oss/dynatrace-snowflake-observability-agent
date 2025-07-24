"""
Init file for all plugins, contains generic methods.
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
import gc
import uuid
import logging
import inspect
from typing import Tuple, Dict, List, Callable, Union, Generator, Optional, Any
from abc import ABC, abstractmethod
import datetime
from snowflake import snowpark

from dtagent.config import Configuration
from dtagent.util import (
    _unpack_json_dict,
    _cleanup_dict,
    _get_timestamp_in_sec,
    get_now_timestamp_formatted,
    NANOSECOND_CONVERSION_RATE,
    EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME,
    is_select_for_table,
)
from dtagent.otel.events import Events, EventType
from dtagent.otel.bizevents import BizEvents
from dtagent.otel.logs import Logs
from dtagent.otel.spans import Spans
from dtagent.otel.metrics import Metrics
from dtagent.context import get_context_by_name

##endregion COMPILE_REMOVE

##region ------------------------ PROCESSING MEASUREMENTS ---------------------------------


class Plugin(ABC):
    """
    Generic plugin class, base for all plugins.
    """

    def __init__(
        self,
        *,
        session: snowpark.Session,
        logs: Optional[Logs] = None,
        spans: Optional[Spans] = None,
        metrics: Optional[Metrics] = None,
        configuration: Optional[Configuration] = None,
        events: Optional[Events] = None,
        bizevents: Optional[BizEvents] = None,
    ):
        """Sets session variables."""

        self._session = session

        if logs is not None:
            self._logs = logs
        if spans is not None:
            self._spans = spans
        if metrics is not None:
            self._metrics = metrics
        if configuration is not None:
            self._configuration = configuration
        if events is not None:
            self._events = events
        if bizevents is not None:
            self._bizevents = bizevents

    def _has_event(
        self,
        column_value: str,
        value_to_compare: Optional[str] = None,
    ) -> bool:
        """Checks for specified column, if desired value is set returns true if column matches the value,
        otherwise true if column is in the row.
        """

        if column_value is None:
            return False
        if value_to_compare is None and str(column_value).lower() != "nan":
            return True
        if value_to_compare is not None and value_to_compare.lower() in str(column_value).lower():
            return True

        return False

    def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
        """Returns generator over result set for given table/view ... or a select query

        Args:
            table_name (str): name of table/view or SELECT statement

        Yields:
            Generator[Dict, None, None]: Generator over result set
        """
        df = self._session.sql(t_data) if is_select_for_table(t_data) else self._session.table(t_data)

        for row in df.collect():
            row_dict = row.as_dict(recursive=True)

            yield row_dict

    def _report_execution(self, measurements_source: str, last_timestamp, last_id, entries_count: dict):
        __context = get_context_by_name("self_monitoring")

        # we cannot use last timestamp when sending logs to DT, because when it is set to snowpark.current_timestamp, the value is taken from a snowflake table
        # for DT it would look like 'Column[current_timestamp]'
        self._logs.send_log(
            f"New entry to STATUS.LOG_PROCESSED_MEASUREMENTS from {measurements_source}",
            extra={"timestamp": get_now_timestamp_formatted(), "last_id": last_id, **entries_count},
            log_level=logging.INFO,
            context=__context,
        )

        # if no valid timestamp given, default to last run timestamp
        if last_timestamp is None or str(last_timestamp) == "None":
            last_timestamp = self._configuration.get_last_measurement_update(self._session, measurements_source)

        self._session.call(
            "STATUS.LOG_PROCESSED_MEASUREMENTS",
            str(measurements_source),
            last_timestamp,
            str(last_id),
            str(entries_count),
        )

    def _process_row(
        self,
        row: dict,
        *,
        processed_ids: list[str],
        processing_errors: list[str],
        row_id_col: str,
        parent_row_id_col: str,
        view_name: str,
        f_span_events: Optional[Callable[[Dict[str, Any]], Tuple[List[Dict[str, Any]], int]]] = None,
        f_log_events: Optional[Callable[[Dict[str, Any]], None]] = None,
        context: Optional[Dict] = None,
    ) -> int:
        """
        Processing single row with data, with optional recursion done within span generation

        Args:
            row (Dict):                         object with measurements to be sent to DT
            processed_ids (List):               accumulated list of IDs processed by this and sub calls
            processing_errors (List):           accumulated list of errors reported when processing this and sub calls
            row_id_col (str):                   name of the column with ID representing the row being processed
            parent_row_id_col (str):            name of the column with parent ID representing the parent row - necessary in context of spans
            view_name (str):                    view which contains all the information to be processed - required for recursion in spans
            f_span_events:                      function that will produce a list of span events to be sent
            f_log_events:                       function that will log current span and its events
            context:                            context information reported as additional attributes in log/span payload
        Return:
            int: accumulated number of span events generated
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE

        row_id = row.get(row_id_col, None)
        LOG.log(LL_TRACE, "Processing row with id = %s", row_id)

        if not self._metrics.report_via_metrics_api(row):
            processing_errors.append(f"Problem sending row {row_id} as metric")

        span_events_added = 0
        if row.get("IS_ROOT", True):  # processing top level rows only: marked as IS_ROOT or missing that marker
            span_events_added = self._spans.generate_span(
                row,
                self._session,
                row_id_col,
                parent_row_id_col,
                is_top_level=True,
                view_name=view_name,
                f_span_events=f_span_events,
                f_log_events=f_log_events,
                context=context,
            )

        if row_id is not None and processed_ids is not None:
            processed_ids.append(row_id)

        return span_events_added

    def _log_entries(
        self,
        f_entry_generator: Callable[[Dict, None], None],
        context_name: str,
        *,
        run_uuid: str = str(uuid.uuid4().hex),
        report_logs: bool = True,
        report_metrics: bool = True,
        report_timestamp_events: bool = True,
        start_time: str = "START_TIME",
        end_time: str = "END_TIME",
        log_completion: bool = True,
        event_column_to_check: Optional[str] = None,
        event_value_to_check: Optional[str] = None,
        event_payload_prepare: Optional[Callable] = None,
    ) -> Tuple[int, int, int, int]:
        """Processes entries delivered by f_entry_generator. By default all entries are sent as logs.
        Unless disabled matching metrics are also generated
        Also events are send for recent timestamp_event entries.

        Args:
            entry_generator (function): function generating entries
            context_name (str): name of the context
            report_metrics (bool): we can disable sending logs this way, e.g., if we only want to have metrics sent
            report_metrics (bool): indicator whether metrics should be generated from this payload entries
            report_timestamp_events (bool): we can disable sending events based on EVENT_TIMESTAMPS (enabled by default)
            start_time (str): name of the key containing the start time
            end_time (str): name of the key containing the end time
            log_completion (bool): indicator whether to log the completion of reporting the payload to DTAGENT_DB.STATUS.LOG_PROCESSED_MEASUREMENTS
            event_column_to_check (str): if this columns exists in the payload, an event will be sent instead of log
            event_value_to_check (str): if the previously stated event_column_to_check exists and is not None and this argument is not None, the event will be sent if the column value is equal to event_value_to_check
            event_payload_prepare (function): additional function preparing payload for the event
        Returns:
            int: number of entries processed sent
            int: number of log entries sent
            int: number of metrics generated and sent
            int: number of events sent
        """

        __context = get_context_by_name(context_name, run_uuid)

        processed_last_timestamp = None
        processed_entries_cnt = 0
        processed_logs_cnt = 0
        processed_metrics_cnt = 0
        processed_events_cnt = 0

        last_timestamp = self._configuration.get_last_measurement_update(self._session, context_name)

        for row_dict in f_entry_generator():

            if report_metrics and self._metrics.discover_report_metrics(row_dict, start_time):
                processed_metrics_cnt += 1

            s_log_level = "INFO" if row_dict.get("status.code", "OK") == "OK" else "ERROR"
            processed_last_timestamp = row_dict.get("TIMESTAMP", None)

            if report_timestamp_events and len(_unpack_json_dict(row_dict, ["EVENT_TIMESTAMPS"])) > 0:

                for key, ts in _unpack_json_dict(row_dict, ["EVENT_TIMESTAMPS"]).items():
                    ts_dt = _get_timestamp_in_sec(ts, NANOSECOND_CONVERSION_RATE)

                    if ts_dt >= last_timestamp:

                        if self._events.report_via_api(
                            query_data=row_dict,
                            title=f"Table event {key}.",
                            additional_payload={
                                "timestamp": ts,
                                EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME: key,
                            },
                            start_time_key=start_time,
                            event_type=EventType.CUSTOM_INFO,
                            end_time_key=end_time,
                            context=__context,
                        ):
                            processed_events_cnt += 1

            if event_payload_prepare is not None and self._has_event(
                value_to_compare=event_value_to_check, column_value=row_dict.get(event_column_to_check, None)
            ):
                event_type, title, properties = event_payload_prepare(row_dict)
                if self._events.report_via_api(
                    query_data=row_dict,
                    event_type=event_type,
                    title=title,
                    start_time_key=start_time,
                    end_time_key=end_time,
                    additional_payload=properties,
                    context=__context,
                ):
                    processed_events_cnt += 1
            elif report_logs:
                log_dict = _unpack_json_dict(
                    row_dict,
                    ["DIMENSIONS", "ATTRIBUTES", "METRICS", "EVENT_TIMESTAMPS"],
                )

                event_dict = _cleanup_dict({"timestamp": processed_last_timestamp, **log_dict})

                self._logs.send_log(
                    row_dict.get("_MESSAGE", context_name),
                    extra=event_dict,
                    log_level=getattr(logging, s_log_level, logging.INFO),
                    context=__context,
                )
                processed_logs_cnt += 1

            processed_entries_cnt += 1

            if processed_entries_cnt % 100:  # invoking garbage collection every 100 entries.

                gc.collect()

        entries_dict = {"processed_entries_cnt": processed_entries_cnt, "processed_events_cnt": processed_events_cnt}
        if report_logs:
            entries_dict["processed_logs_cnt"] = processed_logs_cnt
        if report_metrics:
            entries_dict["processed_metrics_cnt"] = processed_metrics_cnt

        if log_completion:
            self._report_execution(
                context_name,
                str(processed_last_timestamp),
                None,
                entries_dict,
            )

        if processed_metrics_cnt > 0:
            self._metrics.flush_metrics()

        return processed_entries_cnt, processed_logs_cnt, processed_metrics_cnt, processed_events_cnt

    @abstractmethod
    def process(self, run_proc: bool = True):
        """Abstract method for plugin processing."""
        # Implement method process() at plugins


def _get_plugin_class(source: str) -> Union[Plugin, str]:
    """Returns plugin class by name specified, if no plugin matches, returns a warning."""

    s_class_name = f"{source.title().replace('_', '')}Plugin"
    c_source = globals().get(s_class_name, None)

    if inspect.isclass(c_source) and hasattr(c_source, "process") and inspect.isfunction(getattr(c_source, "process", None)):

        return c_source

    warning = f"""Plugin {source} not implemented (properly?):
        class name  = {s_class_name},
        in globals  = {c_source is not None},
        is class    = {inspect.isclass(c_source)},
        has process = {hasattr(c_source, 'process')}
        is function = {inspect.isfunction(getattr(c_source, 'process', None))}
        """

    return warning


##endregion

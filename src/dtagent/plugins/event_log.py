"""
Plugin file for processing event log plugin data.
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
import gc
import logging
from typing import Dict, Generator, Tuple
import pandas as pd
from dtagent import LOG, LL_TRACE
from dtagent.util import _unpack_json_dict
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name, CONTEXT_NAME, RUN_ID_NAME

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: EVENT LOG --------------------------------


class EventLogPlugin(Plugin):
    """
    Event log plugin class.
    """

    def _get_events(self) -> Generator[Dict, None, None]:
        """Fetches data from APP.EVENT_LOG, with limit set in configuration."""

        t_event_log = "APP.V_EVENT_LOG"
        i_limit = self._configuration.get(plugin_name="event_log", key="max_entries", default_value=10000)
        df_recent_events = self._session.table(t_event_log).limit(i_limit)

        for row in df_recent_events.collect():
            row_dict = row.as_dict(recursive=True)

            yield row_dict

    def _process_log_entries(self, __context: Dict[str, str], resource_attributes: Dict, run_proc: bool = True) -> int:
        """Processing entries that are not metrics"""
        processed_last_timestamp = None
        processed_entries_cnt = 0

        for row_dict in self._get_events():
            unpacked_dicts = _unpack_json_dict(
                row_dict, ["_RECORD", "_RECORD_ATTRIBUTES", "_RESOURCE_ATTRIBUTES", "_VALUE_OBJECT"]
            )
            prefixed_dicts = {
                f"snowflake.event.scope.{k}": v for k, v in _unpack_json_dict(row_dict, ["_SCOPE"]).items()
            }
            reserved_dicts = _unpack_json_dict(row_dict, ["_RESERVED"])
            s_log_level = unpacked_dicts.get("severity_text", "INFO")

            event_dict = {
                k.lower(): v
                for k, v in row_dict.items()
                if (k != "START_TIME" or not pd.isna(v)) and k[0] != "_"  # no empty start_time or _underscored keys
            }

            self._logs.send_log(
                str(row_dict.get("_CONTENT") or row_dict.get("_MESSAGE", "event log entry")),
                extra={**unpacked_dicts, **prefixed_dicts, **reserved_dicts, **event_dict, **resource_attributes},
                log_level=getattr(logging, s_log_level, logging.INFO),
                context=__context,
            )

            processed_last_timestamp = row_dict.get("TIMESTAMP", None)
            processed_entries_cnt += 1

            if processed_entries_cnt % 100:  # invoking garbage collection every 100 entries.

                gc.collect()

        if processed_last_timestamp and run_proc:
            self._report_execution(
                "event_log",
                str(processed_last_timestamp),
                None,
                {"entries": processed_entries_cnt},
            )

        return processed_entries_cnt

    def _process_metric_entries(self, __context: Dict[str, str], run_proc: bool = True) -> Tuple[int, int, int, int]:
        t_event_log_metrics_instrumented = "APP.V_EVENT_LOG_METRICS_INSTRUMENTED"
        (metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt) = self._log_entries(
            lambda: self._get_table_rows(t_event_log_metrics_instrumented),
            context_name="event_log_metrics",
            run_uuid=__context[RUN_ID_NAME],
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        return metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt

    def _process_span_entries(self, __context: Dict[str, str], run_proc: bool = True) -> int:
        t_event_log_spans_instrumented = "APP.V_EVENT_LOG_SPANS_INSTRUMENTED"
        span_count = 0
        processing_errors = []
        span_events_added = 0
        context_name = "event_log_spans"
        context = {**__context, CONTEXT_NAME: context_name}

        for row_dict in self._get_table_rows(t_event_log_spans_instrumented):
            _span_id = row_dict.get("_SPAN_ID", None)

            if _span_id is None:
                LOG.warning("Problem with given row in event log: %s", row_dict)
            else:
                LOG.log(LL_TRACE, "Processing query history for %s", _span_id)
                span_events_added += self._process_row(
                    row=row_dict,
                    processed_ids=None,
                    processing_errors=processing_errors,
                    row_id_col="_SPAN_ID",
                    parent_row_id_col="_PARENT_SPAN_ID",
                    view_name=t_event_log_spans_instrumented,
                    context=context,
                )
                span_count += 1

        if not self._spans.flush_traces():
            processing_errors.append("Problem flushing traces")

        processing_errors_count = len(processing_errors)
        if processing_errors_count > 0:
            LOG.warning("Following problems where discovered when processing event log traces: %s", processing_errors)

        from snowflake.snowpark.functions import current_timestamp

        if run_proc:
            self._report_execution(
                context_name,
                current_timestamp(),
                None,
                {
                    "even_log_span_count": span_count,
                    "processing_errors_count": processing_errors_count,
                    "span_events_added_count": span_events_added,
                },
            )

        return span_count

    def process(self, run_proc: bool = True) -> int:
        """
        Analyzes changes in the event log
        """
        __context = get_context_by_name("event_log")
        resource_attributes = self._configuration.get("resource.attributes")

        m_entries_cnt, m_logs_cnt, m_metrics_cnt, m_event_cnt = self._process_metric_entries(__context, run_proc)
        s_entries_cnt = self._process_span_entries(__context, run_proc)
        l_entries_cnt = self._process_log_entries(__context, resource_attributes, run_proc)

        return (
            l_entries_cnt + m_entries_cnt + s_entries_cnt,
            l_entries_cnt + m_logs_cnt,
            m_metrics_cnt,
            m_event_cnt,
            s_entries_cnt,  # number of spans created
        )


##endregion

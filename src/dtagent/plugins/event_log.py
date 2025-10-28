"""
Plugin file for processing event log plugin data.
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
from typing import Dict, Generator, Tuple
import uuid
import pandas as pd
from dtagent.util import _unpack_json_dict
from dtagent.plugins import Plugin

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

    def _process_log_line(self, row_dict, __context, log_level):  # pylint: disable=unused-argument
        """Processes single log line for event log"""

        unpacked_dicts = _unpack_json_dict(row_dict, ["_RECORD", "_RECORD_ATTRIBUTES", "_RESOURCE_ATTRIBUTES", "_VALUE_OBJECT"])
        prefixed_dicts = {f"snowflake.event.scope.{k}": v for k, v in _unpack_json_dict(row_dict, ["_SCOPE"]).items()}
        reserved_dicts = _unpack_json_dict(row_dict, ["_RESERVED"])
        s_log_level = unpacked_dicts.get("severity_text", "INFO")

        event_dict = {
            k.lower(): v
            for k, v in row_dict.items()
            if (k != "START_TIME" or not pd.isna(v)) and k[0] != "_"  # no empty start_time or _underscored keys
        }

        self._logs.send_log(
            str(row_dict.get("_CONTENT") or row_dict.get("_MESSAGE", "event log entry")),
            extra={**unpacked_dicts, **prefixed_dicts, **reserved_dicts, **event_dict, **self._configuration.get("resource.attributes")},
            log_level=getattr(logging, s_log_level, logging.INFO),
            context=__context,
        )

        return True

    def _process_log_entries(self, run_id: str, run_proc: bool = True) -> int:
        """Processing entries that are not metrics"""

        processed_entries_cnt, _, _, _ = self._log_entries(
            f_entry_generator=self._get_events,
            context_name="event_log",
            run_uuid=run_id,
            report_metrics=False,
            report_timestamp_events=False,
            f_report_log=self._process_log_line,
            log_completion=run_proc,
        )

        return processed_entries_cnt

    def _process_metric_entries(self, run_id: str, run_proc: bool = True) -> Tuple[int, int, int, int]:
        """Processes metric entries for event log"""

        t_event_log_metrics_instrumented = "APP.V_EVENT_LOG_METRICS_INSTRUMENTED"
        (metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt) = self._log_entries(
            lambda: self._get_table_rows(t_event_log_metrics_instrumented),
            context_name="event_log_metrics",
            run_uuid=run_id,
            start_time="TIMESTAMP",
            log_completion=run_proc,
        )

        return metric_entries_cnt, metric_logs_cnt, metric_metrics_cnt, metric_event_cnt

    def _process_span_entries(self, run_id, run_proc: bool = True) -> int:
        """Processes span entries for event log"""

        s_entries, _, _, _, _ = self._process_span_rows(
            f_entry_generator=lambda: self._get_table_rows("APP.V_EVENT_LOG_SPANS_INSTRUMENTED"),
            view_name="APP.V_EVENT_LOG_SPANS_INSTRUMENTED",
            context_name="event_log_spans",
            run_uuid=run_id,
            query_id_col_name="_SPAN_ID",
            parent_query_id_col_name="_PARENT_SPAN_ID",
            log_completion=run_proc,
        )

        return len(s_entries)

    def process(self, run_proc: bool = True) -> int:
        """
        Analyzes changes in the event log
        """
        run_id = str(uuid.uuid4().hex)

        s_entries_cnt = self._process_span_entries(run_id, run_proc)
        m_entries_cnt, m_logs_cnt, m_metrics_cnt, m_event_cnt = self._process_metric_entries(run_id, run_proc)
        l_entries_cnt = self._process_log_entries(run_id, run_proc)

        return (
            l_entries_cnt + m_entries_cnt + s_entries_cnt,
            l_entries_cnt + m_logs_cnt,
            m_metrics_cnt,
            m_event_cnt,
            s_entries_cnt,  # number of spans created
        )


##endregion

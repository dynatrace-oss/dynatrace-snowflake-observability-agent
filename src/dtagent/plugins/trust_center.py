"""
Plugin file for processing trust center plugin data.
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
import uuid
import logging
from dtagent.otel.events import EventType
from dtagent.plugins import Plugin
from dtagent.context import get_context_by_name
from dtagent.util import _unpack_json_dict
from dtagent import LOG

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: TRUST CENTER --------------------------------


class TrustCenterPlugin(Plugin):
    """
    Trust center plugin class.
    """

    @staticmethod
    def __to_loglevel(severity):
        """Maps severity from the given severity to log level"""
        severity_mapping = {
            "CRITICAL": logging.CRITICAL,
            "HIGH": logging.ERROR,
            "MEDIUM": logging.WARN,
            "LOW": logging.INFO,
        }
        return severity_mapping.get(severity, logging.INFO)

    def process(self, run_proc: bool = True) -> int:
        """
        Processes data for trust center plugin.
        Returns
            processed_entries_cnt [int]: number of entries reported from APP.V_TRUST_CENTER,
        """

        run_id = str(uuid.uuid4().hex)
        __context = get_context_by_name("trust_center", run_id=run_id)

        processed_entries_cnt = 0
        metrics_sent_cnt = 0
        events_sent_cnt = 0
        processed_last_timestamp = None
        t_trust_center_history = "APP.V_TRUST_CENTER_INSTRUMENTED"
        t_trust_center_metrics = "APP.V_TRUST_CENTER_METRICS"

        _, _, metrics_sent_cnt, _ = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_trust_center_metrics),
            context_name="trust_center",
            run_uuid=run_id,
            log_completion=False,
            report_logs=False,
            report_metrics=True,
            report_timestamp_events=False,
        )

        for row_dict in self._get_table_rows(t_trust_center_history):
            unpacked_dicts = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])

            _message = row_dict.get("_MESSAGE")
            log_level = TrustCenterPlugin.__to_loglevel(unpacked_dicts.get("_SEVERITY"))
            processed_last_timestamp = row_dict.get("TIMESTAMP", None)

            self._logs.send_log(
                f"TrustCenter event: {_message}",
                extra={
                    "timestamp": processed_last_timestamp,
                    "event.start": row_dict.get("EVENT_START"),
                    "event.end": row_dict.get("EVENT_END"),
                    "status_code": row_dict.get("STATUS_CODE"),
                    **unpacked_dicts,
                },
                log_level=log_level,
                context=__context,
            )

            if self._has_event(column_value=unpacked_dicts.get("vulnerability.risk.level", None), value_to_compare="CRITICAL"):
                if self._events.report_via_api(
                    query_data=row_dict,
                    event_type=EventType.CUSTOM_ALERT,
                    title="Trust Center Critical problem",
                    start_time_key="EVENT_START",
                    end_time_key="EVENT_END",
                    context=__context,
                ):
                    events_sent_cnt += 1
                else:
                    LOG.warning("Could not send event from trust center plugin")

            processed_entries_cnt += 1

        if run_proc:
            self._report_execution(
                "trust_center",
                str(processed_last_timestamp),
                None,
                {"entries": processed_entries_cnt, "metrics_sent": metrics_sent_cnt, "events_sent": events_sent_cnt},
            )

        return processed_entries_cnt


##endregion

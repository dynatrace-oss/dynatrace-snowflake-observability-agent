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
from dtagent.util import _unpack_json_dict
from typing import Tuple, Dict

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: TRUST CENTER --------------------------------


class TrustCenterPlugin(Plugin):
    """
    Trust center plugin class.
    """

    def _get_severity_log_level(self, row_dict) -> str:
        """Maps severity from the given severity to log level"""
        severity_mapping = {
            "CRITICAL": logging.CRITICAL,
            "HIGH": logging.ERROR,
            "MEDIUM": logging.WARN,
            "LOW": logging.INFO,
        }
        return severity_mapping.get(row_dict.get("_SEVERITY"), logging.INFO)

    def _report_instrumented_log(self, row_dict, __context, log_level):
        """Defines custom log reporting approach"""
        unpacked_dicts = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])

        self._logs.send_log(
            f"TrustCenter event: {row_dict.get('_MESSAGE')}",
            extra={
                "timestamp": self.processed_last_timestamp,
                "event.start": row_dict.get("EVENT_START"),
                "event.end": row_dict.get("EVENT_END"),
                "status_code": row_dict.get("STATUS_CODE"),
                **unpacked_dicts,
            },
            log_level=log_level,
            context=__context,
        )

        return True

    def _prepare_event_payload_critical_risk(self, row_dict: dict) -> Tuple[EventType, str, Dict]:  # pylint: disable=unused-argument
        """Defines what payload should be sent once vulnerability.risk.level is CRITICAL"""

        return EventType.CUSTOM_ALERT, "Trust Center Critical problem", {}

    def process(self, run_proc: bool = True) -> int:
        """
        Processes data for trust center plugin.
        Returns
            processed_entries_cnt [int]: number of entries reported from APP.V_TRUST_CENTER,
        """

        run_id = str(uuid.uuid4().hex)

        _, _, metrics_sent_cnt, _ = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_TRUST_CENTER_METRICS"),
            context_name="trust_center",
            run_uuid=run_id,
            log_completion=False,
            report_logs=False,
            report_metrics=True,
            report_timestamp_events=False,
        )

        processed_entries_cnt, _, _, events_sent_cnt = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows("APP.V_TRUST_CENTER_INSTRUMENTED"),
            context_name="trust_center",
            run_uuid=run_id,
            log_completion=False,
            start_time="EVENT_START",
            end_time="EVENT_END",
            event_column_to_check="vulnerability.risk.level",
            event_value_to_check="CRITICAL",
            event_payload_prepare=self._prepare_event_payload_critical_risk,
            f_report_log=self._report_instrumented_log,
            f_get_log_level=self._get_severity_log_level,
        )

        if run_proc:
            self._report_execution(
                "trust_center",
                str(self.processed_last_timestamp),
                None,
                {"entries": processed_entries_cnt, "metrics_sent": metrics_sent_cnt, "events_sent": events_sent_cnt},
            )

        return processed_entries_cnt


##endregion

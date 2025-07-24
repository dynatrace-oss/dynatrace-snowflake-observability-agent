"""Mechanisms allowing for parsing and sending metrics"""

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
import sys

from typing import Dict, Union, Optional
from dtagent.otel.otel_manager import OtelManager
from dtagent.util import get_timestamp_in_ms, get_now_timestamp
from dtagent.otel import _log_warning, USER_AGENT


##endregion COMPILE_REMOVE

##region ------------------------ OpenTelemetry METRICS ---------------------------------


class Metrics:
    """Allows for parsing and sending metrics data."""

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    def __init__(self, instruments: Instruments, configuration: Configuration):
        self.PAYLOAD_CACHE: str = ""
        self._configuration = configuration
        self._instruments = instruments
        self._resattr_dims = {
            k: v for k, v in self._configuration.get("resource.attributes").items() if not k.startswith("telemetry.exporter.")
        }
        self._max_retries = self._configuration.get(otel_module="metrics", key="max_retries", default_value=5)
        self._max_batch_size = self._configuration.get(otel_module="metrics", key="max_batch_size", default_value=1000000)

    def _send_metrics(self, payload: Optional[str] = None) -> bool:
        """
        Sends given payload of metrics with metadata to Dynatrace.
        The code attempts to accumulate to the maximal size of payload allowed - and
        will flush before we would exceed with new payload increment.
        IMPORTANT: call _flush_metrics() to flush at the end of processing
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE

        def __send(_payload: str, _retries: int = 0) -> bool:
            """
            Sends given payload to Dynatrace
            """
            import requests

            headers = {
                "Authorization": f'Api-Token {self._configuration.get("dt.token")}',
                "Content-Type": "text/plain",
                "User-Agent": USER_AGENT,
            }
            data_sent_ok = True

            try:
                response = requests.post(
                    self._configuration.get("metrics.http"),
                    headers=headers,
                    data=_payload.replace("\n\n", "\n"),
                    timeout=15 if _retries < 2 else 30,
                )

                LOG.log(LL_TRACE, "Sent %d bytes of metrics payload; response: %s", len(_payload), response.status_code)

                if response.status_code != 202:
                    _log_warning(response, _payload, "metric")
                else:
                    OtelManager.set_current_fail_count(0)

            except requests.exceptions.RequestException as e:
                if isinstance(e, requests.exceptions.Timeout):
                    LOG.error(
                        "The request to send %d bytes with metrics timed out after 5 minutes. (retry = %d)",
                        len(_payload),
                        _retries,
                    )
                else:
                    LOG.error(
                        "An error occurred when sending %d bytes with metrics (retry = %d): %s",
                        len(_payload),
                        _retries,
                        e,
                    )

                if _retries < self._max_retries:
                    __send(_payload, _retries + 1)
                else:
                    LOG.warning("Failed to send metrics within 3 attempts")
                    OtelManager.increase_current_fail_count(response)
                    OtelManager.verify_communication()
                    data_sent_ok = False

            return data_sent_ok

        data_sent_ok = True

        if (
            payload is not None
            and payload.strip() != ""
            and (sys.getsizeof(self.PAYLOAD_CACHE.encode("utf-8")) + sys.getsizeof(payload.encode("utf-8"))) < self._max_batch_size
        ):
            self.PAYLOAD_CACHE += f"\n{payload}" if self.PAYLOAD_CACHE != "" else payload
        else:
            if len(self.PAYLOAD_CACHE) > 0:
                data_sent_ok = __send(self.PAYLOAD_CACHE)
            self.PAYLOAD_CACHE = payload or ""

        return data_sent_ok

    def flush_metrics(self) -> bool:
        """
        Flush metrics cache
        """
        return self._send_metrics()

    def report_via_metrics_api(self, query_data: Dict, start_time: str = "START_TIME") -> bool:
        """
        Generates payload with Metrics v2 API
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE
        from dtagent.util import _unpack_json_dict, _esc, _check_timestamp_ms, _is_not_blank  # COMPILE_REMOVE

        local_metrics_def = _unpack_json_dict(query_data, ["_INSTRUMENTS_DEF"])

        def __combined_dimensions(unpacked_dict: Dict[str, str]) -> str:
            """
            Helper function that renders given dictionary as Dynatrace metrics line.
            """
            return ",".join(f'{_esc(k)}="{_esc(item)}"' for k, item in unpacked_dict.items())

        def __payload_lines(dimensions: str, metric_name: str, metric_value: Union[str, dict], ts: Optional[int]) -> str:
            """Renders a complete, single line with metric information

            Args:
                dimensions (str): Comma separated list of dimension name=value pairs
                metric_name (str): metric identifier under which given values will be reported
                metric_value (Union[str, dict]): Value of the metric.
                                                 If it is a string or number - we will simply report this number
                                                 (You can omit the format if you're using a single value gauge payload.
                                                 In that case, the provided value is used for all summaries and the count is set to 1.)
                                                 However, we should also expect to get a dictionary with (min, max, sum, count) keys,
                                                 which should be reported according to Dynatrace specification:
                                                 https://docs.dynatrace.com/docs/extend-dynatrace/extend-metrics/reference/metric-ingestion-protocol#payload
                ts (Optional[int]): Optional value of the timestamp under which we should report that;
                                    if not provided we send metric line without timeout information

            Returns:
                str: Text payload reporting single metric with given set of dimensions
            """
            if isinstance(metric_value, dict):
                if len(metric_value) == 1:  # from Snowflake Trail we are sometimes (always?) getting single values
                    value = next(iter(metric_value.values()))
                else:
                    if "gauge" in metric_value:  # Snowflake Trail sends gauge instead of count, DT expects the other
                        metric_value["count"] = metric_value.pop("gauge")
                    value = "gauge," + ",".join([f"{k}={v}" for k, v in metric_value.items() if k in ("min", "max", "sum", "count")])
            else:
                value = metric_value
            return (
                f"{metric_name},{dimensions} {value}"
                + ("" if ts is None else f" {ts}")
                + "\n"
                + self._instruments.get_metric_definition(metric_name, local_metrics_def)
            )

        timestamp = get_timestamp_in_ms(query_data, start_time, 1e6, int(get_now_timestamp().timestamp() * 1000))
        timestamp = _check_timestamp_ms(timestamp)

        payload_lines = []
        # list all dimensions with their values from the provided data
        all_dimensions = {**self._resattr_dims, **_unpack_json_dict(query_data, ["DIMENSIONS"])}
        LOG.log(LL_TRACE, "all_dimensions = %r", all_dimensions)

        # prepare dimensions for metrics
        combined_dimensions = __combined_dimensions(all_dimensions)
        LOG.log(LL_TRACE, "combined_dimensions = %r", combined_dimensions)

        for metric_name, metric_value in _unpack_json_dict(query_data, ["METRICS"]).items():
            LOG.log(LL_TRACE, "###\nmetric_name=%r, metric_value=%r", metric_name, metric_value)
            if _is_not_blank(metric_value):
                payload_line = __payload_lines(combined_dimensions, metric_name, metric_value, timestamp)
                payload_lines += [payload_line]
                LOG.log(LL_TRACE, "payload_lines:\n%s", payload_line)

        payload = "\n".join(payload_lines)

        return self._send_metrics(payload)

    def discover_report_metrics(self, query_data: Dict, start_time: str = "START_TIME") -> bool:
        """
        Checks if METRICS section is defined in query data, returns false if not
        otherwise reports metrics and returns result of report_via_metrics_api
        """
        if "METRICS" in query_data:
            return self.report_via_metrics_api(query_data, start_time)
        return False


##endregion

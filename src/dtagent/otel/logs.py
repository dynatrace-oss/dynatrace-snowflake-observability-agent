"""Mechanisms allowing for parsing and sending logs"""

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
from typing import Dict, Optional, Any
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider
from dtagent.util import get_timestamp_in_ms, validate_timestamp_ms
from dtagent.otel import IS_OTEL_BELOW_1_21
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager

##endregion COMPILE_REMOVE

##region ------------------------ OpenTelemetry LOGS ---------------------------------


class Logs:
    """Main Logs class"""

    from dtagent.config import Configuration  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/otlp/v1/logs"

    def __init__(self, resource: Resource, configuration: Configuration):
        self._otel_logger: Optional[logging.Logger] = None
        self._otel_logger_provider: Optional[LoggerProvider] = None
        self._configuration = configuration

        self._setup_logger(resource)

    def _setup_logger(self, resource: Resource) -> None:
        """All necessary actions to initialize logging via OpenTelemetry"""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk._logs import LoggingHandler

        class CustomUserAgentOTLPLogExporter(OTLPLogExporter):
            """Custom OTLP Log Exporter that sets a custom User-Agent header."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._session.headers.update(OtelManager.get_dsoa_headers())

        self._otel_logger_provider = LoggerProvider(resource=resource)
        self._otel_logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                CustomUserAgentOTLPLogExporter(
                    endpoint=f'{self._configuration.get("logs.http")}',
                    headers={"Authorization": f'Api-Token {self._configuration.get("dt.token")}'},
                    session=CustomLoggingSession(),
                ),
                export_timeout_millis=self._configuration.get(otel_module="logs", key="export_timeout_millis", default_value=10000),
                max_export_batch_size=self._configuration.get(otel_module="logs", key="max_export_batch_size", default_value=100),
            )
        )
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=self._otel_logger_provider)

        self._otel_logger = logging.getLogger("DTAGENT_OTLP")
        self._otel_logger.setLevel(logging.NOTSET)
        self._otel_logger.addHandler(handler)

    def send_log(
        self,
        message: str,
        extra: Optional[Dict] = None,
        log_level: int = logging.INFO,
        context: Optional[Dict] = None,
    ):
        """Util function to ensure we send logs correctly"""
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE
        from dtagent.util import _to_json, _cleanup_data, _cleanup_dict  # COMPILE_REMOVE

        def __adjust_log_attribute(key: str, value: Any) -> Any:
            """Ensures following things:
            - numeric timestamps are converted to strings
            - non-primitive type values are sent as JSON strings (only for otel < 1.21.0)
            """
            if key == "timestamp" and str(value).isnumeric():
                value = str(int(value))

            if IS_OTEL_BELOW_1_21 and not isinstance(value, (bool, str, bytes, int, float)):
                value = _to_json(value)

            return value

        # the following conversions through JSON are necessary to ensure certain objects like datetime are properly serialized,
        # otherwise OTEL seems to be sending objects cannot be deserialized on the Dynatrace side
        o_extra = {k: __adjust_log_attribute(k, v) for k, v in _cleanup_data(extra).items() if v} if extra else {}

        observed_timestamp = get_timestamp_in_ms(o_extra, "timestamp")
        if observed_timestamp:
            timestamp = validate_timestamp_ms(observed_timestamp)
            o_extra["timestamp"] = timestamp

        LOG.log(LL_TRACE, o_extra)
        payload = _cleanup_dict(
            {
                "observed_timestamp": observed_timestamp or "",
                **o_extra,
                **(context or {}),
            }
        )
        if message is None:
            message = "-"

        if IS_OTEL_BELOW_1_21:
            self._otel_logger.log(level=log_level, msg=message, extra=payload)
            LOG.log(
                LL_TRACE,
                "Sent log %s with extra content of count %d at level %d",
                message,
                len(o_extra),
                log_level,
            )
        else:
            self._otel_logger.log(level=log_level, msg={"content": message, **payload})
            LOG.log(
                LL_TRACE,
                "Sent log %s with message content of count %d at level %d",
                message,
                len(o_extra),
                log_level,
            )

        OtelManager.verify_communication()

    def flush_logs(self) -> None:
        """Flushes remaining logs."""

        if self._otel_logger_provider:
            self._otel_logger_provider.force_flush()

    def shutdown_logger(self) -> None:
        """Flushes remaining logs and shuts down the logger."""

        if self._otel_logger_provider:
            self._otel_logger_provider.force_flush()
            self._otel_logger_provider.shutdown()


##endregion

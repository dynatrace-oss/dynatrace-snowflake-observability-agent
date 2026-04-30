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
from dtagent.util import process_timestamps_for_telemetry
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager

##endregion COMPILE_REMOVE

from opentelemetry._logs import SeverityNumber  # pylint: disable=ungrouped-imports

##region ------------------------ OpenTelemetry LOGS ---------------------------------

_SEVERITY_MAP = {
    5: SeverityNumber.TRACE,
    logging.DEBUG: SeverityNumber.DEBUG,
    logging.INFO: SeverityNumber.INFO,
    logging.WARNING: SeverityNumber.WARN,
    logging.ERROR: SeverityNumber.ERROR,
    logging.CRITICAL: SeverityNumber.FATAL,
}


class Logs:
    """Main Logs class for sending logs via Dynatrace OTLP Logs API.

    API Specifications:
    - Dynatrace OTLP Logs: https://docs.dynatrace.com/docs/ingest-from/opentelemetry/otlp-api/ingest-logs
    - OTLP Logs Standard: https://opentelemetry.io/docs/specs/otel/logs/data-model/

    Note: ``timestamp`` is passed as nanoseconds (OTLP standard) via ``Logger.emit()``.
    ``observed_timestamp`` is also in nanoseconds per OTLP standard.
    """

    from dtagent.config import Configuration  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/otlp/v1/logs"

    def __init__(self, resource: Resource, configuration: Configuration):
        """Initialize the OTLP logs exporter."""
        self._otel_logger: Optional[Any] = None
        self._otel_logger_provider: Optional[LoggerProvider] = None
        self._configuration = configuration

        self._setup_logger(resource)

    def __get_logger_name(self) -> str:
        """We use a custom logger name to be able to distinguish logs coming from different agents in case of multitenancy,
           and also to be able to filter them out if needed.

        NOTE: this code is broken into pieces to avoid replacement in prepare_deploy_script in case of multitenancy_tag being set
        """
        logger_name = "DTAGENT"
        if self._configuration.multitenancy_tag:
            logger_name += f"_{self._configuration.multitenancy_tag}"
        logger_name += "_OTLP"
        return logger_name

    def _setup_logger(self, resource: Resource) -> None:
        """All necessary actions to initialize logging via OpenTelemetry"""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

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
        self._otel_logger = self._otel_logger_provider.get_logger(self.__get_logger_name())

    def send_log(
        self,
        message: Optional[str],
        extra: Optional[Dict] = None,
        log_level: int = logging.INFO,
        context: Optional[Dict] = None,
    ):
        """Util function to ensure we send logs correctly"""
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE
        from dtagent.util import _cleanup_data, _cleanup_dict  # COMPILE_REMOVE

        def __adjust_log_attribute(key: str, value: Any) -> Any:
            if key == "timestamp" and str(value).isnumeric():
                value = str(int(value))
            return value

        # the following conversions through JSON are necessary to ensure certain objects like datetime are properly serialized,
        # otherwise OTEL seems to be sending objects cannot be deserialized on the Dynatrace side
        o_extra = {k: __adjust_log_attribute(k, v) for k, v in _cleanup_data(extra).items() if v is not None} if extra else {}

        validated_timestamp_ms, validated_observed_timestamp_ns = process_timestamps_for_telemetry(o_extra)

        # pop timestamp fields — they go as direct emit params, not attributes
        o_extra.pop("timestamp", None)
        o_extra.pop("observed_timestamp", None)

        LOG.log(LL_TRACE, o_extra)

        raw_payload = o_extra | (context or {})
        if raw_payload.get("telemetry.sdk.language") == "python":
            del raw_payload["telemetry.sdk.language"]

        payload = _cleanup_dict(raw_payload)

        if message is None:
            message = "-"

        self._otel_logger.emit(
            timestamp=validated_timestamp_ms * 1_000_000 if validated_timestamp_ms else None,
            observed_timestamp=validated_observed_timestamp_ns,
            severity_number=_SEVERITY_MAP.get(log_level, SeverityNumber.INFO),
            severity_text=logging.getLevelName(log_level),
            body=message,
            attributes=payload if payload else None,
        )
        LOG.log(LL_TRACE, "Sent log %s with extra content of count %d at level %d", message, len(o_extra), log_level)
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

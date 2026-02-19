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
from dtagent.util import get_timestamp, validate_timestamp, process_timestamps_for_telemetry
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager

##endregion COMPILE_REMOVE

##region ------------------------ OpenTelemetry LOGS ---------------------------------


class Logs:
    """Main Logs class for sending logs via Dynatrace OTLP Logs API.

    API Specifications:
    - Dynatrace OTLP Logs: https://docs.dynatrace.com/docs/ingest-from/opentelemetry/otlp-api/ingest-logs
    - OTLP Logs Standard: https://opentelemetry.io/docs/specs/otel/logs/data-model/

    Note: Dynatrace requires timestamps in milliseconds (UTC milliseconds, RFC3339, or RFC3164),
    which differs from the OTLP standard that specifies nanoseconds. However, `observed_timestamp`
    must be in nanoseconds per OTLP standard to preserve original timestamp precision.
    """

    from dtagent.config import Configuration  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/otlp/v1/logs"

    def __init__(self, resource: Resource, configuration: Configuration):
        """Initialize the OTLP logs exporter."""
        self._otel_logger: Optional[logging.Logger] = None
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
        from opentelemetry.sdk._logs import LoggingHandler

        class CustomUserAgentOTLPLogExporter(OTLPLogExporter):
            """Custom OTLP Log Exporter that sets a custom User-Agent header."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._session.headers.update(OtelManager.get_dsoa_headers())

        class CustomOTelTimestampFilter(logging.Filter):
            """Reads record.timestamp (int epoch milliseconds) and applies it to the Python LogRecord timing fields.

            Also validates record.observed_timestamp and converts it to nanoseconds for OTEL.
            """

            def filter(self, record: logging.LogRecord) -> bool:
                # Handle timestamp field (for log record timing)
                ts_attr = getattr(record, "timestamp", None)
                if ts_attr is not None:
                    delattr(record, "timestamp")

                    try:
                        ts_val = int(ts_attr)
                        # Validate with auto-detection and convert to milliseconds using standard validation
                        validated_ts_ms = validate_timestamp(ts_val, return_unit="ms")
                        if validated_ts_ms:
                            record.created = validated_ts_ms / 1_000
                            record.msecs = validated_ts_ms % 1_000
                    except (ValueError, TypeError, OverflowError):
                        # If conversion fails, use default timestamp
                        pass

                # Handle observed_timestamp field (must be in nanoseconds per OTLP standard)
                observed_ts_attr = getattr(record, "observed_timestamp", None)
                if observed_ts_attr is not None:
                    try:
                        observed_ts_val = int(observed_ts_attr)
                    except (ValueError, TypeError, OverflowError):
                        delattr(record, "observed_timestamp")
                    else:
                        # Validate with auto-detection and return nanoseconds; skip range validation to preserve original observed_timestamp
                        validated_ts_ns = validate_timestamp(
                            observed_ts_val,
                            return_unit="ns",
                            skip_range_validation=True,
                        )
                        if validated_ts_ns:
                            setattr(record, "observed_timestamp", validated_ts_ns)
                        else:
                            delattr(record, "observed_timestamp")

                return True

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
        handler.addFilter(CustomOTelTimestampFilter())

        self._otel_logger = logging.getLogger(self.__get_logger_name())
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

            return value

        # the following conversions through JSON are necessary to ensure certain objects like datetime are properly serialized,
        # otherwise OTEL seems to be sending objects cannot be deserialized on the Dynatrace side
        o_extra = {k: __adjust_log_attribute(k, v) for k, v in _cleanup_data(extra).items() if v} if extra else {}

        # Process timestamps using standard pattern:
        # - timestamp in milliseconds (Dynatrace OTLP Logs API deviation from spec)
        # - observed_timestamp in nanoseconds (per OTLP standard)
        validated_timestamp_ms, validated_observed_timestamp_ns = process_timestamps_for_telemetry(o_extra)

        if validated_timestamp_ms:
            o_extra["timestamp"] = validated_timestamp_ms

        LOG.log(LL_TRACE, o_extra)

        raw_payload = o_extra | (context or {})
        if (
            raw_payload.get("telemetry.sdk.language") == "python"
        ):  # remove telemetry.sdk.language="python" which is added by OTEL by default as resource attribute
            del raw_payload["telemetry.sdk.language"]

        # Add observed_timestamp if available (in nanoseconds per OTLP standard)
        if validated_observed_timestamp_ns:
            raw_payload["observed_timestamp"] = validated_observed_timestamp_ns

        payload = _cleanup_dict(raw_payload)

        if message is None:
            message = "-"

        if payload.get("timestamp", None) is None:
            payload.pop("timestamp", None)

        self._otel_logger.log(level=log_level, msg=message, extra=payload)
        LOG.log(
            LL_TRACE,
            "Sent log %s with extra content of count %d at level %d",
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

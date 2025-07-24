"""Mechanisms allowing for parsing and sending logs"""

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

import logging
from typing import Dict, Optional, Any
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider
from dtagent.otel import IS_OTEL_BELOW_1_21, USER_AGENT
from dtagent.otel.otel_manager import CustomLoggingSession, OtelManager

##endregion COMPILE_REMOVE

##region ------------------------ OpenTelemetry LOGS ---------------------------------


class Logs:
    """Main Logs class"""

    from dtagent.config import Configuration  # COMPILE_REMOVE

    def __init__(self, resource: Resource, configuration: Configuration):
        self._otel_logger: Optional[logging.Logger] = None
        self._otel_logger_provider: Optional[LoggerProvider] = None
        self._configuration = configuration

        self._setup_logger(resource)

    def _setup_logger(self, resource: Resource) -> None:
        """
        All necessary actions to initialize logging via OpenTelemetry
        """
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk._logs import LoggingHandler

        class CustomUserAgentOTLPLogExporter(OTLPLogExporter):
            """Custom OTLP Log Exporter that sets a custom User-Agent header."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._session.headers["User-Agent"] = USER_AGENT

        self._otel_logger_provider = LoggerProvider(resource=resource)
        self._otel_logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                CustomUserAgentOTLPLogExporter(
                    endpoint=f'{self._configuration.get("otlp.http")}/v1/logs',
                    headers={"Authorization": f'Api-Token {self._configuration.get("dt.token")}'},
                    session=CustomLoggingSession(),
                )
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
        """
        Util function to ensure we send logs correctly
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE
        from dtagent.util import _to_json, _cleanup_data, _cleanup_dict  # COMPILE_REMOVE

        def __adjust_log_attribute(key: str, value: Any) -> Any:
            """
            Ensures following things:
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

        LOG.log(LL_TRACE, o_extra)
        payload = _cleanup_dict(
            {
                "observed_timestamp": o_extra.get("timestamp", ""),
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

    def shutdown_logger(self) -> None:
        """flushes remaining logs and shuts down the logger."""

        if self._otel_logger_provider:
            self._otel_logger_provider.force_flush()
            self._otel_logger_provider.shutdown()


##endregion

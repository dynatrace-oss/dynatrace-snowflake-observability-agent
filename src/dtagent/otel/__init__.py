"""Defines resource creation and IS_OTEL_BELOW_21 const."""

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

import requests
from typing import Any
from opentelemetry.sdk.resources import Resource
from opentelemetry import version as otel_version
from dtagent.config import Configuration
from dtagent.version import VERSION

##endregion COMPILE_REMOVE


##region ------------------------ OTEL INIT ----------------------------------------
def _gen_resource(config: Configuration) -> Resource:
    """Generates configuration's resource.attributes field"""
    return Resource.create(attributes=config.get("resource.attributes"))


def _log_warning(response: requests.Response, payload, source: str = "data", max_payload_length_reported: int = 100) -> None:
    """Logs a warning when sending data to Dynatrace fails.

    Args:
        response (requests.Response): The HTTP response object from the request.
        payload: The payload that was attempted to be sent.
        source (str): A string indicating the source of the data (default is "data").
        max_payload_length_reported (int): Maximum length of the payload to include in the log
    """

    from dtagent import LOG  # COMPILE_REMOVE

    LOG.warning(
        "Problem sending %s to Dynatrace; error code: %s, reason: %s, response: %s, payload: %r",
        source,
        response.status_code,
        response.reason,
        response.text,
        str(payload)[:max_payload_length_reported],
    )


class NoOpTelemetry:
    """A no-operation telemetry class used when telemetry is disabled."""

    def __init__(self):
        self.NOT_ENABLED = True

    def __getattr__(self, name):
        """Returns a no-op method for any attribute or function access."""

        def __void_method(*args, **kwargs):
            """Dummy method that will not do anything or return anything"""
            pass

        def __int_method(*args, **kwargs):
            """Dummy method that will not do anything and return 0"""
            return 0

        def __zero_tuple_method(length):
            def method(*args, **kwargs):
                """Dummy method that returns a tuple of zeros of specified length"""
                return tuple(0 for _ in range(length))

            return method

        def __dummy_discover_report_metrics(*args, **kwargs):
            """Dummy method that will not do anything and return False, 0"""
            return False, 0

        def __bool_method(*args, **kwargs):
            """Dummy method that will not do anything and return False"""
            return False

        def _not_implemented(*args, **kwargs):
            """In case a method is not implemented, log it."""
            from dtagent import LOG  # COMPILE_REMOVE

            LOG.warning(f"Method '{name}' is not implemented in NoOpTelemetry.")

        if name in ("send_log", "flush_logs", "shutdown_logger", "shutdown_tracer"):
            return __void_method

        if name in ("flush_events", "send_events", "report_via_api", "flush_metrics"):
            return __int_method

        if name in ("flush_traces", "report_via_metrics_api"):
            return __bool_method

        if name in ("discover_report_metrics"):
            return __dummy_discover_report_metrics

        if name in ("generate_span"):
            return __zero_tuple_method(3)

        return _not_implemented


NO_OP_TELEMETRY = NoOpTelemetry()


IS_OTEL_BELOW_1_21 = otel_version.__version__ < "1.21.0"

USER_AGENT = f"dsoa/{'.'.join(VERSION.split('.')[:3])}"
##endregion

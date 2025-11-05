"""Contains the base class for all otel modules"""

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
##endregion COMPILE_REMOVE

import requests
from dtagent.otel import _log_warning, USER_AGENT

##region ------------------------ OTEL base class---------------------------------


class OtelManager:
    """Class containing methods managing the failures of otel modules"""

    _max_consecutive_fails: int = 0
    _consecutive_fail_count: int = 0
    _to_abort: bool = False
    _last_response: requests.Response

    @staticmethod
    def set_max_fail_count(set_to: int = 10):
        """Sets maximum allowed fail count to specified nr (default: 10)"""
        OtelManager._max_consecutive_fails = set_to

    @staticmethod
    def get_max_fails() -> int:
        """Returns maximum allowed concurrent fails"""
        return OtelManager._max_consecutive_fails

    @staticmethod
    def get_current_fail_count() -> int:
        """Returns current API ingest fail count"""
        return OtelManager._consecutive_fail_count

    @staticmethod
    def reset_current_fail_count():
        """Resets current API ingest fail count to 0"""
        OtelManager._consecutive_fail_count = 0

    @staticmethod
    def increase_current_fail_count(last_response: requests.Response, increase_by: int = 1) -> None:
        """Increases run time API fail count by specified number (default: 1).
        Updates last known response, flips the flag if current fail exceeds max allowed
        """
        OtelManager._consecutive_fail_count += increase_by
        OtelManager._last_response = last_response
        if OtelManager.get_current_fail_count() >= OtelManager.get_max_fails():
            OtelManager._to_abort = True
            OtelManager._last_response = last_response

    @staticmethod
    def set_current_fail_count(set_to: int = 0) -> None:
        """Sets runtime API fail count to specified number (default: 0)"""
        OtelManager._consecutive_fail_count = set_to
        OtelManager._to_abort = False

    @staticmethod
    def verify_communication() -> None:
        """Checks if run should be aborted. Raises RuntimeError with last known response code, if current fails exceed max allowed."""
        if OtelManager._to_abort and OtelManager.get_current_fail_count() >= OtelManager.get_max_fails():
            from dtagent import LOG

            error_message = (
                "Too many failed attempts to send data to Dynatrace "
                f"({OtelManager.get_current_fail_count()} / {OtelManager.get_max_fails()}), aborting run. Last response:\n"
                f"                                error code: {OtelManager._last_response.status_code},\n"
                f"                                reason: {OtelManager._last_response.reason},\n"
                f"                                response: {OtelManager._last_response.text}"
            )

            LOG.error(error_message)
            raise RuntimeError(error_message)

    @staticmethod
    def get_dsoa_headers() -> dict:
        """Returns headers required for DSOA to DT communication"""
        return {"User-Agent": USER_AGENT, "X-Dynatrace-Attr": "dt.ingest.origin=snowflake-dsoa"}


class CustomLoggingSession(requests.Session):
    """Session wrapper for logs and spans to capture responses when sending payload."""

    def send(self, request, **kwargs):
        """Sends data using superclass method and calls OtelManager to handle response."""
        response: requests.Response = super().send(request, **kwargs)
        if response.status_code >= 300:
            OtelManager.increase_current_fail_count(response)
            _log_warning(response, response.request.body, source=response.url.rsplit("/", 1)[-1])
        else:
            OtelManager.set_current_fail_count(0)
        return response

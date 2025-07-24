"""Contains the base class for all otel modules"""

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
##endregion COMPILE_REMOVE

import requests
from dtagent.otel import _log_warning

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
    def increase_current_fail_count(last_response: requests.Response, increase_by: int = 1) -> None:
        """
        Increases run time API fail count by specified number (default: 1).
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
        if OtelManager._to_abort:
            from dtagent import LOG

            error_message = f"""Too many failed attempts to send data to Dynatrace, aborting run. Last response:
                                error code: {OtelManager._last_response.status_code},
                                reason: {OtelManager._last_response.reason},
                                response: {OtelManager._last_response.text}"""

            LOG.error(error_message)
            raise RuntimeError(error_message)


class CustomLoggingSession(requests.Session):
    """Session wrapper for logs and spans to capture responses when sending payload."""

    def send(self, request, **kwargs):
        """Sends data using superclass method and calls OtelManager to handle response."""
        response: requests.Response = super().send(request, **kwargs)
        if response.status_code >= 300:
            OtelManager.increase_current_fail_count(response)
            _log_warning(response, response.request.body)
        else:
            OtelManager.set_current_fail_count(0)
        return response

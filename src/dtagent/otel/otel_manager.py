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

import re
import requests
from typing import Optional
from dtagent.otel import _log_warning, USER_AGENT
from dtagent.otel.ingest_warnings import IngestWarningCollector

##region ------------------------ OTEL base class---------------------------------

_UNSAFE_CHARS_RE = re.compile(r"[\r\n\x00-\x1f]")


def _sanitize_ua_segment(value: Optional[str]) -> Optional[str]:
    """Strips control and CRLF characters from a User-Agent segment value.

    Args:
        value (Optional[str]): Raw segment value, may be None or empty.

    Returns:
        Optional[str]: Sanitized value, or None when blank after stripping.
    """
    if not value:
        return None
    return _UNSAFE_CHARS_RE.sub("", value).strip() or None


class OtelManager:
    """Class containing methods managing the failures of otel modules"""

    _max_consecutive_fails: int = 0
    _consecutive_fail_count: int = 0
    _to_abort: bool = False
    _last_response: requests.Response
    _run_environment: Optional[str] = None
    _current_plugin: Optional[str] = None

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

    def set_run_environment(self, deployment_environment: Optional[str]) -> None:
        """Stores the deployment environment for inclusion in the User-Agent header.

        Sets class-level state so the value is visible to all callers of get_dsoa_headers(),
        including per-call senders in metrics and events that build headers fresh each request.

        Args:
            deployment_environment (Optional[str]): Value of core.deployment_environment from config.
        """
        OtelManager._run_environment = _sanitize_ua_segment(deployment_environment)

    def set_current_plugin(self, plugin_name: Optional[str]) -> None:
        """Stores the currently active plugin name for inclusion in the User-Agent header.

        Sets class-level state so the value is visible to all callers of get_dsoa_headers(),
        including per-call senders in metrics and events that build headers fresh each request.

        Args:
            plugin_name (Optional[str]): Name of the plugin about to execute.
        """
        OtelManager._current_plugin = _sanitize_ua_segment(plugin_name)

    @classmethod
    def get_dsoa_headers(cls) -> dict:
        """Returns headers required for DSOA to DT communication.

        Builds a dynamic User-Agent of the form ``dsoa/{version};env={env};plugin={plugin}``,
        omitting segments that are not set. Falls back to the bare version string on any error
        so UA construction never breaks ingestion. Class-level state means per-call senders
        in metrics and events pick up changes automatically with no per-call modification.
        """
        try:
            parts = [USER_AGENT]
            if cls._run_environment:
                parts.append(f"env={cls._run_environment}")
            if cls._current_plugin:
                parts.append(f"plugin={cls._current_plugin}")
            user_agent = ";".join(parts)
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001 - never let UA construction break ingestion
            user_agent = USER_AGENT
        return {"User-Agent": user_agent, "X-Dynatrace-Attr": "dt.ingest.origin=snowflake-dsoa"}


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
            try:
                # Dynatrace's OTLP endpoint returns JSON (not protobuf) in the response body,
                # so JSON parsing is correct here. Non-JSON responses are handled by the except.
                body = response.json()
                partial = body.get("partialSuccess", {}) if isinstance(body, dict) else {}
                rejected_logs = partial.get("rejectedLogRecords", 0)
                rejected_spans = partial.get("rejectedSpans", 0)
                if rejected_logs:
                    IngestWarningCollector.add_warning(
                        "partial_success", "logs", f"OTLP partial success: {rejected_logs} log record(s) rejected", rejected_logs
                    )
                if rejected_spans:
                    IngestWarningCollector.add_warning(
                        "partial_success", "spans", f"OTLP partial success: {rejected_spans} span(s) rejected", rejected_spans
                    )
            except Exception:  # pylint: disable=broad-except
                pass
        return response

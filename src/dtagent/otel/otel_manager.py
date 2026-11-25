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
from typing import Dict, Optional

import requests
from dtagent.otel import _log_warning, USER_AGENT
from dtagent.otel.ingest_warnings import IngestWarningCollector
from dtagent.otel.export_stats import ExportStatsCollector, Attribution

##region ------------------------ OTEL base class---------------------------------

_UNSAFE_CHARS_RE = re.compile(r"[\r\n\x00-\x1f\x7f;]")
MAX_USER_AGENT_LENGTH = 64  # the self-monitoring side truncates the User-Agent beyond this many characters
MAX_REPORT_ENVIRONMENT_LENGTH = 16  # keeps the segments of a report within MAX_USER_AGENT_LENGTH
USER_AGENT_REPORT_PAYLOAD = ""  # empty on purpose: the endpoint answers 400, but the User-Agent of the request is routed all the same


def _sanitize_ua_segment(value: Optional[str]) -> Optional[str]:
    """Strips control characters, CR/LF and the ``;`` separator from a User-Agent segment value (header injection guard).

    Args:
        value (Optional[str]): Raw segment value, may be None or empty.

    Returns:
        Optional[str]: Sanitized value, or None when blank after stripping.
    """
    if not value:
        return None
    return _UNSAFE_CHARS_RE.sub("", str(value)).strip() or None


class OtelManager:
    """Class containing methods managing the failures of otel modules"""

    _max_consecutive_fails: int = 0
    _consecutive_fail_count: int = 0
    _to_abort: bool = False
    _run_environment: Optional[str] = None
    _current_plugin: Optional[str] = None
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
    def record_export_attempt(signal: str, records: int, attribution: Optional[Attribution] = None) -> None:
        """Records that a batch of records is about to be exported.  Call before exporting, so the batch is counted even if the export raises.

        Args:
            signal (str):                       Exporter signal, e.g. ``logs`` or ``spans``.
            records (int):                      Number of records in the batch.
            attribution (Optional[Attribution]): ``(plugin, run id)`` captured before the export started; pass the same value to
                                                :meth:`record_export_delivered`, as the export can finish after the next plugin started.
        """
        ExportStatsCollector.add_attempted(signal, records, attribution)

    @staticmethod
    def record_export_delivered(
        signal: str, records: int, session: Optional[requests.Session] = None, attribution: Optional[Attribution] = None
    ) -> None:
        """Records that a batch of records was exported successfully.

        Args:
            signal (str):                           Exporter signal, e.g. ``logs`` or ``spans``.
            records (int):                          Number of records in the exported batch.
            session (Optional[requests.Session]):   Session used for the export; its ``rejected_records`` (records rejected
                                                    by Dynatrace in a partially successful request) are not counted as delivered.
            attribution (Optional[Attribution]):    ``(plugin, run id)`` that was given to :meth:`record_export_attempt`.
        """
        rejected = getattr(session, "rejected_records", 0) if session is not None else 0
        ExportStatsCollector.add_delivered(signal, max(0, records - rejected), attribution)

    @staticmethod
    def set_run_environment(deployment_environment: Optional[str]) -> None:
        """Stores the deployment environment for inclusion in the User-Agent (``env=`` segment).

        Args:
            deployment_environment (Optional[str]): Value of core.deployment_environment from the configuration.
        """
        OtelManager._run_environment = _sanitize_ua_segment(deployment_environment)

    @staticmethod
    def set_current_plugin(plugin_name: Optional[str]) -> None:
        """Stores the name of the plugin that is running for inclusion in the User-Agent (``plugin=`` segment).

        Args:
            plugin_name (Optional[str]): Name of the plugin about to execute; ``None`` clears it.
        """
        OtelManager._current_plugin = _sanitize_ua_segment(plugin_name)

    @staticmethod
    def build_user_agent(segments: Optional[Dict[str, object]] = None, report: bool = False, shrink_key: Optional[str] = None) -> str:
        """Builds the User-Agent ``dsoa/{version};env={env};plugin={plugin};{segments}`` of at most ``MAX_USER_AGENT_LENGTH`` characters.

        Parts are added by importance - version, plugin, environment, then the given segments in the given order - and a part that
        does not fit is dropped (an environment name is truncated instead), so the limit is never exceeded.  Segment keys and values
        are sanitized; blank ones are skipped.

        Args:
            segments (Optional[Dict[str, object]]): Extra ``key=value`` segments, the most important first.
            report (bool):                          Build the User-Agent of a report request: it has no ``plugin`` segment (the report
                                                    type says what it is) and the environment is cut to ``MAX_REPORT_ENVIRONMENT_LENGTH``.
            shrink_key (Optional[str]):             Key of a segment whose value (e.g. a task name) is shortened, if necessary, so
                                                    that all the other segments fit; it is dropped if not even one character fits.

        Returns:
            str: the User-Agent value
        """
        plugin = f";plugin={OtelManager._current_plugin}" if OtelManager._current_plugin and not report else ""
        if len(USER_AGENT) + len(plugin) > MAX_USER_AGENT_LENGTH:
            plugin = ""

        environment = ""
        if OtelManager._run_environment:
            prefix = ";env="
            room = min(
                MAX_USER_AGENT_LENGTH - len(USER_AGENT) - len(plugin) - len(prefix),
                MAX_REPORT_ENVIRONMENT_LENGTH if report else MAX_USER_AGENT_LENGTH,
            )
            if room > 0:
                environment = prefix + OtelManager._run_environment[:room]

        user_agent = f"{USER_AGENT}{environment}{plugin}"

        cleaned = [(_sanitize_ua_segment(key), _sanitize_ua_segment(value)) for key, value in (segments or {}).items()]
        cleaned = [(key, value) for key, value in cleaned if key and value]
        if shrink_key:
            others = sum(len(key) + len(value) + 2 for key, value in cleaned if key != shrink_key)
            room = MAX_USER_AGENT_LENGTH - len(user_agent) - others - len(shrink_key) - 2
            cleaned = [(key, value[: max(room, 0)] if key == shrink_key else value) for key, value in cleaned]
            cleaned = [(key, value) for key, value in cleaned if value]

        for key, value in cleaned:
            if len(user_agent) + len(key) + len(value) + 2 <= MAX_USER_AGENT_LENGTH:
                user_agent = f"{user_agent};{key}={value}"
        return user_agent

    @staticmethod
    def get_dsoa_headers(segments: Optional[Dict[str, object]] = None, report: bool = False, shrink_key: Optional[str] = None) -> dict:
        """Returns headers required for DSOA to DT communication.

        Falls back to the bare version on any error, so building the User-Agent can never break ingestion.

        Args:
            segments (Optional[Dict[str, object]]): Extra User-Agent segments, see :meth:`build_user_agent`.
            report (bool):                          Headers of a report request, see :meth:`build_user_agent`.
            shrink_key (Optional[str]):             Segment to shorten if necessary, see :meth:`build_user_agent`.
        """
        try:
            user_agent = OtelManager.build_user_agent(segments, report, shrink_key)
        except Exception:  # pylint: disable=broad-except
            user_agent = USER_AGENT
        return {"User-Agent": user_agent, "X-Dynatrace-Attr": "dt.ingest.origin=snowflake-dsoa"}

    @staticmethod
    def send_user_agent_report(
        url: str, token: str, segments: Dict[str, object], timeout: int = 10, shrink_key: Optional[str] = None
    ) -> bool:
        """Sends a minimal request whose only purpose is to carry the given segments in its User-Agent (routed to the self-monitoring tenant).

        The request is independent of the exporters: it is not counted in the export statistics or the failure counter,
        and a failure never raises.  Only the User-Agent matters, so the status of the response does not: the (empty) body is rejected
        by the endpoint, which does not keep the User-Agent from being routed.

        Args:
            url (str):                              Metrics ingest URL.
            token (str):                            Dynatrace API token.
            segments (Dict[str, object]):           User-Agent segments to report, see :meth:`build_user_agent`.
            timeout (int):                          Request timeout in seconds.
            shrink_key (Optional[str]):             Segment to shorten if necessary, see :meth:`build_user_agent`.

        Returns:
            bool: ``True`` if the request was sent and answered (with any status), ``False`` if it could not be sent
        """
        from dtagent import LOG  # COMPILE_REMOVE

        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Api-Token {token}", "Content-Type": "text/plain"}
                | OtelManager.get_dsoa_headers(segments, report=True, shrink_key=shrink_key),
                data=USER_AGENT_REPORT_PAYLOAD,
                timeout=timeout,
            )
            LOG.debug("User-Agent report sent, response: %s", response.status_code)
            return True
        except requests.RequestException as e:
            LOG.warning("Unable to send the User-Agent report: %s", e)
            return False


class SessionUserAgentMixin:
    """Mixin for exporters holding a ``requests.Session`` in ``_session``, to refresh its User-Agent before each export."""

    def refresh_user_agent(self) -> None:
        """Updates the HTTP session headers with the current dynamic User-Agent."""
        session = getattr(self, "_session", None)
        if session is not None:
            session.headers.update(OtelManager.get_dsoa_headers())


class CustomLoggingSession(requests.Session):
    """Session wrapper for logs and spans to capture responses when sending payload."""

    def __init__(self, *args, **kwargs):
        """Initializes the session; ``rejected_records`` holds the records rejected in the last (partially successful) request."""
        super().__init__(*args, **kwargs)
        self.rejected_records: int = 0

    def send(self, request, **kwargs):
        """Sends data using superclass method and calls OtelManager to handle response."""
        self.rejected_records = 0
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
                self.rejected_records = (rejected_logs or 0) + (rejected_spans or 0)
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

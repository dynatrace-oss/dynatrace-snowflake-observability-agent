"""Mechanisms allowing for parsing and sending events."""

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

from calendar import c
import json
import sys
import time
import uuid
from abc import ABC, abstractmethod
from types import NoneType
from typing import Any, Dict, List, Optional, Tuple, Union, Generator

import requests

from dtagent.context import CONTEXT_NAME
from dtagent.otel import _log_warning
from dtagent.otel.otel_manager import OtelManager
from dtagent.util import StringEnum, get_timestamp_in_ms
from dtagent.version import VERSION


##endregion COMPILE_REMOVE

##region ------------------------ Abstract EVENTS ---------------------------------

EventType = StringEnum(
    "EventType",
    [
        "AVAILABILITY_EVENT",
        "CUSTOM_ALERT",
        "CUSTOM_ANNOTATION",
        "CUSTOM_CONFIGURATION",
        "CUSTOM_DEPLOYMENT",
        "CUSTOM_INFO",
        "ERROR_EVENT",
        "MARKED_FOR_TERMINATION",
        "PERFORMANCE_EVENT",
        "RESOURCE_CONTENTION_EVENT",
    ],
)


class AbstractEvents(ABC):
    """This is an abstract class for OpenPipelineEvents and BizEvents implementations"""

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    ENDPOINT_PATH = None  # to be defined in child classes

    def __init__(self, configuration: Configuration, event_type: str = "events", default_params: Optional[Dict[str, Any]] = None):
        """Initializing payload cache and fields from configuration.

        Args:
            configuration (Configuration): Current configuration of the agent
            event_type (str, optional): Name of the events. Defaults to "events".
            defaults (Optional[Dict[str, Any]], optional): Dictionary with overrides for default values for API parameters. Defaults to None.
        """
        _default_params = default_params or {}

        self.PAYLOAD_CACHE: List[Dict[str, Any]] = []
        self._configuration = configuration
        self._resource_attributes = self._configuration.get("resource.attributes")
        self._max_payload_bytes = self._configuration.get(
            otel_module=event_type, key="max_payload_bytes", default_value=_default_params.get("max_payload_bytes", 10000000)
        )
        self._max_event_count = self._configuration.get(
            otel_module=event_type, key="max_event_count", default_value=_default_params.get("max_event_count", 400)
        )
        self._max_retries = self._configuration.get(
            otel_module=event_type, key="max_retries", default_value=_default_params.get("max_retries", 5)
        )
        self._retry_delay_ms = self._configuration.get(
            otel_module=event_type, key="retry_delay_ms", default_value=_default_params.get("retry_delay_ms", 10000)
        )
        self._ingest_retry_statuses = self._configuration.get(
            otel_module=event_type, key="retry_on_status", default_value=_default_params.get("retry_on_status", [429, 502, 503])
        )
        self._api_event_type = event_type
        self._api_url = self._configuration.get(f"{event_type}.http")
        self._api_content_type = _default_params.get("api_content_type", "application/json")
        self._api_post_timeout = self._configuration.get(
            otel_module=event_type, key="api_post_timeout", default_value=_default_params.get("api_post_timeout", 30)
        )

    def _send_events(self, payload: Optional[List[Dict[str, Any]]] = None) -> int:
        """Sends given payload of events to Dynatrace via the chosen API.
        The code attempts to accumulate to the maximal size of payload allowed - and
        will flush before we would exceed with new payload increment.
        IMPORTANT: call _flush_events() to flush at the end of processing

        Args:
            payload (List, optional): List of one or multiple dictionaries to be send as events. Defaults to None.

        Returns:
            int: Number of events that were sent without issues; -1 if there were any issues
        """
        from dtagent import LL_TRACE, LOG  # COMPILE_REMOVE

        events_sent = 0

        def __send(_payload_list: List[Dict[str, Any]], _retries: int = 0) -> int:
            """
            Sends given payload to Dynatrace
            """

            response = None
            events_count = -1  # something was wrong with events sent - resetting to -1

            headers = {
                "Authorization": f'Api-Token {self._configuration.get("dt.token")}',
                "Accept": "application/json",
                "Content-Type": self._api_content_type,
            } | OtelManager.get_dsoa_headers()

            payload = json.dumps(_payload_list)
            payload_cnt = len(_payload_list)
            try:
                LOG.log(
                    LL_TRACE,
                    "Sending %d bytes payload with %d %s records to %s",
                    sys.getsizeof(payload),
                    payload_cnt,
                    self._api_event_type,
                    self._api_url,
                )

                LOG.log(
                    LL_TRACE,
                    "Sending %s as %s records to %s",
                    payload,
                    self._api_event_type,
                    self._api_url,
                )

                response = requests.post(
                    self._api_url,
                    headers=headers,
                    data=payload,
                    timeout=self._api_post_timeout,
                )

                LOG.log(
                    LL_TRACE,
                    "Sent payload with %d %s records; response: %s",
                    payload_cnt,
                    self._api_event_type,
                    response.status_code,
                )

                if response.status_code == 202:
                    events_count = payload_cnt
                    OtelManager.set_current_fail_count(0)
                else:
                    _log_warning(response, _payload_list, self._api_event_type)

            except requests.exceptions.RequestException as e:
                if isinstance(e, requests.exceptions.Timeout):
                    LOG.error(
                        "The request to send %d bytes payload with %d %s records timed out after 5 minutes. (retry = %d)",
                        sys.getsizeof(_payload_list),
                        len(_payload_list),
                        self._api_event_type,
                        _retries,
                    )
                else:
                    LOG.error(
                        "An error occurred when sending %d bytes payload with %d %s records (retry = %d): %s",
                        sys.getsizeof(_payload_list),
                        len(_payload_list),
                        self._api_event_type,
                        _retries,
                        e,
                    )
            finally:
                if response is not None and response.status_code in self._ingest_retry_statuses:
                    if _retries < self._max_retries:
                        time.sleep(self._retry_delay_ms)
                        events_count = __send(_payload_list, _retries + 1)
                    else:
                        LOG.warning(
                            "Failed to send all %s data with %d (max=%d) attempts; last status code = %s",
                            self._api_event_type,
                            _retries,
                            self._max_retries,
                            response.status_code,
                        )
                        OtelManager.increase_current_fail_count(response)

                elif response is not None and response.status_code >= 300:
                    OtelManager.increase_current_fail_count(response)

                OtelManager.verify_communication()

            return events_count

        def __split_payload(payload: List[Dict[str, Any]]) -> Generator[List[Dict[str, Any]], None, None]:
            """Enables to iterate over "ingestible" chunks of events payload"""
            current_chunk = []
            current_size = 0
            for event in payload:
                event_size = sys.getsizeof(json.dumps(event))
                if event_size > self._max_payload_bytes:
                    LOG.warning(
                        "%s records size %d exceeds max payload size %d, skipping event",
                        self._api_event_type,
                        event_size,
                        self._max_payload_bytes,
                    )
                    continue
                if current_size + event_size > self._max_payload_bytes or len(current_chunk) >= self._max_event_count:
                    yield current_chunk
                    current_chunk = []
                    current_size = 0

                current_chunk.append(event)
                current_size += event_size

            if current_chunk:
                yield current_chunk

        events_sent = 0

        if payload is not None:
            self.PAYLOAD_CACHE += payload

        if payload is None or len(self.PAYLOAD_CACHE) >= self._max_event_count:
            for events_chunk in __split_payload(self.PAYLOAD_CACHE):
                events_sent += __send(events_chunk)
            self.PAYLOAD_CACHE = []

        return events_sent

    def flush_events(self) -> int:
        """
        Flush business events cache
        """
        return self._send_events()

    @abstractmethod
    def send_events(self, events: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> bool:
        """Sends given list of events to Dynatrace via the chosen API.

        This is an abstract method that must be implemented in subclasses.

        Args:
            events (List): List of events data, each in form of dict
            context (Dict, optional): Additional information that should be appended to event data. Defaults to None.

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        return self._send_events(events | (context or {}))

    def report_via_api(
        self,
        query_data: Union[List[Dict[str, Any]], Generator[Dict, None, None]],
        context: Optional[Dict] = None,
        event_type: Optional[Union[str, EventType]] = None,
        is_data_structured: bool = True,
    ) -> int:
        """
        Generates and sends payload with selected events to Dynatrace via the chosen API.

        Args:
            query_data (Union[List[Dict], Generator[Dict, None, None]]): List or generator of dictionaries with data to be sent as events
            context (Optional[Dict], optional): Additional context that should be added to the event properties. Defaults to None.
            event_type (Optional[Union[str, EventType]], optional): Event type to report under. Defaults to None.

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import _unpack_payload  # COMPILE_REMOVE

        _event_type = {"event.type": str(event_type)} if event_type is not None else {}
        _events = [(_unpack_payload(query_datum) if is_data_structured else query_datum) | _event_type for query_datum in query_data]

        return self.send_events(_events, context)


##endregion

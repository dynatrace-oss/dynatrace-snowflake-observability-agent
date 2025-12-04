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

from dtagent.context import RUN_CONTEXT_KEY
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

    ENDPOINT_PATH = None  # to be defined in child classes

    def __init__(self, configuration: Configuration, event_type: str = "events", default_params: Optional[Dict[str, Any]] = None):
        """Initializing payload cache and fields from configuration.

        Args:
            configuration (Configuration):                          Current configuration of the agent
            event_type (str, optional):                             Name of the events. Defaults to "events".
            default_params (Optional[Dict[str, Any]], optional):    Dictionary with overrides for default values for API parameters.
                                                                    Defaults to None.
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

    def _send(self, _payload_list: List[Dict[str, Any]], _retries: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
        """Sends given payload to Dynatrace

        Args:
            _payload_list (List[Dict[str, Any]]): List of events to be sent
            _retries (int, optional): Current retry count. Defaults to 0.
        """
        from dtagent import LL_TRACE, LOG  # COMPILE_REMOVE

        response = None
        events_count = -1  # something was wrong with events sent - resetting to -1
        _payload_to_repeat = []  # we will keep events that failed to be delivered

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
                    time.sleep(self._retry_delay_ms / 1000)
                    repeated_events_send, _payload_to_repeat = self._send(_payload_list, _retries + 1)
                    events_count += repeated_events_send
                else:
                    LOG.warning(
                        "Failed to send all %s data with %d (max=%d) attempts; last status code = %s",
                        self._api_event_type,
                        _retries,
                        self._max_retries,
                        response.status_code,
                    )
                    _payload_to_repeat = _payload_list
                    OtelManager.increase_current_fail_count(response)

            elif response is not None and response.status_code >= 300:
                OtelManager.increase_current_fail_count(response)

            OtelManager.verify_communication()

        return events_count, _payload_to_repeat

    def _split_payload(self, payload: List[Dict[str, Any]]) -> Generator[List[Dict[str, Any]], None, None]:
        """Enables to iterate over "ingestible" chunks of events payload
        Args:
            payload (List[Dict[str, Any]]): List of events to be sent
        Yields:
            Generator[List[Dict[str, Any]], None, None]: generator of lists of events, each within allowed limits
        """
        from dtagent import LL_TRACE, LOG  # COMPILE_REMOVE

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

        events_count = 0

        if payload is not None:
            self.PAYLOAD_CACHE += payload

        if payload is None or len(self.PAYLOAD_CACHE) >= self._max_event_count:
            collected_events_failed_to_send = []
            for events_chunk in self._split_payload(self.PAYLOAD_CACHE):
                events_sent, events_failed_to_send = self._send(events_chunk)
                events_count += events_sent
                collected_events_failed_to_send += events_failed_to_send
            self.PAYLOAD_CACHE = collected_events_failed_to_send

        return events_count

    def flush_events(self) -> int:
        """Flush business events cache"""
        return self._send_events()

    @abstractmethod
    def _pack_event_data(
        self, event_type: Union[str, EventType], event_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Packs given event data into payload accepted by Dynatrace Events API

        Args:
            event_type (str): Event type, e.g. EventType.CUSTOM_ALERT
            event_data (Dict[str, Any]): Event data in form of dict
            context (Optional[Dict[str, Any]]): Additional context to be added to event properties
            **kwargs: Additional parameters, like title, start_time_key, end_time_key, additional_payload, timeout, or formatted_time
        Returns:
            Dict[str, Any]: Event payload in form accepted by Dynatrace BizEvents endpoint
        """
        raise NotImplementedError("This is an abstract method and should be implemented in child classes")

    @abstractmethod
    def send_events(
        self,
        events_data: List[Dict[str, Any]],
        event_type: Optional[Union[str, EventType]] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> int:
        """Sends given list of events to Dynatrace via the chosen API.

        This is an abstract method that must be implemented in subclasses.

        Args:
            events_data (List):                                     List of events data, each in form of dict
            event_type (Optional[Union[str, EventType]], optional): Event type to report under. Defaults to None.
            context (Dict, optional):                               Additional information that should be appended to event data based on
                                                                    agent execution context. Defaults to None.
            **kwargs:                                Additional keyword arguments to be processed by child classes:
                is_data_structured (bool, optional):    Indicates whether the data in events_data is structured into a
                                                        DSOA standardized dictionary. Defaults to True.
                additional_payload (Dict, optional):    Additional lines of payload,
                title (str, optional):                  Event title,
                start_time_key (str, optional):         Key in event_data dict to be used as event start time,
                end_time_key (str, optional):           Key in event_data dict to be used as event end time,
                timeout (int, optional):                Timeout for sending events,
                formatted_time (bool, optional):        Indicates whether the time values in event_data are already formatted

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        raise NotImplementedError("This is an abstract method and should be implemented in child classes")

    def report_via_api(
        self,
        query_data: Union[List[Dict[str, Any]], Generator[Dict, None, None], Dict[str, Any]],
        event_type: Optional[Union[str, EventType]],
        *,
        is_data_structured: bool = True,
        context: Optional[Dict] = None,
        **kwargs,
    ) -> int:
        """Generates and sends payload with selected events to Dynatrace via the chosen API.

        Args:
            query_data (Union[List[Dict], Generator[Dict, None, None]]): List or generator of dictionaries with data to be sent as events
            event_type (Optional[Union[str, EventType]], optional):      Event type to report under. Defaults to None.
            is_data_structured (bool, optional):                         Indicates whether the data in query_data is structured into a
                                                                         DSOA standardized dictionary. Defaults to True.
            context (Optional[Dict], optional):                          Additional context that should be added to the event properties,
                                                                         formatted as dict which is merged with unpacked query_data contents
                                                                         based on agent execution context. Defaults to None.

            **kwargs: Additional keyword arguments to be passed to send_events() and processed in child classes:
                additional_payload (Dict, optional):        Additional lines of payload,
                title (str, optional):                      Event title,
                start_time_key (str, optional):             Key in event_data dict to be used as event start time,
                end_time_key (str, optional):               Key in event_data dict to be used as event end time,
                timeout (int, optional):                    Timeout for sending events,
                formatted_time (bool, optional):            Indicates whether the time values in event_data are already formatted

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import _unpack_payload  # COMPILE_REMOVE

        _event_data = [query_data] if isinstance(query_data, dict) else query_data
        # unpacking only if data is structured; otherwise using as-is
        if is_data_structured:
            _event_data = [_unpack_payload(query_datum) for query_datum in _event_data]

        return self.send_events(_event_data, event_type, context, **kwargs)


##endregion

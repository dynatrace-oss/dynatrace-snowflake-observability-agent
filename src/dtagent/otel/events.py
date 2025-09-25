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

import json
import time
from types import NoneType
from typing import Dict, List, Tuple, Any, Optional
import requests
from dtagent.otel.otel_manager import OtelManager
from dtagent.util import StringEnum, get_timestamp_in_ms
from dtagent.otel import _log_warning

##endregion COMPILE_REMOVE

##region ------------------------ CloudEvents EVENTS ---------------------------------

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


class Events:
    """Allows for parsing and sending Events payloads"""

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/events/ingest"

    def __init__(self, configuration: Configuration):
        """Initializes configuration's resources for events"""

        self.PAYLOAD_CACHE: List[Dict[str, Any]] = []
        self._configuration = configuration
        self._resource_attributes = self._configuration.get("resource.attributes")
        self._valid_event_types = {}
        self._retry_delay = self._configuration.get(otel_module="events", key="retry_delay", default_value=10000)
        self._max_retries = self._configuration.get(otel_module="events", key="max_retries", default_value=5)

    def _send_events(self, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Sends given payload of a single event to Dynatrace.
        Currently Dynatrace does not support sending multiple events at the same time,
        as a bulk, like in BizEvents.

        IMPORTANT: although we can only send one event at time,
        if there are issues with sending/resending the event they are put in cache
        so they could be send next time we try.
        Hence it is a good practice to call flash_events() as the last attempt to resend the failed events.

        Args:
            payload (Dict, optional): complete body of the event API call payload. Defaults to None.

        Returns:
            bool: True if there are no un-send events left.
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE

        def __send(_payload_list: List[Dict[str, Any]], _retries: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
            """Sends given payload to Dynatrace

            Args:
                _payload_list (list): list of events to send
                _retries (int, optional): Number of retries - will stop retrying after 3 attempts. Defaults to 0.

            Returns:
                int: number of events that we managed to send
                List[Dict[str, Any]]: list of events that we failed to send and we need to resend
            """

            headers = {
                "Authorization": f'Api-Token {self._configuration.get("dt.token")}',
                "Content-Type": "application/json",
            } | OtelManager.get_dsoa_headers()

            _payload_to_repeat = []  # we will keep events that failed to be delivered
            events_send = 0

            for _payload in _payload_list:
                try:
                    payload = json.dumps(_payload)
                    response = requests.post(
                        self._configuration.get("events.http"),
                        headers=headers,
                        data=payload,
                        timeout=30,
                    )

                    LOG.log(LL_TRACE, "Sent %d events payload; response: %d", len(_payload), response.status_code)

                    if response.status_code == 201:
                        events_send += 1
                        OtelManager.set_current_fail_count(0)
                    else:
                        _log_warning(response, _payload, "event")

                except requests.exceptions.RequestException as e:
                    if isinstance(e, requests.exceptions.Timeout):
                        LOG.error(
                            "The request to send %d bytes with events timed out after 5 minutes. (retry = %d)",
                            len(_payload),
                            _retries,
                        )
                    else:
                        LOG.error(
                            "An error occurred when sending %d bytes with events (retry = %d): %s",
                            len(_payload),
                            _retries,
                            e,
                        )

                    _payload_to_repeat.append(_payload)

            if _payload_to_repeat:
                if _retries < self._max_retries:
                    time.sleep(self._retry_delay)
                    repeated_events_send, _payload_to_repeat = __send(_payload_to_repeat, _retries + 1)
                    events_send += repeated_events_send
                else:
                    __message = f"Failed to send all data within {self._max_retries} attempts"
                    LOG.warning(__message)
                    OtelManager.increase_current_fail_count(response)
                    OtelManager.verify_communication()

            return events_send, _payload_to_repeat

        # There is no way to send events by batches
        # that is why we just append to cache of events we wanted to send and attempt to send right away

        events_send = 0

        if payload is not None:
            self.PAYLOAD_CACHE.append(payload)
        elif payload is None and len(self.PAYLOAD_CACHE) == 0:
            LOG.info("Events: no more to send.")
            return True

        if len(self.PAYLOAD_CACHE) > 0:
            to_send = len(self.PAYLOAD_CACHE)
            events_send, self.PAYLOAD_CACHE = __send(self.PAYLOAD_CACHE)
            return to_send == events_send

        return False

    def flush_events(self) -> bool:
        """
        Flush events cache
        """
        return self._send_events()

    def send_event(
        self,
        event_type: EventType = EventType.CUSTOM_ALERT,
        title: str = "Dynatrace Snowflake Observability Agent event",
        *,
        properties: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """Schedules delivery of Dynatrace Event with given information

        Args:
            event_type (EventType, optional): Event type to report under. Defaults to EventType.CUSTOM_ALERT.
            title (str, optional): Title of the event. Defaults to "Dynatrace Snowflake Observability Agent event".
            properties (Dict, optional): Content of the event. Defaults to None.
            context (Dict, optional): Additional context that should be added to the event properties
            start_time (int, optional): start timestamp. Defaults to None.
            end_time (int, optional): end timestamp. Defaults to None.
            timeout (int, optional): timeout in minutes (max 360). Defaults to None.

        Raises:
            ValueError: if given event_type is not registered in EventType

        Returns:
            bool: True if we managed to send those events successfully
        """
        from dtagent.util import _cleanup_dict, _pack_values_to_json_strings  # COMPILE_REMOVE

        def __limit_to_api(properties: Dict[str, str]) -> Dict:
            """Limit values to no longer than 4096 characters"""
            for key in properties:
                if isinstance(properties[key], str) and len(properties[key]) > 4096:
                    properties[key] = properties[key][:4096]

            return properties

        if not isinstance(event_type, EventType):
            raise ValueError(f"{event_type} is not a valid EventType value")

        payload = {
            "eventType": str(event_type),
            "title": title,
            "properties": __limit_to_api(
                _pack_values_to_json_strings(
                    _cleanup_dict(properties or {}) | self._resource_attributes | (context or {}), max_list_level=1
                )
            ),
        }

        if timeout is not None and timeout <= 360:  # max available timeout 6h
            payload["timeout"] = timeout

        if start_time:
            payload["startTime"] = start_time

        if end_time:
            payload["endTime"] = end_time

        return self._send_events(payload)

    def report_via_api(
        self,
        query_data: Dict[str, Any],
        event_type=EventType.CUSTOM_ALERT,
        *,
        title: str = "Dynatrace Snowflake Observability Agent event",
        start_time_key: str = "START_TIME",
        end_time_key: str = "END_TIME",
        context: Optional[Dict[str, Any]] = None,
        additional_payload: Optional[dict] = None,
    ) -> bool:
        """Sends given payload of data resulted from Dynatrace Snowflake Observability Agent standard view as Events v2 API

        Args:
            query_data (Dict): results of querying Dynatrace Snowflake Observability Agent standard view with objects like DIMENSIONS
            event_type (EventType, optional): Type of event to report under. Defaults to EventType.CUSTOM_ALERT.
            title (str, optional): Title of the event to report, **unless** `_MESSAGE` is provided in `query_data`.
                                   Defaults to "Dynatrace Snowflake Observability Agent event".
            start_time_key (str, optional): name of the query_data object key where start_time timestamp is stored.
                                            Defaults to "START_TIME".
            end_time_key (str, optional): name of the query_data object key where end_time timestamp is stored. Defaults to "END_TIME".
            context (Dict, optional): Additional context that should be added to the event properties
            additional_payload (Dict, optional): Additional lines of payload,
                                                 formatted as dict which is merged with unpacked query_data contents.
        Returns:
            bool: If scheduling of the event delivery was successful
        """
        from dtagent.util import _unpack_payload  # COMPILE_REMOVE

        message = str(query_data.get("_MESSAGE", ""))
        properties = _unpack_payload(query_data) if additional_payload is None else additional_payload | _unpack_payload(query_data)

        start_ts = get_timestamp_in_ms(query_data, start_time_key, 1e6, None)
        end_ts = get_timestamp_in_ms(query_data, end_time_key, 1e6, None)

        # we have map non-simple types to string, as events are not capable of mapping lists
        for key, value in properties.items():
            if not isinstance(value, (int, float, str, bool, NoneType)):
                properties[key] = str(value)

        return self.send_event(
            event_type=event_type,
            title=message if len(message) > 0 else title,
            properties=properties if properties is not None else query_data,
            start_time=start_ts,
            end_time=end_ts,
            context=context,
        )

"""Mechanisms for processing and sending bizevents."""

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

import sys
import json
import time
import uuid
from typing import Generator, Dict, List, Optional, Union, Any
import requests
from dtagent.context import CONTEXT_NAME
from dtagent.otel.events import EventType
from dtagent.otel.otel_manager import OtelManager
from dtagent.version import VERSION
from dtagent.otel import _log_warning


##endregion COMPILE_REMOVE

##region ------------------------ CloudEvents BIZEVENTS ---------------------------------


class BizEvents:
    """Class parsing and sending bizevents."""

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    def __init__(self, configuration: Configuration):
        """Initializing payload cache and fields from configuration."""
        self.PAYLOAD_CACHE: List[Dict[str, Any]] = []
        self._configuration = configuration
        self._resource_attributes = self._configuration.get("resource.attributes")
        self._max_payload_bytes = self._configuration.get(otel_module="biz_events", key="max_payload_bytes", default_value=5120000)
        self._max_event_count = self._configuration.get(otel_module="biz_events", key="max_event_count", default_value=400)
        self._max_retries = self._configuration.get(otel_module="biz_events", key="max_retries", default_value=5)
        self._retry_delay_ms = self._configuration.get(otel_module="biz_events", key="retry_delay_ms", default_value=10000)
        self._ingest_retry_statuses = self._configuration.get(
            otel_module="biz_events", key="retry_on_status", default_value=[429, 502, 503]
        )
        self._bizevents_url = self._configuration.get("bizevents.http")

    def _send_events(self, payload: Optional[List[Dict[str, Any]]] = None) -> int:
        """Sends given payload of business events (as CloudEvent batch) to Dynatrace.
        The code attempts to accumulate to the maximal size of payload allowed - and
        will flush before we would exceed with new payload increment.
        IMPORTANT: call _flush_events() to flush at the end of processing

        Args:
            payload (List, optional): List of one or multiple dictionaries to be send as bizevents. Defaults to None.

        Returns:
            int: Number of bizevents that were sent without issues; -1 if there were any issues
        """
        from dtagent import LOG, LL_TRACE  # COMPILE_REMOVE

        events_sent = 0

        def __send(_payload_list: List[Dict[str, Any]], _retries: int = 0) -> int:
            """
            Sends given payload to Dynatrace
            """

            response = None
            bizevents_count = -1  # something was wrong with bizevents sent - resetting to -1

            headers = {
                "Authorization": f'Api-Token {self._configuration.get("dt.token")}',
                "Accept": "application/json",
                "Content-Type": "application/cloudevent-batch+json",
            } | OtelManager.get_dsoa_headers()

            payload = json.dumps(_payload_list)
            payload_cnt = len(_payload_list)
            try:
                LOG.log(
                    LL_TRACE,
                    "Sending %d bytes payload with %d business events to %s",
                    sys.getsizeof(payload),
                    payload_cnt,
                    self._bizevents_url,
                )

                LOG.log(
                    LL_TRACE,
                    "Sending %s as business events to %s",
                    payload,
                    self._bizevents_url,
                )

                response = requests.post(
                    self._bizevents_url,
                    headers=headers,
                    data=payload,
                    timeout=30,
                )

                LOG.log(
                    LL_TRACE,
                    "Sent payload with %d business events; response: %s",
                    payload_cnt,
                    response.status_code,
                )

                if response.status_code == 202:
                    bizevents_count = payload_cnt
                    OtelManager.set_current_fail_count(0)
                else:
                    _log_warning(response, _payload_list, "business event")

            except requests.exceptions.RequestException as e:
                if isinstance(e, requests.exceptions.Timeout):
                    LOG.error(
                        "The request to send %d bytes payload with %d business events timed out after 5 minutes. (retry = %d)",
                        sys.getsizeof(_payload_list),
                        len(_payload_list),
                        _retries,
                    )
                else:
                    LOG.error(
                        "An error occurred when sending %d bytes payload with %d business events (retry = %d): %s",
                        sys.getsizeof(_payload_list),
                        len(_payload_list),
                        _retries,
                        e,
                    )
            finally:
                if response is not None and response.status_code in self._ingest_retry_statuses:
                    if _retries < self._max_retries:
                        time.sleep(self._retry_delay_ms)
                        bizevents_count = __send(_payload_list, _retries + 1)
                    else:
                        LOG.warning(
                            "Failed to send all business events data with %d (max=%d) attempts; last status code = %s",
                            _retries,
                            self._max_retries,
                            response.status_code,
                        )
                        OtelManager.increase_current_fail_count(response)

                elif response is not None and response.status_code >= 300:
                    OtelManager.increase_current_fail_count(response)

                OtelManager.verify_communication()

            return bizevents_count

        def __split_payload(payload: List[Dict[str, Any]]) -> Generator[List[Dict[str, Any]], None, None]:
            """Enables to iterate over "ingestible" chunks of bizevents payload"""
            current_chunk = []
            current_size = 0
            for event in payload:
                event_size = sys.getsizeof(json.dumps(event))
                if event_size > self._max_payload_bytes:
                    LOG.warning(
                        "Business event size %d exceeds max payload size %d, skipping event",
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

    def send_events(self, events: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> bool:
        """Sends give list of events (in dict form) as CloudEvents to Dynatrace BizEvents endpoint

        Args:
            events (List): List of events data, each in form of dict
            context (Dict, optional): Additional information that should be appended to event data. Defaults to None.

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import get_now_timestamp_formatted, _cleanup_data  # COMPILE_REMOVE

        _formatted_time = get_now_timestamp_formatted()
        _context = context or {}
        _cloud_event_core = {
            "specversion": "1.0",
            "id": str(uuid.uuid4().hex),
            "source": self._resource_attributes.get("host.name", "snowflakecomputing.com"),
            "time": _formatted_time,
        }
        _event_extra = (
            {
                "app.version": self._resource_attributes.get("telemetry.exporter.version", "0.0.0"),
                "app.short_version": VERSION,
                "app.bundle": _context.get(CONTEXT_NAME, "bizevents"),
                "app.id": "dynatrace.snowagent",
            }
            | self._resource_attributes
            | _context
        )

        cloud_events = [
            _cloud_event_core
            | _cleanup_data(
                {
                    "type": event.get("event.type", "dsoa.bizevent"),
                }
            )
            | _cleanup_data({"data": event | _event_extra})
            for event in events
        ]

        return self._send_events(cloud_events)

    def report_via_api(
        self,
        query_data: Union[List[Dict[str, Any]], Generator[Dict, None, None]],
        context: Optional[Dict] = None,
        event_type: Optional[Union[str, EventType]] = None,
        is_data_structured: bool = True,
    ) -> int:
        """
        Generates and sends payload with Business Events v2 API

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import _unpack_payload  # COMPILE_REMOVE

        _event_type = {"event.type": str(event_type)} if event_type is not None else {}
        _events = [(_unpack_payload(query_datum) if is_data_structured else query_datum) | _event_type for query_datum in query_data]

        return self.send_events(_events, context)

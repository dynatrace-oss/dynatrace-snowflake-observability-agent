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
from dtagent.otel.events import EventType, AbstractEvents
from dtagent.otel.events.generic import GenericEvents
from dtagent.util import StringEnum, get_timestamp_in_ms
from dtagent.version import VERSION

##endregion COMPILE_REMOVE

##region ------------------------ Davis EVENTS ---------------------------------


class DavisEvents(GenericEvents):
    """Allows for parsing and sending (Davis) Events payloads via Events v2 API
    https://docs.dynatrace.com/docs/discover-dynatrace/platform/openpipeline/reference/api-ingestion-reference#davis-events

    Note: Events API does not support sending multiple events at the same time, as a bulk, like in BizEvents or OpenPipelineEvents.

    Deprecated: use dtagent.otel.events.generic.GenericEvents instead.
    """

    from dtagent.config import Configuration  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/events/ingest"

    def __init__(self, configuration: Configuration):
        """Initializes configuration's resources for events"""
        GenericEvents.__init__(self, configuration, event_type="davis_events")

    def _send(self, _payload_list: List[Dict[str, Any]], _retries: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
        """Sends given payload to Dynatrace Events v2 API.
        Overrides GenericEvents.__send() as Events v2 API does not support sending multiple events at the same time,
        as a bulk, like in BizEvents or OpenPipelineEvents.

        Args:
            _payload_list (list): list of events to send
            _retries (int, optional): Number of retries - will stop retrying after 3 attempts. Defaults to 0.

        Returns:
            int: number of events that we managed to send
            List[Dict[str, Any]]: list of events that we failed to send and we need to resend
        """
        from dtagent import LL_TRACE, LOG  # COMPILE_REMOVE

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
                    self._api_url,
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
                time.sleep(self._retry_delay_ms / 1000)
                repeated_events_send, _payload_to_repeat = self._send(_payload_to_repeat, _retries + 1)
                events_send += repeated_events_send
            else:
                __message = f"Failed to send all data within {self._max_retries} attempts"
                LOG.warning(__message)
                OtelManager.increase_current_fail_count(response)
                OtelManager.verify_communication()

        return events_send, _payload_to_repeat

    def _add_data_to_payload(self, payload: Dict[str, Any], event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adds given properties to event payload under 'properties' key
        Args:
            payload (Dict[str, Any]): Event payload in form of dict
            event_data (Dict[str, Any]): Properties to be added to event payload
        Returns:
            Dict[str, Any]: Event payload with added event data
        """

        def __limit_to_api(properties: Dict[str, str]) -> Dict:
            """Limit values to no longer than 4096 characters as per API documentation."""
            for key in properties:
                if isinstance(properties[key], str) and len(properties[key]) > 4096:
                    properties[key] = properties[key][:4096]

            return properties

        payload["properties"] = __limit_to_api(event_data or {})
        return payload

    def _split_payload(self, payload: List[Dict[str, Any]]) -> Generator[List[Dict[str, Any]], None, None]:
        """Overrides _split_payload from GenericEvents as Events v2 API does not support sending multiple events at the same time,
        and hence we do not need to split payloads.

        Args:
            payload (List[Dict[str, Any]]): List of events to be sent
        Yields:
            Generator[List[Dict[str, Any]], None, None]: generator of lists of events, each within allowed limits
        """
        yield payload


##endregion

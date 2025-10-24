"""Mechanisms allowing for parsing and sending generic OpenPipeline events."""

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

from dtagent.context import CONTEXT_NAME
from dtagent.otel import _log_warning
from dtagent.otel.otel_manager import OtelManager
from dtagent.otel.events import EventType, AbstractEvents
from dtagent.util import StringEnum, get_timestamp_in_ms
from dtagent.version import VERSION
import datetime


##endregion COMPILE_REMOVE


##region ------------------------ CloudEvents EVENTS ---------------------------------


class GenericEvents(AbstractEvents):
    """
    Enables for parsing and sending Events via OpenPipeline Events API
    https://docs.dynatrace.com/docs/discover-dynatrace/platform/openpipeline/reference/api-ingestion-reference

    Note: OpenPipeline Events API does support sending multiple events at the same time, similar to BizEvents.
    """

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    ENDPOINT_PATH = "/platform/ingest/v1/events"

    def __init__(self, configuration: Configuration, event_type: str = "events"):
        """Initializes configuration's resources for events"""
        AbstractEvents.__init__(self, configuration, event_type=event_type)

    def _add_data_to_payload(self, payload: Dict[str, Any], event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adds given event_data to event payload.
        This is a separate method to allow overriding in child classes,
        especially in DavisEvents where event data needs to be set under 'properties' key.
        Args:
            payload (Dict[str, Any]): Event payload in form of dict
            event_data (Dict[str, Any]): Properties to be added to event payload
        Returns:
            Dict[str, Any]: Event payload with added event data
        """
        payload |= event_data
        return payload

    def _pack_event_data(
        self, event_type: Union[str, EventType], event_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Packs given event data into payload accepted by Dynatrace Events API
        Args:
            event_type (str): Event type, e.g. EventType.CUSTOM_ALERT
            event_data (Dict[str, Any]): Event data in form of dict
            context (Optional[Dict[str, Any]]): Additional context to be added to event properties
            **kwargs: Additional parameters, like title, start_time_key, end_time_key, additional_payload, timeout
        Returns:
            Dict[str, Any]: Event payload in form accepted by Dynatrace Events API
        """
        from dtagent.util import _cleanup_dict, _pack_values_to_json_strings, _unpack_payload  # COMPILE_REMOVE

        title = (
            str(event_data.get("_MESSAGE", ""))
            or str(event_data.get("_message", ""))
            or kwargs.get("title", "Dynatrace Snowflake Observability Agent event")
        )
        event_data_extended = kwargs.get("additional_payload", {}) | {
            k: v for k, v in event_data.items() if k not in ("_MESSAGE", "_message")
        }

        start_ts = get_timestamp_in_ms(event_data, kwargs.get("start_time_key", "START_TIME"), 1e6, None)
        end_ts = get_timestamp_in_ms(event_data, kwargs.get("end_time_key", "END_TIME"), 1e6, None)

        # we have map non-simple types to string, as events are not capable of mapping lists
        # for key, value in event_data_extended.items():
        #     if not isinstance(value, (int, float, str, bool, NoneType)):
        #         event_data_extended[key] = str(value)

        if isinstance(event_type, EventType) and event_type not in EventType:
            raise ValueError(f"{event_type} is not a valid EventType value")

        event_payload = self._add_data_to_payload(
            {
                "eventType": str(event_data.get("event.type", event_type)),
                "title": title,
            },
            _pack_values_to_json_strings(
                _cleanup_dict(event_data_extended or {}) | (self._resource_attributes or {}) | (context or {}), max_list_level=1
            ),
        )

        if kwargs.get("timeout", None) is not None and kwargs.get("timeout", None) <= 360:  # max available timeout 6h
            event_payload["timeout"] = kwargs.get("timeout", None)

        if start_ts:
            event_payload["startTime"] = start_ts

        if end_ts:
            event_payload["endTime"] = end_ts

        return event_payload

    def send_events(
        self,
        events_data: List[Dict[str, Any]],
        event_type: Optional[Union[str, EventType]] = EventType.CUSTOM_ALERT,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> bool:

        generic_events = [
            self._pack_event_data(
                event_type=event_type,
                event_data=event_data,
                context=context,
                **kwargs,
            )
            for event_data in events_data
        ]

        return self._send_events(generic_events)


##endregion

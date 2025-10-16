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

import json
import sys
import time
import uuid
from typing import Any, Dict, Generator, List, Optional, Union

import requests

from dtagent.context import CONTEXT_NAME
from dtagent.otel import _log_warning
from dtagent.otel.events import EventType, AbstractEvents
from dtagent.otel.otel_manager import OtelManager
from dtagent.version import VERSION

##endregion COMPILE_REMOVE

##region ------------------------ CloudEvents BIZEVENTS ---------------------------------


class BizEvents(AbstractEvents):
    """Class parsing and sending bizevents."""

    from dtagent.config import Configuration  # COMPILE_REMOVE
    from dtagent.otel.instruments import Instruments  # COMPILE_REMOVE

    ENDPOINT_PATH = "/api/v2/bizevents/ingest"

    def __init__(self, configuration: Configuration):
        """Initializing payload cache and fields from configuration."""
        AbstractEvents.__init__(
            self,
            configuration,
            event_type="biz_events",
            default_params={"max_payload_bytes": 5120000, "api_content_type": "application/cloudevent-batch+json"},
        )

    def _pack_event_data(
        self, event_type: Union[str, EventType], event_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Packs given event data into CloudEvent format
        Args:
            event_type (str): Event type, e.g. EventType.CUSTOM_ALERT
            event_data (Dict[str, Any]): Event data in form of dict
            context (Optional[Dict[str, Any]]): Additional context to be added to event properties
            **kwargs: Additional parameters, like formatted_time
        Returns:
            Dict[str, Any]: Event payload in form accepted by Dynatrace BizEvents endpoint
        """
        from dtagent.util import _cleanup_data, get_now_timestamp_formatted  # COMPILE_REMOVE

        _context = context or {}
        _cloud_event_core = {
            "specversion": "1.0",
            "id": str(uuid.uuid4().hex),
            "source": self._resource_attributes.get("host.name", "snowflakecomputing.com"),
            "time": kwargs.get("formatted_time", get_now_timestamp_formatted()),
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
        event_payload = (
            # CloudEvents header data
            _cloud_event_core
            # event data with bizevents specific extra info
            | _cleanup_data(
                {
                    "type": event_type,
                    "data": event_data | _event_extra,
                }
            )
        )
        return event_payload

    def send_events(
        self,
        events_data: List[Dict[str, Any]],
        event_type: Optional[Union[str, EventType]] = "dsoa.bizevent",
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """Sends give list of events (in dict form) as CloudEvents to Dynatrace BizEvents endpoint

        Args:
            events (List): List of events data, each in form of dict
            context (Dict, optional): Additional information that should be appended to event data. Defaults to None.

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import get_now_timestamp_formatted  # COMPILE_REMOVE

        cloud_events = [
            self._pack_event_data(
                event_type=event_type,
                event_data=event_data,
                context=context,
                formatted_time=get_now_timestamp_formatted(),
            )
            for event_data in events_data
        ]

        return self._send_events(cloud_events)

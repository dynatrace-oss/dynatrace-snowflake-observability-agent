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
            event_type="davis_events",
            default_params={"max_payload_bytes": 5120000, "api_content_type": "application/cloudevent-batch+json"},
        )

    def send_events(self, events: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> bool:
        """Sends give list of events (in dict form) as CloudEvents to Dynatrace BizEvents endpoint

        Args:
            events (List): List of events data, each in form of dict
            context (Dict, optional): Additional information that should be appended to event data. Defaults to None.

        Returns:
            int: Count of all events that went through (or were scheduled successfully); -1 indicates a problem
        """
        from dtagent.util import _cleanup_data, get_now_timestamp_formatted  # COMPILE_REMOVE

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

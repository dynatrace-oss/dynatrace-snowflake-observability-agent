"""
Init module for dtagent.
"""

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

# Source-only imports
from dtagent.config import Configuration
from dtagent.otel import _gen_resource
from dtagent.otel.instruments import Instruments
from dtagent.otel.logs import Logs
from dtagent.otel.otel_manager import OtelManager
from dtagent.otel.spans import Spans
from dtagent.otel.metrics import Metrics
from dtagent.otel.events.generic import GenericEvents
from dtagent.otel.events.davis import DavisEvents
from dtagent.otel.events.bizevents import BizEvents
from dtagent.context import get_context_name_and_run_id
from dtagent.util import get_now_timestamp_formatted, is_regular_mode

##endregion COMPILE_REMOVE

##region ------------------------------ GENERAL_IMPORTS  -----------------------------------------
# DO NOT OPTIMIZE THOSE IMPORTS
# This is the set of imports in the final version of script after running compile and build
# All blocks and lines marked as COMPILE_REMOVE will be removed in the compiled version

import os
import types
import sys
import json
import uuid
import time
import logging
import datetime
import requests
import gc

import inspect

from typing import Tuple, Dict, List, Callable, Generator, Any, Union, Optional
from abc import ABC, abstractmethod
from snowflake import snowpark
from snowflake.snowpark.functions import current_timestamp
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, Tracer, SpanLimits
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry import version as otel_version

##endregion

##region ---------------------------- VARIABLES  -----------------------------------------
LL_TRACE = 5
logging.addLevelName(LL_TRACE, "TRACE")

LOG = logging.getLogger("DTAGENT")
LOG.setLevel(logging.DEBUG)
##endregion

# ----------------------------------------------------------------------------------
# ------------                       MAIN entry                         ------------
# ----------------------------------------------------------------------------------


class AbstractDynatraceSnowAgentConnector:
    """Abstract base class for DynatraceSnowAgent class"""

    def __init__(self, session: snowpark.Session) -> None:
        # --- initializing
        self._session = session

        if is_regular_mode(session):
            session.query_tag = "dsoa:" + get_now_timestamp_formatted()

        self._configuration = self._get_config(session)

        self.telemetry_allowed = set(
            [
                k
                for k, v in self._configuration.get(key="OTEL", default_value={}).items()
                if isinstance(v, dict) and not v.get("is_disabled", False)
            ]
        )

        if self._configuration:
            resource = _gen_resource(self._configuration)
            self._instruments = Instruments(self._configuration)
            self._logs = self._get_logs(resource)
            self._spans = self._get_spans(resource)
            self._metrics = self._get_metrics()
            self._events = self._get_events()
            self._davis_events = self._get_davis_events()
            self._biz_events = self._get_biz_events()
            self._set_max_consecutive_fails()

    def _get_spans(self, resource: Resource) -> Spans:
        """Returns new Spans instance"""
        return Spans(resource, self._configuration)

    def _get_logs(self, resource: Resource) -> Logs:
        """Returns new Logs instance"""
        return Logs(resource, self._configuration)

    def _get_metrics(self) -> Metrics:
        """Returns new Metrics instance"""
        return Metrics(self._instruments, self._configuration)

    def _get_events(self) -> GenericEvents:
        """Returns new Events instance"""
        return GenericEvents(self._configuration)

    def _get_davis_events(self) -> DavisEvents:
        """Returns new Events instance"""
        return DavisEvents(self._configuration)

    def _get_biz_events(self) -> BizEvents:
        """Returns new BizEvents instance"""
        return BizEvents(self._configuration)

    def _get_config(self, session: snowpark.Session) -> Configuration:
        """
        Wrapper around Configuration constructor call to re-use in Test
        """
        return Configuration(session)

    def report_execution_status(self, status: str, task_name: str, exec_id: str, details_dict: Optional[dict] = None):
        """Sends BizEvent for given task with given status if BizEvents are allowed and send_bizevents_on_run is enabled"""

        if "biz_events" in self.telemetry_allowed and self._configuration.get(
            plugin_name="self_monitoring", key="send_bizevents_on_run", default_value=True
        ):

            data_dict = {
                "event.provider": str(self._configuration.get(context="resource.attributes", key="host.name")),
                "dsoa.task.exec.id": exec_id,
                "dsoa.task.name": str(task_name),
                "dsoa.task.exec.status": str(status),
            }

            bizevents_sent = self._biz_events.report_via_api(
                query_data=[data_dict | (details_dict or {})],
                event_type="dsoa.task",
                context=get_context_name_and_run_id("self-monitoring"),
                is_data_structured=False,
            )
            bizevents_sent += self._biz_events.flush_events()
            if bizevents_sent == 0:
                LOG.warning("Unable to report task execution status via BizEvents: %s", str(data_dict))

    def _set_max_consecutive_fails(self):
        OtelManager.set_max_fail_count(self._configuration.get("max_consecutive_api_fails", context="otel", default_value=10))

    def handle_interrupted_run(self, source, exec_id, original_error):
        """Logs, original error, attempts to report failed run bizevent"""
        LOG.error("An error occurred during run: %s", str(original_error))
        try:
            self.report_execution_status("FAILED", source, exec_id, {"message": str(original_error)})
        except RuntimeError as e2:
            LOG.error("Unable to report failed run due to: %s", str(e2))

    def teardown(self) -> None:
        """wrapping up, shutting logger and tracer"""
        self._logs.shutdown_logger()
        self._spans.shutdown_tracer()

        if is_regular_mode(self._session):
            self._session.query_tag = None

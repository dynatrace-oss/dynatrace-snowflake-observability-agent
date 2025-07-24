"""Connector file allowing for sending custom telemetry data from snowflake to grail."""

##region ------------------------------ IMPORTS  -----------------------------------------
# Source-only imports
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
from dtagent import AbstractDynatraceSnowAgentConnector

from dtagent.config import Configuration
from dtagent.util import get_now_timestamp_formatted
from dtagent.otel.instruments import Instruments
from dtagent.otel.logs import Logs
from dtagent.otel.spans import Spans
from dtagent.otel.metrics import Metrics
from dtagent.otel.events import Events
from dtagent.otel.bizevents import BizEvents
from dtagent.version import VERSION
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------------------ GENERAL_IMPORTS  -----------------------------------------
# DO NOT OPTIMIZE THOSE IMPORTS
# This is the set of imports in the final version of script after running compile and build
# All blocks and lines marked as COMPILE_REMOVE will be removed in the compiled version

import types
import sys
import json
import uuid
import time
import logging
import datetime

from types import NoneType
from typing import Tuple, Dict, List, Callable, Generator, Any, Union, Optional
from enum import Enum
from abc import ABC, abstractmethod
import pandas as pd

from snowflake import snowpark

from opentelemetry.trace import SpanKind, INVALID_SPAN_ID, INVALID_TRACE_ID
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, Tracer, SpanLimits
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry import version as otel_version

##endregion

##region ---------------------------- VARIABLES  -----------------------------------------

##endregion

##region ---------------------------- CODE  -----------------------------------------

##INSERT
##INSERT build/_version.py
##INSERT src/dtagent/context.py
##INSERT src/dtagent/util.py
##INSERT src/dtagent/config.py
##INSERT src/dtagent/otel/otel_manager.py
##INSERT src/dtagent/otel/__init__.py
##INSERT src/dtagent/otel/instruments.py
##INSERT src/dtagent/otel/spans.py
##INSERT src/dtagent/otel/metrics.py
##INSERT src/dtagent/otel/logs.py
##INSERT src/dtagent/otel/events.py
##INSERT src/dtagent/otel/bizevents.py
##INSERT src/dtagent/plugins/__init__.py
##INSERT src/dtagent/__init__.py


##endregion CODE

# ----------------------------------------------------------------------------------
# ------------                       MAIN entry                         ------------
# ----------------------------------------------------------------------------------


class TelemetrySender(AbstractDynatraceSnowAgentConnector, Plugin):
    """Telemetry sender class delivers possibility of sending custom data
    from Snowflake to Grail, not being limited by plugins."""

    def __init__(self, session: snowpark.Session, params: dict):
        """
        Initialization for TelemetrySender class.
        """
        from dtagent.context import get_context_by_name  # COMPILE_REMOVE

        Plugin.__init__(self, session=session)
        AbstractDynatraceSnowAgentConnector.__init__(self, session)

        self.__context_name = "telemetry_sender"
        self.__context = get_context_by_name(self.__context_name)

        self._params = params or {}
        # if not turned off we expect that data delivered in source follows Dynatrace Snowflake Observability Agent data structure
        self._auto_mode = self._params.get("auto_mode", True)
        # in case of auto-mode enabled we can disable sending metrics based on METRICS
        self._send_metrics = self._params.get("metrics", True)
        # in case of auto-mode enable we can disable sending logs
        # in case of auto-mode disabled we will send the source as plain logs
        self._send_logs = self._params.get("logs", True)
        # in case of auto-mode enable we can disable sending events based on EVENT_TIMESTAMPS
        # in case of auto-mode disabled we will send the source as plain events
        self._send_events = self._params.get("events", self._auto_mode)
        # in case of auto-mode disabled we will send the source as bizevents
        self._send_bizevents = self._params.get("bizevents", False)

    def process(self):
        """we don't use it but Plugin marks it as abstract"""

        return None

    def _get_source_rows(self, source: Union[str, dict, list]) -> Generator[Dict, None, None]:
        """Delivers generator over different types of sources.
        For a name of view/table to query it will use _get_table_rows().
        For a single object it will wrap it as a list and will continute to ...
        For a list of objects it will deliver a generator over that list.

        Args:
            source (Union[str, dict, list]): _description_

        Yields:
            Generator[Dict, None, None]: _description_
        """

        if isinstance(source, str):
            for row in self._get_table_rows(source):
                yield row

        if isinstance(source, dict):
            source = [source]

        if isinstance(source, list):
            for row_dict in source:
                yield row_dict

    def send_data(self, source: Union[str, dict, list], exec_id: str = get_now_timestamp_formatted()) -> Tuple[int, int, int, int, int]:
        """Sends telemetry data from given source based on the parameters provided to the stored procedure

        Args:
            source (Union[str, dict, list]): the source of telemetry data

        Returns:
            Tuple[int, int, int, int]: Count of objects, log lines, metrics, events, and bizevents sent
        """
        from dtagent.otel.events import EventType  # COMPILE_REMOVE

        self.report_execution_status(status="STARTED", task_name="telemetry_sender", exec_id=exec_id)

        entries_cnt, logs_cnt, metrics_cnt, events_cnt, bizevents_cnt = (0, 0, 0, 0, 0)
        if self._auto_mode:
            entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
                lambda: self._get_source_rows(source),
                self.__context_name,
                report_logs=self._send_logs,
                report_metrics=self._send_metrics,
                report_timestamp_events=self._send_events,
                start_time="TIMESTAMP",
                log_completion=False,
            )
        else:
            if self._send_logs or self._send_events:
                for row_dict in self._get_source_rows(source):
                    from dtagent.util import _cleanup_dict  # COMPILE_REMOVE

                    processed_last_timestamp = row_dict.get("timestamp", None)
                    event_dict = _cleanup_dict({"timestamp": processed_last_timestamp, **row_dict})
                    s_log_level = "INFO" if row_dict.get("status.code", "OK") == "OK" else "ERROR"

                    if self._send_logs:
                        self._logs.send_log(
                            row_dict.get("_message", f"Log entry sent with {self.__context_name}"),
                            extra=event_dict,
                            log_level=getattr(logging, s_log_level, logging.INFO),
                            context=self.__context,
                        )
                        logs_cnt += 1

                    if self._send_events:
                        try:
                            events_cnt += self._events.report_via_api(
                                query_data=row_dict,
                                event_type=(EventType[row_dict["event.type"]] if "event.type" in row_dict else EventType.CUSTOM_INFO),
                                title=row_dict.get("_message", f"Log entry sent with {self.__context_name}"),
                                context=self.__context,
                            )
                        except ValueError as e:
                            from dtagent import LOG  # COMPILE_REMOVE

                            self.report_execution_status(status="FAILED", task_name="telemetry_sender", exec_id=exec_id)
                            LOG.error("Could not send event due to " + e)

                    entries_cnt += 1
            else:
                entries_cnt = sum(1 for _ in self._get_source_rows(source))

            if self._send_bizevents:
                import itertools

                chunk_size = 100

                def __chunked_iterable(iterable, size):
                    it = iter(iterable)
                    while chunk := list(itertools.islice(it, size)):
                        yield chunk

                for chunk in __chunked_iterable(self._get_source_rows(source), chunk_size):
                    bizevents_cnt += self._bizevents.report_via_api(
                        chunk,
                        self.__context,
                        event_type=EventType.CUSTOM_INFO,
                        is_data_structured=False,
                    )
                bizevents_cnt += self._bizevents.flush_events()

            if self._send_events:
                self._events.flush_events()

        self.report_execution_status(status="FINISHED", task_name="telemetry_sender", exec_id=exec_id)

        self._report_execution(
            self.__context_name,
            get_now_timestamp_formatted(),
            None,
            {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,
                "bizevents": bizevents_cnt,
            },
        )

        return (entries_cnt, logs_cnt, metrics_cnt, events_cnt, bizevents_cnt)


def main(session: snowpark.Session, source: Union[str, dict, list], params: dict) -> str:
    """
    MAIN entry to this stored procedure - this is where the fun begins
    """
    sender = TelemetrySender(session, params)
    exec_id = get_now_timestamp_formatted()
    try:
        results = sender.send_data(source, exec_id)
    except RuntimeError as e:
        sender.handle_interrupted_run(source, exec_id, str(e))

    sender.teardown()

    return results

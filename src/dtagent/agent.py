"""Main DynatraceSnowAgent file"""

##region ------------------------------ IMPORTS  -----------------------------------------
# Source-only imports
from dtagent import AbstractDynatraceSnowAgentConnector
from dtagent.version import VERSION
from dtagent.util import get_now_timestamp_formatted

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
##INSERT src/dtagent/plugins/*.py
##INSERT src/dtagent/__init__.py

##endregion CODE

# ----------------------------------------------------------------------------------
# ------------                       MAIN entry                         ------------
# ----------------------------------------------------------------------------------


class DynatraceSnowAgent(AbstractDynatraceSnowAgentConnector):
    """Main DynatraceSnowAgent class managing plugins executions"""

    def process(self, sources: List, run_proc: bool = True) -> Dict:
        """Starts plugins specified in sources executions"""
        # --- processing measurement sources
        import inspect
        from dtagent import LOG

        results: dict = {}
        for source in sources:
            from dtagent.plugins import _get_plugin_class  # COMPILE_REMOVE

            c_source = _get_plugin_class(source)
            exec_id = get_now_timestamp_formatted()

            self.report_execution_status(status="STARTED", task_name=source, exec_id=exec_id)

            self._session.query_tag = f"dsoa.version:{ str(VERSION) }.plugin:{ c_source.__name__ }.{ exec_id }"

            if inspect.isclass(c_source):
                #
                # running the plugin
                #
                try:
                    results[source] = c_source(
                        session=self._session,
                        logs=self._logs,
                        spans=self._spans,
                        metrics=self._metrics,
                        configuration=self._configuration,
                        events=self._events,
                        bizevents=self._bizevents,
                    ).process(run_proc)
                    #
                    self.report_execution_status(status="FINISHED", task_name=source, exec_id=exec_id)
                except RuntimeError as e:
                    self.handle_interrupted_run(source, exec_id, str(e))
            else:
                self.report_execution_status(status="FAILED", task_name=source, exec_id=exec_id)
                results[source] = c_source
                LOG.warning(f"""Requested measuring source {source} that is not implemented: {results[source]}""")

        return results

    def teardown(self) -> None:
        """ "wrapping up, shutting logger and tracer"""
        self._logs.shutdown_logger()
        self._spans.shutdown_tracer()
        self._session.query_tag = None


def main(session: snowpark.Session, sources: List) -> dict:
    """
    MAIN entry to this stored procedure - this is where the fun begins
    """
    agent = DynatraceSnowAgent(session)
    results = agent.process(sources)
    agent.teardown()

    return results

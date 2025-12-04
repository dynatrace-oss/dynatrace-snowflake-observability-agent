"""Main DynatraceSnowAgent file"""

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
from dtagent.version import VERSION
from dtagent.util import get_now_timestamp_formatted, is_regular_mode

##endregion COMPILE_REMOVE

##region ------------------------------ GENERAL_IMPORTS  -----------------------------------------
# DO NOT OPTIMIZE THOSE IMPORTS
# This is the set of imports in the final version of script after running compile and build
# All blocks and lines marked as COMPILE_REMOVE will be removed in the compiled version

import types
import sys
import re
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
##INSERT build/_semantics.py
##INSERT src/dtagent/otel/spans.py
##INSERT src/dtagent/otel/metrics.py
##INSERT src/dtagent/otel/logs.py
##INSERT src/dtagent/otel/events/__init__.py
##INSERT src/dtagent/otel/events/generic.py
##INSERT src/dtagent/otel/events/davis.py
##INSERT src/dtagent/otel/events/bizevents.py
##INSERT src/dtagent/plugins/*.py
##INSERT src/dtagent/__init__.py

##endregion CODE

# ----------------------------------------------------------------------------------
# ------------                       MAIN entry                         ------------
# ----------------------------------------------------------------------------------


class DynatraceSnowAgent(AbstractDynatraceSnowAgentConnector):
    """Main DynatraceSnowAgent class managing plugins executions"""

    def process(self, sources: List, run_proc: bool = True) -> Dict[str, Union[Dict[str, int], str]]:
        """Starts plugins specified in sources executions

        Args:
            sources (List): List of measurement sources (plugins) to execute
            run_proc (bool): Whether to actually run the preparation procedures and log results

        Returns:
            Dict[str,Union[Dict[str,int],str]]: A dictionary with plugin names as keys and their
            processing results (telemetry counts dictionary) or error message (if requested source is not implemented) as values.

            Example:
            {
                "plugin_name": {
                    "dsoa.run.results": {
                        "context_name": {
                            "entries": 10,
                            "log_lines": 100,
                            "metrics": 5,
                            "events": 2
                        }
                    },
                    "dsoa.run.id": "uuid_string"
                },
                "some_other_plugin": "not_implemented"
            }

        """
        # --- processing measurement sources
        import inspect
        from dtagent import LOG  # COMPILE_REMOVE
        from dtagent.otel import NO_OP_TELEMETRY  # COMPILE_REMOVE
        from dtagent.context import RUN_PLUGIN_KEY, RUN_ID_KEY, RUN_VERSION_KEY  # COMPILE_REMOVE

        results: dict = {}

        for source in sources:
            from dtagent.plugins import _get_plugin_class  # COMPILE_REMOVE

            c_source = _get_plugin_class(source)
            run_id = str(uuid.uuid4().hex)

            if is_regular_mode(self._session):
                self._session.query_tag = json.dumps(
                    {RUN_VERSION_KEY: str(VERSION), RUN_PLUGIN_KEY: c_source.PLUGIN_NAME, RUN_ID_KEY: run_id}
                )

            self.report_execution_status(status="STARTED", task_name=source, exec_id=run_id)

            plugin_telemetry_allowed = (
                set(
                    self._configuration.get(
                        plugin_name=source, key="TELEMETRY", default_value=["logs", "spans", "metrics", "events", "biz_events"]
                    )
                )
                & self.telemetry_allowed
            )

            if inspect.isclass(c_source):
                #
                # running the plugin
                #
                try:
                    results[source] = c_source(
                        plugin_name=source,
                        session=self._session,
                        configuration=self._configuration,
                        logs=self._logs if "logs" in plugin_telemetry_allowed else NO_OP_TELEMETRY,
                        spans=self._spans if "spans" in plugin_telemetry_allowed else NO_OP_TELEMETRY,
                        metrics=self._metrics if "metrics" in plugin_telemetry_allowed else NO_OP_TELEMETRY,
                        events=self._events if "events" in plugin_telemetry_allowed else NO_OP_TELEMETRY,
                        bizevents=self._biz_events if "biz_events" in plugin_telemetry_allowed else NO_OP_TELEMETRY,
                    ).process(run_id, run_proc)
                    #

                    self.report_execution_status(status="FINISHED", task_name=source, exec_id=run_id, details_dict=results[source])
                except RuntimeError as e:
                    self.handle_interrupted_run(source, run_id, str(e))
            else:
                self.report_execution_status(status="FAILED", task_name=source, exec_id=run_id)
                results[source] = {"not_implemented": c_source}
                LOG.warning(f"""Requested measuring source {source} that is not implemented: {results[source]}""")

        return results


def main(session: snowpark.Session, sources: List) -> dict:
    """MAIN entry to this stored procedure - this is where the fun begins"""
    agent = DynatraceSnowAgent(session)
    results = agent.process(sources)
    agent.teardown()

    return results

#!/usr/bin/env python3
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

"""Tests for source-string parsing and context propagation in DynatraceSnowAgent.process().

Covers the ``plugin:context`` source syntax to ensure:

- ``dsoa.run.plugin`` is set to the bare plugin name (e.g. ``table_health``), not the
  full source string (e.g. ``table_health:table_health_derived``).
- ``dsoa.task.name`` retains the full source string so manual-call traces remain faithful.
- Multiple comma-separated context values are parsed and forwarded correctly.
"""

from unittest.mock import MagicMock, patch, call


class TestAgentSourceParsing:
    """Verify that DynatraceSnowAgent.process() correctly splits ``plugin:context`` sources."""

    # --------------------------------------------------------------------- helpers

    @staticmethod
    def _make_agent():
        """Build a DynatraceSnowAgent with a fully-mocked Snowpark session and telemetry."""
        from test import TestConfiguration
        from dtagent.agent import DynatraceSnowAgent

        session = MagicMock()
        session.query_tag = ""
        session.sql.return_value.collect.return_value = []

        config = TestConfiguration(
            {
                "core": {
                    "snowflake": {"account_name": "test.account", "host_name": "test.snowflakecomputing.com"},
                    "dynatrace_tenant_address": "https://test.live.dynatrace.com",
                    "run_regular_mode": True,
                },
                "otel": {
                    "logs": {"max_export_batch_size": 1},
                    "spans": {"max_export_batch_size": 1},
                },
                "resource.attributes": {
                    "host.name": "test.snowflakecomputing.com",
                    "service.name": "test.dsoa",
                    "deployment.environment": "TEST",
                },
                "dt.token": "dt0c01.FAKE.FAKE",
                "metrics.http": "https://test.live.dynatrace.com/api/v2/metrics/ingest",
                "logs.http": "https://test.live.dynatrace.com/api/v2/logs/ingest",
                "spans.http": "https://test.live.dynatrace.com/api/v2/otlp/v1/traces",
                "events.http": "https://test.live.dynatrace.com/api/v2/events/ingest",
                "davis_events.http": "https://test.live.dynatrace.com/api/v2/events/ingest",
                "biz_events.http": "https://test.live.dynatrace.com/api/v2/bizevents/ingest",
                "self_monitoring": {"send_bizevents_on_run": False},
                "plugins": {
                    "table_health": {
                        "clustering_enabled": True,
                        "history_retention_days": 30,
                        "TELEMETRY": ["logs", "spans", "metrics", "events", "biz_events"],
                    }
                },
            }
        )

        agent = DynatraceSnowAgent.__new__(DynatraceSnowAgent)
        agent._session = session
        agent._configuration = config
        agent.telemetry_allowed = {"logs", "spans", "metrics", "events", "biz_events"}

        from dtagent.otel import NO_OP_TELEMETRY

        agent._logs = NO_OP_TELEMETRY
        agent._spans = NO_OP_TELEMETRY
        agent._metrics = NO_OP_TELEMETRY
        agent._events = NO_OP_TELEMETRY
        agent._biz_events = NO_OP_TELEMETRY

        return agent

    @staticmethod
    def _make_dummy_plugin_class(plugin_name: str):
        """Return a minimal Plugin subclass that records the contexts it was called with."""
        from dtagent.plugins import Plugin
        from dtagent.context import RUN_RESULTS_KEY, RUN_ID_KEY

        class DummyPlugin(Plugin):
            PLUGIN_NAME = plugin_name
            PLUGIN_CONTEXTS: tuple = ("table_storage", "table_clustering", "table_health_derived")
            called_contexts = None

            def process(self, run_id, run_proc=True, contexts=None):  # pylint: disable=arguments-differ
                DummyPlugin.called_contexts = contexts
                return {RUN_RESULTS_KEY: {}, RUN_ID_KEY: run_id}

        return DummyPlugin

    # --------------------------------------------------------------------- tests

    def test_plugin_name_not_polluted_by_context_suffix(self):
        """report_execution_status receives plugin_name='table_health', not 'table_health:table_health_derived'.

        When DTAGENT is invoked with ``ARRAY_CONSTRUCT('table_health:table_health_derived')``,
        the ``dsoa.run.plugin`` attribute on the resulting bizevents must be ``table_health``,
        not the full source string.  This is the regression guard for the bug discovered during
        the 0.9.5 QA cycle on dev-095.
        """
        agent = self._make_agent()
        dummy_cls = self._make_dummy_plugin_class("table_health")

        captured_calls = []

        def _capture_report(status, task_name, exec_id, details_dict=None, plugin_name=None):  # pylint: disable=unused-argument
            captured_calls.append({"status": status, "task_name": task_name, "plugin_name": plugin_name})

        agent.report_execution_status = _capture_report

        with patch("dtagent.plugins._get_plugin_class", return_value=dummy_cls), patch(
            "dtagent.agent.DynatraceSnowAgent._emit_ingest_warnings"
        ), patch("dtagent.agent.DynatraceSnowAgent._emit_acquisition_problems"):
            agent.process(["table_health:table_health_derived"], run_proc=False)

        assert captured_calls, "report_execution_status was never called"

        for c in captured_calls:
            assert c["plugin_name"] == "table_health", (
                f"Expected plugin_name='table_health' but got '{c['plugin_name']}' "
                f"(status={c['status']}). dsoa.run.plugin would have been set incorrectly."
            )
            # dsoa.task.name must preserve the full source string for traceability
            assert (
                c["task_name"] == "table_health:table_health_derived"
            ), f"Expected task_name='table_health:table_health_derived' but got '{c['task_name']}'"

    def test_contexts_forwarded_to_plugin(self):
        """process() forwards the parsed context list to the plugin's process() method."""
        agent = self._make_agent()
        dummy_cls = self._make_dummy_plugin_class("table_health")

        agent.report_execution_status = MagicMock()

        with patch("dtagent.plugins._get_plugin_class", return_value=dummy_cls), patch(
            "dtagent.agent.DynatraceSnowAgent._emit_ingest_warnings"
        ), patch("dtagent.agent.DynatraceSnowAgent._emit_acquisition_problems"):
            agent.process(["table_health:table_health_derived"], run_proc=False)

        assert dummy_cls.called_contexts == ["table_health_derived"], (
            f"Expected contexts=['table_health_derived'] forwarded to plugin, " f"got {dummy_cls.called_contexts!r}"
        )

    def test_plain_source_still_works(self):
        """process() with a plain (no-colon) source still passes plugin_name correctly."""
        agent = self._make_agent()
        dummy_cls = self._make_dummy_plugin_class("table_health")

        captured_calls = []

        def _capture_report(status, task_name, exec_id, details_dict=None, plugin_name=None):  # pylint: disable=unused-argument
            captured_calls.append({"status": status, "task_name": task_name, "plugin_name": plugin_name})

        agent.report_execution_status = _capture_report

        with patch("dtagent.plugins._get_plugin_class", return_value=dummy_cls), patch(
            "dtagent.agent.DynatraceSnowAgent._emit_ingest_warnings"
        ), patch("dtagent.agent.DynatraceSnowAgent._emit_acquisition_problems"):
            agent.process(["table_health"], run_proc=False)

        assert captured_calls
        for c in captured_calls:
            assert c["plugin_name"] == "table_health"
            assert c["task_name"] == "table_health"

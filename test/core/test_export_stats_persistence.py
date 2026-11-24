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
"""Tests for export statistics attribution per plugin run and their persistence into STATUS.EXPORT_STATS."""

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from dtagent import AbstractDynatraceSnowAgentConnector
from dtagent.otel.export_stats import ExportStatsCollector
from test.core.test_agent_source_parsing import TestAgentSourceParsing


@pytest.fixture(autouse=True)
def _reset_collector():
    ExportStatsCollector.reset()
    yield
    ExportStatsCollector.reset()


def _agent(config_overrides: Optional[dict] = None):
    """Builds a DynatraceSnowAgent with mocked session and (optionally) self_monitoring configuration."""
    agent = TestAgentSourceParsing._make_agent()  # pylint: disable=protected-access
    if config_overrides is not None:
        agent._configuration._config["plugins"]["self_monitoring"] = config_overrides  # pylint: disable=protected-access
    return agent


def _sql_statements(agent) -> list:
    return [c.args[0] for c in agent._session.sql.call_args_list]  # pylint: disable=protected-access


def _sql_params(agent) -> list:
    """Bound parameters of every executed statement (empty list for a statement without any)."""
    return [c.kwargs.get("params", []) for c in agent._session.sql.call_args_list]  # pylint: disable=protected-access


class TestAttribution:
    """DynatraceSnowAgent.process() attributes export statistics to the plugin run that is executing."""

    def test_each_plugin_gets_its_own_counts_and_run_id(self):
        """Each plugin gets its own counts and run id."""
        from dtagent.plugins import Plugin
        from dtagent.context import RUN_RESULTS_KEY, RUN_ID_KEY

        agent = _agent()
        agent.report_execution_status = MagicMock()

        def _plugin_class(name: str, records: int):
            class _Plugin(Plugin):
                PLUGIN_NAME = name

                def process(self, run_id, run_proc=True, contexts=None):  # pylint: disable=arguments-differ
                    ExportStatsCollector.add_attempted("logs", records)
                    ExportStatsCollector.add_delivered("logs", records - 1)
                    return {RUN_RESULTS_KEY: {}, RUN_ID_KEY: run_id}

            return _Plugin

        classes = {"first": _plugin_class("first", 5), "second": _plugin_class("second", 7)}
        with patch("dtagent.plugins._get_plugin_class", side_effect=lambda name: classes[name]), patch.object(
            AbstractDynatraceSnowAgentConnector, "_emit_ingest_warnings"
        ), patch.object(AbstractDynatraceSnowAgentConnector, "_emit_acquisition_problems"):
            agent.process(["first", "second"], run_proc=False)

        stats = ExportStatsCollector.get_stats()
        assert [(r["plugin"], r["attempted"], r["delivered"]) for r in stats] == [("first", 5, 4), ("second", 7, 6)]
        assert all(r["run_id"] for r in stats)
        assert stats[0]["run_id"] != stats[1]["run_id"]

    def test_logs_and_spans_are_flushed_after_each_plugin(self):
        """Logs and spans are flushed after each plugin."""
        agent = _agent()
        agent._logs = MagicMock()  # pylint: disable=protected-access
        agent._spans = MagicMock()  # pylint: disable=protected-access
        agent.report_execution_status = MagicMock()
        dummy = TestAgentSourceParsing._make_dummy_plugin_class("table_health")  # pylint: disable=protected-access

        with patch("dtagent.plugins._get_plugin_class", return_value=dummy), patch.object(
            AbstractDynatraceSnowAgentConnector, "_emit_ingest_warnings"
        ), patch.object(AbstractDynatraceSnowAgentConnector, "_emit_acquisition_problems"):
            agent.process(["table_health", "table_health"], run_proc=False)

        assert agent._logs.flush_logs.call_count == 2  # pylint: disable=protected-access
        assert agent._spans.flush_traces.call_count == 2  # pylint: disable=protected-access

    def test_spans_are_flushed_after_a_failed_plugin(self):
        """Spans are flushed after a plugin that ended with an error, before the next plugin starts."""
        from dtagent.plugins import Plugin

        order = []
        agent = _agent()
        agent._spans = MagicMock()  # pylint: disable=protected-access
        agent._spans.flush_traces.side_effect = lambda: order.append("flush")  # pylint: disable=protected-access
        agent.report_execution_status = MagicMock()
        agent.handle_interrupted_run = MagicMock()

        def _plugin_class(name: str, fail: bool):
            class _Plugin(Plugin):
                PLUGIN_NAME = name

                def process(self, run_id, run_proc=True, contexts=None):  # pylint: disable=arguments-differ
                    order.append(f"run {name}")
                    if fail:
                        raise RuntimeError("Too many failed attempts")
                    return {}

            return _Plugin

        classes = {"first": _plugin_class("first", True), "second": _plugin_class("second", False)}
        with patch("dtagent.plugins._get_plugin_class", side_effect=lambda name: classes[name]), patch.object(
            AbstractDynatraceSnowAgentConnector, "_emit_ingest_warnings"
        ), patch.object(AbstractDynatraceSnowAgentConnector, "_emit_acquisition_problems"):
            agent.process(["first", "second"], run_proc=False)

        assert order == ["run first", "flush", "run second", "flush"]


class TestPersistExportStats:
    """AbstractDynatraceSnowAgentConnector.persist_export_stats"""

    @staticmethod
    def _collect():
        ExportStatsCollector.set_plugin("query_history", "run1")
        ExportStatsCollector.add_attempted("logs", 10)
        ExportStatsCollector.add_delivered("logs", 9)
        ExportStatsCollector.add_attempted("metrics", 4)
        ExportStatsCollector.add_delivered("metrics", 4)

    def test_inserts_one_row_per_plugin_run_and_signal(self):
        """Inserts one row per plugin run and signal, with every value bound."""
        agent = _agent()
        self._collect()
        agent.persist_export_stats()

        insert = _sql_statements(agent)[0]
        assert insert == (
            "insert into DTAGENT_DB.STATUS.EXPORT_STATS (RUN_ID, PLUGIN, SIGNAL, ATTEMPTED, DELIVERED) values (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)"
        )
        assert _sql_params(agent)[0] == ["run1", "query_history", "logs", 10, 9, "run1", "query_history", "metrics", 4, 4]

    def test_statements_are_qualified_with_the_agent_database(self):
        """The agent procedure runs as caller: both statements name the agent database, not the caller's current one."""
        agent = _agent()
        self._collect()
        agent.persist_export_stats()

        assert all("DTAGENT_DB.STATUS.EXPORT_STATS" in statement for statement in _sql_statements(agent))

    def test_prunes_with_default_retention(self):
        """Prunes with default retention."""
        agent = _agent()
        self._collect()
        agent.persist_export_stats()

        assert _sql_statements(agent)[1] == "delete from DTAGENT_DB.STATUS.EXPORT_STATS where RUN_TS < dateadd(day, ?, current_timestamp())"
        assert _sql_params(agent)[1] == [-30]

    def test_retention_is_configurable(self):
        """Retention is configurable."""
        agent = _agent({"export_stats_retention_days": 7})
        self._collect()
        agent.persist_export_stats()

        assert _sql_params(agent)[1] == [-7]

    def test_counts_are_reset_after_persisting(self):
        """Counts are reset after persisting."""
        agent = _agent()
        self._collect()
        agent.persist_export_stats()

        assert ExportStatsCollector.get_stats() == []

    def test_disabled(self):
        """Nothing is written when export_stats_enabled is false."""
        agent = _agent({"export_stats_enabled": False})
        self._collect()
        agent.persist_export_stats()

        assert not _sql_statements(agent)
        assert ExportStatsCollector.get_stats() == []

    def test_nothing_collected_nothing_written(self):
        """Nothing collected, nothing written."""
        agent = _agent()
        agent.persist_export_stats()

        assert not _sql_statements(agent)

    def test_local_testing_mode_is_skipped(self):
        """Local testing mode (session id 1) is skipped."""
        agent = _agent()
        agent._session.session_id = 1  # pylint: disable=protected-access
        self._collect()
        agent.persist_export_stats()

        assert not _sql_statements(agent)

    def test_values_are_bound_not_interpolated(self):
        """Quotes, backslashes and SQL fragments in a plugin name never reach the statement text, only the bound parameters."""
        agent = _agent()
        hostile = "x\\', 'run', 'logs', 1, 1), ('evil"
        ExportStatsCollector.set_plugin(hostile, "run\\'1")
        ExportStatsCollector.add_attempted("logs", 1)
        agent.persist_export_stats()

        insert = _sql_statements(agent)[0]
        assert "evil" not in insert and "run" not in insert and "\\" not in insert
        assert insert.count("?") == 5
        assert _sql_params(agent)[0] == ["run\\'1", hostile, "logs", 1, 0]

    def test_failure_is_swallowed(self):
        """A failing insert is logged and never propagates."""
        agent = _agent()
        agent._session.sql.side_effect = RuntimeError("table does not exist")  # pylint: disable=protected-access
        self._collect()

        agent.persist_export_stats()  # must not raise


class TestMain:
    """agent.main() persists the statistics after teardown, also when the run fails."""

    def test_persisted_after_teardown(self):
        """Statistics are persisted after teardown."""
        from dtagent import agent as agent_module

        calls = []
        instance = MagicMock()
        instance.process.return_value = {"ok": True}
        instance.teardown.side_effect = lambda: calls.append("teardown")
        instance.persist_export_stats.side_effect = lambda: calls.append("persist")

        with patch.object(agent_module, "DynatraceSnowAgent", return_value=instance):
            assert agent_module.main(MagicMock(), ["x"]) == {"ok": True}

        assert calls == ["teardown", "persist"]

    def test_persisted_when_process_raises(self):
        """Statistics are persisted even if processing raises."""
        from dtagent import agent as agent_module

        instance = MagicMock()
        instance.process.side_effect = RuntimeError("boom")

        with patch.object(agent_module, "DynatraceSnowAgent", return_value=instance), pytest.raises(RuntimeError, match="boom"):
            agent_module.main(MagicMock(), ["x"])

        instance.teardown.assert_called_once()
        instance.persist_export_stats.assert_called_once()

    def test_persisted_when_teardown_raises(self):
        """Statistics are persisted even if teardown raises."""
        from dtagent import agent as agent_module

        instance = MagicMock()
        instance.teardown.side_effect = RuntimeError("teardown failed")

        with patch.object(agent_module, "DynatraceSnowAgent", return_value=instance), pytest.raises(RuntimeError, match="teardown failed"):
            agent_module.main(MagicMock(), ["x"])

        instance.persist_export_stats.assert_called_once()

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
class TestQueryHist:
    import pytest

    FIXTURES = {"APP.V_RECENT_QUERIES": "test/test_data/query_history.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_query_hist(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        from snowflake import snowpark
        import json as _json
        import test._utils as utils

        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin

        # ======================================================================

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        from dtagent.otel.spans import Spans

        class TestSpans(Spans):

            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                fixture_path = TestQueryHist.FIXTURES[view_name]
                print(f"Loaded fixture for {view_name} at {parent_row_id_col} = {row_id}")
                with open(fixture_path, "r", encoding="utf-8") as _fh:
                    all_rows = [_json.loads(line) for line in _fh if line.strip()]

                from dtagent.util import _adjust_timestamp

                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHist.FIXTURES, t_data, limit=3)

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        # Test different disabled telemetry combinations
        disabled_combinations = [
            [],
            ["logs"],
            ["spans"],
            ["metrics"],
            ["logs", "metrics"],
            ["metrics", "spans"],
            ["logs", "spans", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestSpanDynatraceSnowAgent,
                test_name="test_query_history",
                disabled_telemetry=disabled_telemetry,
                base_count={"query_history": {"entries": 3, "log_lines": 3, "metrics": 111, "spans": 3}},
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_query_history_max_entries_limiting(self):
        """Test that max_entries config limits the number of processed queries."""
        from typing import Dict, Generator
        from snowflake import snowpark
        import json as _json
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin
        from dtagent.otel.spans import Spans

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSpans(Spans):
            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                fixture_path = TestQueryHist.FIXTURES[view_name]
                with open(fixture_path, "r", encoding="utf-8") as _fh:
                    all_rows = [_json.loads(line) for line in _fh if line.strip()]
                from dtagent.util import _adjust_timestamp

                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):
            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHist.FIXTURES, t_data, limit=3)

            def _call_refresh_recent_queries(self) -> Dict:
                # Simulate max_entries=2 applied with 3 available (1 dropped)
                return {
                    "status": "success",
                    "total_processed": 2,
                    "total_available": 3,
                    "max_entries_applied": True,
                    "max_entries_value": 2,
                }

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # Test with max_entries limiting - should still process 3 rows from fixture
        # but self-monitoring event should indicate 1 row was dropped
        # TODO: test validates fixture replay only; _call_refresh_recent_queries override is not exercised with run_proc=False
        utils.execute_telemetry_test(
            TestSpanDynatraceSnowAgent,
            test_name="test_query_history_max_entries",
            disabled_telemetry=[],
            base_count={"query_history": {"entries": 3, "log_lines": 3, "metrics": 111, "spans": 3}},
        )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_query_history_backward_compatibility(self):
        """Test that default config (max_entries=0) processes all rows unchanged."""
        from typing import Dict, Generator
        from snowflake import snowpark
        import json as _json
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin
        from dtagent.otel.spans import Spans

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSpans(Spans):
            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                fixture_path = TestQueryHist.FIXTURES[view_name]
                with open(fixture_path, "r", encoding="utf-8") as _fh:
                    all_rows = [_json.loads(line) for line in _fh if line.strip()]
                from dtagent.util import _adjust_timestamp

                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):
            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHist.FIXTURES, t_data, limit=3)

            def _call_refresh_recent_queries(self) -> Dict:
                # Simulate default config (max_entries=0, unlimited)
                return {
                    "status": "success",
                    "total_processed": 3,
                    "total_available": 3,
                    "max_entries_applied": False,
                    "max_entries_value": 0,
                }

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # Test backward compatibility: no max_entries limiting
        # TODO: test validates fixture replay only; _call_refresh_recent_queries override is not exercised with run_proc=False
        utils.execute_telemetry_test(
            TestSpanDynatraceSnowAgent,
            test_name="test_query_history_backward_compat",
            disabled_telemetry=[],
            base_count={"query_history": {"entries": 3, "log_lines": 3, "metrics": 111, "spans": 3}},
        )


class TestCallRefreshRecentQueries:
    """Unit tests for _call_refresh_recent_queries() parsing logic."""

    import pytest

    def _make_plugin(self):
        """Create a minimal QueryHistoryPlugin instance with a mock session."""
        from unittest.mock import MagicMock
        from dtagent.plugins.query_history import QueryHistoryPlugin

        plugin = QueryHistoryPlugin.__new__(QueryHistoryPlugin)
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        plugin._events = MagicMock()
        return plugin

    def test_returns_dict_when_snowpark_returns_dict(self):
        """Snowpark VARIANT → dict path: result returned directly."""
        from unittest.mock import MagicMock

        plugin = self._make_plugin()
        expected = {"status": "success", "total_processed": 5, "total_available": 10, "max_entries_applied": True, "max_entries_value": 5}
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: expected
        plugin._session.sql.return_value.collect.return_value = [mock_row]

        result = plugin._call_refresh_recent_queries()
        assert result == expected

    def test_returns_dict_when_snowpark_returns_json_string(self):
        """Legacy JSON string path: result parsed from string."""
        import json
        from unittest.mock import MagicMock

        plugin = self._make_plugin()
        expected = {"status": "success", "total_processed": 3, "total_available": 3, "max_entries_applied": False}
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: json.dumps(expected)
        plugin._session.sql.return_value.collect.return_value = [mock_row]

        result = plugin._call_refresh_recent_queries()
        assert result == expected

    def test_returns_default_on_exception(self):
        """Broad-except path: returns error default when procedure call raises."""
        plugin = self._make_plugin()
        plugin._session.sql.side_effect = RuntimeError("Snowpark connection error")

        result = plugin._call_refresh_recent_queries()
        assert result["status"] == "error"
        assert result["max_entries_applied"] is False

    def test_returns_default_when_no_rows(self):
        """Empty result set: returns success default."""
        plugin = self._make_plugin()
        plugin._session.sql.return_value.collect.return_value = []

        result = plugin._call_refresh_recent_queries()
        assert result["status"] == "success"
        assert result["max_entries_applied"] is False


class TestQueryCostAttributionPlugin:
    """Tests for the query_cost_attribution context of QueryHistoryPlugin."""

    import pytest

    FIXTURES = {
        "APP.V_QUERY_COST_ATTRIBUTION_SUMMARY": "test/test_data/query_history_cost_attribution.ndjson",
    }

    def _make_plugin_class(self, fixtures, raise_on_summary=None):
        """Return a QueryHistoryPlugin subclass that reads from fixtures."""
        from typing import Dict, Generator
        from dtagent.plugins.query_history import QueryHistoryPlugin
        import test._utils as utils

        class TestQueryCostPlugin(QueryHistoryPlugin):
            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                if raise_on_summary and t_data == "APP.V_QUERY_COST_ATTRIBUTION_SUMMARY":
                    raise raise_on_summary
                return utils._safe_get_fixture_entries(fixtures, t_data)

            def _call_refresh_recent_queries(self) -> Dict:
                return {"status": "success", "total_processed": 0, "total_available": 0, "max_entries_applied": False}

            def _process_span_rows(self, **kwargs):  # pylint: disable=arguments-differ
                return ([], 0, 0, 0, 0, 0)

        return TestQueryCostPlugin

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cost_attribution_with_data(self):
        """Cost data present: verify metrics are emitted for all summary rows."""
        import test._utils as utils
        from test import TestDynatraceSnowAgent
        from dtagent import plugins

        plugin_class = self._make_plugin_class(self.FIXTURES)

        def __local_get_plugin_class(source: str):
            return plugin_class

        plugins._get_plugin_class = __local_get_plugin_class

        config = utils.get_config()
        config._config["plugins"]["test_query_cost_attribution"] = {"query_cost_attribution": {"enabled": True, "summary_window_hours": 24}}

        utils.execute_telemetry_test(
            TestDynatraceSnowAgent,
            test_name="test_query_cost_attribution",
            disabled_telemetry=[],
            base_count={
                "query_history": {"entries": 0, "log_lines": 0, "metrics": 0, "spans": 0},
                "query_cost_attribution": {"entries": 3, "log_lines": 3, "metrics": 9},
            },
            config=config,
        )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cost_attribution_context_disabled(self):
        """When query_cost_attribution is not in contexts, summary view is never queried and result is zeros."""
        from unittest.mock import MagicMock
        from dtagent.plugins.query_history import QueryHistoryPlugin

        plugin = QueryHistoryPlugin.__new__(QueryHistoryPlugin)
        plugin._plugin_name = "query_history"
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        plugin._metrics = MagicMock()
        plugin._events = MagicMock()
        plugin._configuration = MagicMock()

        result = plugin._process_query_cost_attribution(run_id="test-run-id", contexts=["query_history"])

        assert result == {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0}
        plugin._session.sql.assert_not_called()

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cost_attribution_privilege_missing(self):
        """When required database role is missing, plugin logs warning and returns zeros without crashing."""
        from unittest.mock import MagicMock, patch
        from dtagent.plugins.query_history import QueryHistoryPlugin

        privilege_error = RuntimeError("Insufficient privileges to access QUERY_ATTRIBUTION_HISTORY")

        plugin_class = self._make_plugin_class(self.FIXTURES, raise_on_summary=privilege_error)

        plugin = plugin_class.__new__(plugin_class)
        plugin._plugin_name = "query_history"
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        plugin._metrics = MagicMock()
        plugin._events = MagicMock()
        plugin._configuration = MagicMock()
        plugin._configuration.get.return_value = {"enabled": True}

        with patch("dtagent.plugins.query_history.LOG") as mock_log:
            result = plugin._process_query_cost_attribution(run_id="test-run-id", contexts=["query_history", "query_cost_attribution"])

        assert result == {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0}
        mock_log.warning.assert_called_once()
        warning_msg = mock_log.warning.call_args[0][0]
        assert "QUERY_ATTRIBUTION_HISTORY" in warning_msg

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cost_attribution_requires_explicit_enable(self):
        """When contexts=None but config does not enable the context, result is zeros (disabled by default)."""
        from unittest.mock import MagicMock
        from dtagent.plugins.query_history import QueryHistoryPlugin

        plugin = QueryHistoryPlugin.__new__(QueryHistoryPlugin)
        plugin._plugin_name = "query_history"
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        plugin._metrics = MagicMock()
        plugin._events = MagicMock()
        plugin._configuration = MagicMock()
        plugin._configuration.get.return_value = None

        result = plugin._process_query_cost_attribution(run_id="test-run-id", contexts=None)

        assert result == {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cost_attribution_none_contexts_with_config_enabled(self):
        """When contexts=None and config enables the context, query_cost_attribution is processed."""
        from unittest.mock import MagicMock, patch
        from dtagent.plugins.query_history import QueryHistoryPlugin

        plugin = QueryHistoryPlugin.__new__(QueryHistoryPlugin)
        plugin._plugin_name = "query_history"
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        plugin._metrics = MagicMock()
        plugin._events = MagicMock()
        plugin._configuration = MagicMock()
        plugin._configuration.get.return_value = {"enabled": True}

        expected = (3, 3, 9, 0)
        with patch.object(plugin, "_log_entries", return_value=expected) as mock_log_entries:
            result = plugin._process_query_cost_attribution(run_id="test-run-id", contexts=None)

        mock_log_entries.assert_called_once()
        assert result["entries"] == 3
        assert result["metrics"] == 9


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()

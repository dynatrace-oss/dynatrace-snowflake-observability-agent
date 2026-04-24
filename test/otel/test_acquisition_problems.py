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
"""Tests for AcquisitionProblemCollector and SQL error handling in _get_table_rows/_get_sub_rows."""

import threading
from unittest.mock import MagicMock, patch

from dtagent.otel.ingest_warnings import AcquisitionProblemCollector

##region ------------------- AcquisitionProblemCollector unit tests -----------------------


class TestAcquisitionProblemCollector:
    """Unit tests for the AcquisitionProblemCollector static-method collector."""

    def setup_method(self):
        """Reset collector before each test."""
        AcquisitionProblemCollector.reset()

    def teardown_method(self):
        """Reset collector after each test."""
        AcquisitionProblemCollector.reset()

    def test_initially_empty(self):
        """Collector starts with no problems."""
        assert not AcquisitionProblemCollector.has_problems()
        assert AcquisitionProblemCollector.get_problems() == []

    def test_add_single_problem(self):
        """A single problem is stored and retrievable."""
        AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "SQL compilation error", 0)
        assert AcquisitionProblemCollector.has_problems()
        problems = AcquisitionProblemCollector.get_problems()
        assert len(problems) == 1
        assert problems[0]["problem_type"] == "sql_error"
        assert problems[0]["source"] == "APP.V_QUERY_HISTORY"
        assert problems[0]["detail"] == "SQL compilation error"
        assert problems[0]["count"] == 0

    def test_add_multiple_problems(self):
        """Multiple problems are all stored."""
        AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "detail-a")
        AcquisitionProblemCollector.add_problem("sub_row_error", "APP.V_SPANS", "detail-b")
        AcquisitionProblemCollector.add_problem("query_timeout", "APP.V_WAREHOUSE", "detail-c")
        assert len(AcquisitionProblemCollector.get_problems()) == 3

    def test_reset_clears_problems(self):
        """Reset() clears all accumulated problems."""
        AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "detail")
        AcquisitionProblemCollector.reset()
        assert not AcquisitionProblemCollector.has_problems()
        assert AcquisitionProblemCollector.get_problems() == []

    def test_get_problems_returns_snapshot(self):
        """get_problems() returns a copy — mutating it does not affect the collector."""
        AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "detail")
        snapshot = AcquisitionProblemCollector.get_problems()
        snapshot.clear()
        assert AcquisitionProblemCollector.has_problems()

    def test_default_count_is_zero(self):
        """Count defaults to 0 when not supplied."""
        AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "detail")
        problems = AcquisitionProblemCollector.get_problems()
        assert problems[0]["count"] == 0

    def test_thread_safety(self):
        """Concurrent adds from multiple threads all land in the collector."""
        threads = []
        n_threads = 20

        def _add():
            AcquisitionProblemCollector.add_problem("sql_error", "APP.V_QUERY_HISTORY", "concurrent")

        for _ in range(n_threads):
            t = threading.Thread(target=_add)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(AcquisitionProblemCollector.get_problems()) == n_threads


##endregion

##region -------------- _get_table_rows SQL error handling tests --------------------------


class TestGetTableRowsSqlErrors:
    """Tests that _get_table_rows() catches SnowparkSQLException and records a problem."""

    def setup_method(self):
        AcquisitionProblemCollector.reset()

    def teardown_method(self):
        AcquisitionProblemCollector.reset()

    def _make_plugin_instance(self):
        """Build a minimal Plugin instance for testing _get_table_rows."""
        from dtagent.plugins import Plugin

        class _TestPlugin(Plugin):
            PLUGIN_NAME = "test_plugin"

            def process(self, run_id, run_proc=True, **kwargs):
                return {}

        plugin = _TestPlugin.__new__(_TestPlugin)
        plugin._session = MagicMock()
        plugin._plugin_name = "test_plugin"
        return plugin

    def test_clean_query_no_problem(self):
        """A successful query produces no acquisition problem."""
        from dtagent.plugins import is_select_for_table

        plugin = self._make_plugin_instance()
        mock_df = MagicMock()
        mock_row = MagicMock()
        mock_row.as_dict.return_value = {"COL": "value"}
        mock_df.to_local_iterator.return_value = iter([mock_row])
        plugin._session.table.return_value = mock_df

        rows = list(plugin._get_table_rows("APP.V_QUERY_HISTORY"))

        assert len(rows) == 1
        assert not AcquisitionProblemCollector.has_problems()

    def test_sql_exception_adds_problem(self):
        """SQL exception during table iteration adds a 'sql_error' problem."""
        from snowflake.snowpark.exceptions import SnowparkSQLException

        plugin = self._make_plugin_instance()
        exc = SnowparkSQLException("SQL compilation error: table not found")
        plugin._session.table.side_effect = exc

        rows = list(plugin._get_table_rows("APP.V_QUERY_HISTORY"))

        assert rows == []
        assert AcquisitionProblemCollector.has_problems()
        problems = AcquisitionProblemCollector.get_problems()
        assert problems[0]["problem_type"] == "sql_error"
        assert problems[0]["source"] == "APP.V_QUERY_HISTORY"
        assert "SQL compilation error" in problems[0]["detail"]

    def test_sql_exception_during_iteration_adds_problem(self):
        """SQL exception raised during row iteration (not just setup) adds a problem."""
        from snowflake.snowpark.exceptions import SnowparkSQLException

        plugin = self._make_plugin_instance()
        mock_df = MagicMock()

        def _bad_iterator():
            raise SnowparkSQLException("query execution error")
            yield  # make it a generator  # pylint: disable=unreachable

        mock_df.to_local_iterator.side_effect = _bad_iterator
        plugin._session.table.return_value = mock_df

        rows = list(plugin._get_table_rows("APP.V_DATA_VOLUME"))

        assert rows == []
        assert AcquisitionProblemCollector.has_problems()
        problems = AcquisitionProblemCollector.get_problems()
        assert problems[0]["problem_type"] == "sql_error"
        assert "query execution error" in problems[0]["detail"]


##endregion

##region -------------- _get_sub_rows SQL error handling tests ----------------------------


class TestGetSubRowsSqlErrors:
    """Tests that _get_sub_rows() catches SnowparkSQLException and records a sub_row_error."""

    def setup_method(self):
        AcquisitionProblemCollector.reset()

    def teardown_method(self):
        AcquisitionProblemCollector.reset()

    def _make_spans_instance(self):
        """Build a minimal Spans instance for testing _get_sub_rows."""
        from dtagent.otel.spans import Spans

        spans = Spans.__new__(Spans)
        return spans

    def test_clean_sub_rows_no_problem(self):
        """Successful sub-row query produces no acquisition problem."""
        spans = self._make_spans_instance()
        mock_session = MagicMock()
        mock_df = MagicMock()
        mock_row = MagicMock()
        mock_row.as_dict.return_value = {"QUERY_ID": "q1", "PARENT_QUERY_ID": "p1"}
        mock_df.to_local_iterator.return_value = iter([mock_row])
        mock_df.filter.return_value = mock_df
        mock_session.table.return_value = mock_df

        rows = list(spans._get_sub_rows(mock_session, "APP.V_SPANS", "PARENT_QUERY_ID", "p1"))

        assert len(rows) == 1
        assert not AcquisitionProblemCollector.has_problems()

    def test_sql_exception_in_sub_rows_adds_problem(self):
        """SQL exception during sub-row fetch adds a 'sub_row_error' problem."""
        from snowflake.snowpark.exceptions import SnowparkSQLException

        spans = self._make_spans_instance()
        mock_session = MagicMock()
        exc = SnowparkSQLException("table APP.V_SPANS does not exist")
        mock_session.table.side_effect = exc

        rows = list(spans._get_sub_rows(mock_session, "APP.V_SPANS", "PARENT_QUERY_ID", "p1"))

        assert rows == []
        assert AcquisitionProblemCollector.has_problems()
        problems = AcquisitionProblemCollector.get_problems()
        assert problems[0]["problem_type"] == "sub_row_error"
        assert problems[0]["source"] == "APP.V_SPANS"
        assert "does not exist" in problems[0]["detail"]


##endregion

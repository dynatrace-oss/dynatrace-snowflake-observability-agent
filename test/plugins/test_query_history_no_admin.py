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


class TestQueryHistNoAdmin:
    """Validate query_history plugin runs without error when admin-scoped objects are absent.

    This test verifies the Python code path only: APP.V_RECENT_QUERIES is the sole data
    source for query_history.py — there is no Python-level dependency on admin objects
    (P_MONITOR_WAREHOUSES or TASK_DTAGENT_QUERY_HISTORY_GRANTS). The test fixture
    (test/test_data/query_history.ndjson) is shared with the standard query_history test
    and reflects a normal run; this is intentional. Whether fewer rows appear in practice
    (because MONITOR grants were never applied without admin scope) is a live-environment
    concern confirmed separately via fixture regen on test-qa with admin scope excluded.
    """

    import pytest

    FIXTURES = {"APP.V_RECENT_QUERIES": "test/test_data/query_history.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_query_history_no_admin(self):
        import logging
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
                fixture_path = TestQueryHistNoAdmin.FIXTURES[view_name]
                print(f"Loaded fixture for {view_name} at {parent_row_id_col} = {row_id}")
                with open(fixture_path, "r", encoding="utf-8") as _fh:
                    all_rows = [_json.loads(line) for line in _fh if line.strip()]

                from dtagent.util import _adjust_timestamp

                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        class TestQueryHistoryNoAdminPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHistNoAdmin.FIXTURES, t_data, limit=3)

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryNoAdminPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

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
                test_name="test_query_history_no_admin",
                disabled_telemetry=disabled_telemetry,
                base_count={"query_history": {"entries": 3, "log_lines": 3, "metrics": 111, "spans": 3}},
            )

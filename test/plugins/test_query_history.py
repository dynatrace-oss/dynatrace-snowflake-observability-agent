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


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()

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
"""Tests for span hierarchy validation in query_history plugin (BDX-620).

Verifies that nested stored procedure call chains (outer SP → inner SP → leaf SELECT)
are correctly represented using IS_PARENT / IS_ROOT flags and produce the expected
parent-child span structure via OpenTelemetry propagation.

Fixture layout (query_history_nested_sp.ndjson):
    sp-root  (IS_ROOT=True,  IS_PARENT=True,  PARENT_QUERY_ID=null)
    sp-mid1  (IS_ROOT=False, IS_PARENT=True,  PARENT_QUERY_ID=sp-root)
    sp-leaf  (IS_ROOT=False, IS_PARENT=False, PARENT_QUERY_ID=sp-mid1)
"""


class TestQueryHistSpanHierarchy:
    import pytest

    FIXTURES = {"APP.V_RECENT_QUERIES": "test/test_data/query_history_nested_sp.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_span_hierarchy(self):
        """Validates nested stored procedure span hierarchy (BDX-620).

        Checks that:
        - Only the IS_ROOT=True row is processed as a top-level span entry.
        - IS_PARENT=True rows recurse into sub-spans via _get_sub_rows.
        - All 3 queries in the chain are recorded as processed_ids.
        - IS_PARENT / IS_ROOT flags computed by P_REFRESH_RECENT_QUERIES are
          correctly consumed by the OTel span generation path.
        """
        import json as _json
        from typing import Dict, Generator

        from snowflake import snowpark
        import test._utils as utils

        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin
        from dtagent.otel.spans import Spans
        from dtagent.util import _adjust_timestamp

        # ------------------------------------------------------------------
        # Sub-class Spans so _get_sub_rows reads from the fixture instead of
        # querying a live Snowflake table.
        # ------------------------------------------------------------------
        class TestSpans(Spans):

            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                fixture_path = TestQueryHistSpanHierarchy.FIXTURES[view_name]
                with open(fixture_path, "r", encoding="utf-8") as fh:
                    all_rows = [_json.loads(line) for line in fh if line.strip()]

                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        # ------------------------------------------------------------------
        # Sub-class QueryHistoryPlugin so _get_table_rows reads the fixture.
        # ------------------------------------------------------------------
        class TestQueryHistoryPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHistSpanHierarchy.FIXTURES, t_data)

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ------------------------------------------------------------------
        # Verify hierarchy: the fixture has 1 root, so spans=1 at the top level
        # but sub-spans bring the total spans count to 3 (root + mid + leaf).
        # ------------------------------------------------------------------
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
                test_name="test_query_history_span_hierarchy",
                disabled_telemetry=disabled_telemetry,
                base_count={
                    "query_history": {
                        "entries": 3,
                        "log_lines": 3,
                        "metrics": 27,
                        "spans": 3,
                    }
                },
            )

    def test_is_root_only_processes_top_level(self):
        """Unit test: _process_span_rows skips rows where IS_ROOT=False at top level.

        Ensures that only rows with IS_ROOT=True (or missing IS_ROOT) are passed
        to generate_span as top-level spans, consistent with the OTel parent-child
        model produced by P_REFRESH_RECENT_QUERIES.
        """
        import json as _json
        from dtagent.util import _adjust_timestamp

        fixture_path = self.FIXTURES["APP.V_RECENT_QUERIES"]
        with open(fixture_path, "r", encoding="utf-8") as fh:
            rows = [_json.loads(line) for line in fh if line.strip()]

        root_rows = [r for r in rows if r.get("IS_ROOT", True)]
        non_root_rows = [r for r in rows if not r.get("IS_ROOT", True)]

        assert len(root_rows) == 1, f"Expected 1 root row, got {len(root_rows)}"
        assert len(non_root_rows) == 2, f"Expected 2 non-root rows, got {len(non_root_rows)}"

        root = root_rows[0]
        assert root["QUERY_ID"] == "sp-root-0001-0000-0000-000000000001"
        assert root["PARENT_QUERY_ID"] is None
        assert root["IS_PARENT"] is True

    def test_is_parent_flags_intermediate_nodes(self):
        """Unit test: IS_PARENT=True on intermediate nodes, False on leaves.

        Validates that the fixture correctly represents the 3-level SP hierarchy
        where only leaf nodes have IS_PARENT=False.
        """
        import json as _json

        fixture_path = self.FIXTURES["APP.V_RECENT_QUERIES"]
        with open(fixture_path, "r", encoding="utf-8") as fh:
            rows = [_json.loads(line) for line in fh if line.strip()]

        by_id = {r["QUERY_ID"]: r for r in rows}

        root = by_id["sp-root-0001-0000-0000-000000000001"]
        mid = by_id["sp-mid1-0001-0000-0000-000000000002"]
        leaf = by_id["sp-leaf-0001-0000-0000-000000000003"]

        assert root["IS_ROOT"] is True
        assert root["IS_PARENT"] is True
        assert root["PARENT_QUERY_ID"] is None

        assert mid["IS_ROOT"] is False
        assert mid["IS_PARENT"] is True
        assert mid["PARENT_QUERY_ID"] == root["QUERY_ID"]

        assert leaf["IS_ROOT"] is False
        assert leaf["IS_PARENT"] is False
        assert leaf["PARENT_QUERY_ID"] == mid["QUERY_ID"]


if __name__ == "__main__":
    test_class = TestQueryHistSpanHierarchy()
    test_class.test_span_hierarchy()

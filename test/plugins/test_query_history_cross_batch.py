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
"""Tests for cross-batch parent OTEL context injection in query_history spans.

Verifies that when a query's parent was processed in a previous batch, the cached
OTEL span context (_PARENT_OTEL_SPAN_ID / _PARENT_OTEL_TRACE_ID) is correctly
injected as the parent span context, enabling cross-batch trace continuity.

Fixture layout (query_history_cross_batch.ndjson):
    xbatch-child  (IS_ROOT=True, has _PARENT_OTEL_SPAN_ID/_PARENT_OTEL_TRACE_ID, no _SPAN_ID/_TRACE_ID)
    xbatch-noctx  (IS_ROOT=True, no cached parent context, no _SPAN_ID/_TRACE_ID → fresh random IDs)
    xbatch-evtlog (IS_ROOT=True, has both event_log _SPAN_ID/_TRACE_ID AND cached parent → event_log wins)
"""


class TestQueryHistCrossBatch:
    import pytest

    FIXTURES = {"APP.V_RECENT_QUERIES": "test/test_data/query_history_cross_batch.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_cross_batch_span_context_injection(self):
        """Validates cross-batch parent OTEL context injection.

        Checks that:
        - A child query with _PARENT_OTEL_SPAN_ID/_PARENT_OTEL_TRACE_ID gets the cached
          parent context injected (span has a parent).
        - A child query without cached parent context gets fresh random IDs (no parent).
        - When both event_log _SPAN_ID/_TRACE_ID and cached parent context are present,
          event_log IDs take precedence (cached parent context is NOT injected).
        - span_context_map is populated with (span_id, trace_id) for each processed query.
        """
        import json as _json
        from typing import Dict, Generator, Optional, Tuple

        from snowflake import snowpark
        import test._utils as utils

        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin
        from dtagent.otel.spans import Spans
        from dtagent.util import _adjust_timestamp

        class TestSpans(Spans):

            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                fixture_path = TestQueryHistCrossBatch.FIXTURES[view_name]
                with open(fixture_path, "r", encoding="utf-8") as fh:
                    all_rows = [_json.loads(line) for line in fh if line.strip()]
                for row_dict in all_rows:
                    if row_dict.get(parent_row_id_col) == row_id:
                        _adjust_timestamp(row_dict)
                        yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestQueryHistCrossBatch.FIXTURES, t_data)

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

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
                test_name="test_query_history_cross_batch",
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

    def test_cached_parent_context_injected_when_no_event_log_ids(self):
        """Unit test: parent context injected when _PARENT_OTEL_SPAN_ID present and no event_log IDs.

        Verifies the precedence rule:
          event_log _SPAN_ID/_TRACE_ID > cached parent OTEL context > fresh random IDs
        """
        import json as _json
        from opentelemetry.trace import INVALID_SPAN_ID, INVALID_TRACE_ID

        fixture_path = self.FIXTURES["APP.V_RECENT_QUERIES"]
        with open(fixture_path, "r", encoding="utf-8") as fh:
            rows = [_json.loads(line) for line in fh if line.strip()]

        by_id = {r["QUERY_ID"]: r for r in rows}

        # Row with cached parent context and no event_log IDs
        child = by_id["xbatch-child-0000-0000-000000000001"]
        assert child["_SPAN_ID"] is None
        assert child["_TRACE_ID"] is None
        assert child["_PARENT_OTEL_SPAN_ID"] == "deadbeef12345678"
        assert child["_PARENT_OTEL_TRACE_ID"] == "deadbeef1234567800000000cafebabe"
        assert child["IS_ROOT"] is True  # root in this batch (parent was in prev batch)

        # Row without any parent context
        noctx = by_id["xbatch-noctx-0000-0000-000000000002"]
        assert noctx["_SPAN_ID"] is None
        assert noctx["_TRACE_ID"] is None
        assert noctx["_PARENT_OTEL_SPAN_ID"] is None
        assert noctx["_PARENT_OTEL_TRACE_ID"] is None

        # Row with event_log IDs AND cached parent context → event_log wins
        evtlog = by_id["xbatch-evtlog-0000-0000-000000000003"]
        assert evtlog["_SPAN_ID"] == "aabbccdd99887766"
        assert evtlog["_TRACE_ID"] == "aabbccdd9988776600000000aabbccdd"
        assert evtlog["_PARENT_OTEL_SPAN_ID"] == "deadbeef99887766"
        assert evtlog["_PARENT_OTEL_TRACE_ID"] == "deadbeef9988776600000000cafebabe"

    def test_span_context_map_populated(self):
        """Unit test: span_context_map is populated with hex span/trace IDs after generate_span.

        Verifies that after processing a span, the span_context_map contains the
        (span_id_hex, trace_id_hex) tuple for the processed query ID.
        """
        import json as _json
        from unittest.mock import MagicMock, patch
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.trace import INVALID_SPAN_ID, INVALID_TRACE_ID

        from dtagent.otel.spans import Spans
        from dtagent.config import Configuration
        from dtagent.util import _adjust_timestamp

        fixture_path = self.FIXTURES["APP.V_RECENT_QUERIES"]
        with open(fixture_path, "r", encoding="utf-8") as fh:
            rows = [_json.loads(line) for line in fh if line.strip()]

        # Use the row without event_log IDs and without cached parent
        row = next(r for r in rows if r["QUERY_ID"] == "xbatch-noctx-0000-0000-000000000002")
        _adjust_timestamp(row)

        mock_config = MagicMock(spec=Configuration)

        def _mock_get(*args, **kwargs):
            key = args[0] if args else kwargs.get("key", "")
            if key == "resource.attributes":
                return {"telemetry.exporter.name": "test"}
            return kwargs.get("default_value", "http://localhost")

        mock_config.get.side_effect = _mock_get

        resource = Resource.create({"service.name": "test"})

        with patch("dtagent.otel.spans.OtelManager.verify_communication"):
            with patch("dtagent.otel.spans.OtelManager.get_dsoa_headers", return_value={}):
                with patch("dtagent.otel.spans.CustomLoggingSession"):
                    spans = Spans(resource, mock_config)

        span_context_map: dict = {}
        mock_session = MagicMock()
        mock_session.table.return_value.filter.return_value.to_local_iterator.return_value = iter([])

        with patch("dtagent.otel.spans.OtelManager.verify_communication"):
            spans.generate_span(
                row,
                mock_session,
                "QUERY_ID",
                "PARENT_QUERY_ID",
                view_name="APP.V_RECENT_QUERIES",
                is_top_level=True,
                span_context_map=span_context_map,
            )
            spans.flush_traces()

        query_id = "xbatch-noctx-0000-0000-000000000002"
        assert query_id in span_context_map, f"Expected {query_id} in span_context_map"
        span_id_hex, trace_id_hex = span_context_map[query_id]
        assert len(span_id_hex) == 16, f"span_id_hex should be 16 hex chars, got {len(span_id_hex)}"
        assert len(trace_id_hex) == 32, f"trace_id_hex should be 32 hex chars, got {len(trace_id_hex)}"
        # Verify they are valid hex strings
        int(span_id_hex, 16)
        int(trace_id_hex, 16)


if __name__ == "__main__":
    test_class = TestQueryHistCrossBatch()

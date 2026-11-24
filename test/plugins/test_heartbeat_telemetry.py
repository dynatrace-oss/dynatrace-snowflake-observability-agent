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
from dtagent.plugins.heartbeat import _T_HEARTBEAT_EXPORTS


class TestHeartbeat:
    import pytest

    FIXTURES = {
        "call DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED()": "test/test_data/heartbeat.ndjson",
    }

    # rows of APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED(); none by default - the export statistics get their own test below
    EXPORT_ROWS: list = []

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_heartbeat(self):
        from typing import Dict, Generator
        from dtagent.plugins.heartbeat import HeartbeatPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        # ======================================================================

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestHeartbeatPlugin(HeartbeatPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                if t_data == _T_HEARTBEAT_EXPORTS:
                    yield from TestHeartbeat.EXPORT_ROWS
                    return
                # fixture rows go through the same enrichment as live rows
                for row_dict in utils._safe_get_fixture_entries(TestHeartbeat.FIXTURES, t_data, limit=2):
                    yield self._add_expected_runs(row_dict)

        def __local_get_plugin_class(source: str):
            return TestHeartbeatPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["metrics"],
            ["logs"],
            ["metrics", "logs"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_heartbeat",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={
                    "heartbeat": {"entries": 2, "log_lines": 2, "metrics": 10, "events": 0},
                    "heartbeat_exports": {"entries": 0, "log_lines": 0, "metrics": 0, "events": 0},
                },
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_heartbeat_exports(self):
        """Export statistics rows are emitted as metrics and logs of the heartbeat_exports context, next to the heartbeat rows."""
        import json
        from typing import Dict, Generator
        from dtagent.plugins.heartbeat import HeartbeatPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent

        # rows shaped like the output of APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED() (synthetic: the procedure was not run against Snowflake)
        export_rows = [
            {
                "TIMESTAMP": 1713873600000000000,
                "_MESSAGE": f"Export statistics for query_history / {signal}: delivered {delivered} of {attempted} attempted records in last 24h",
                "DIMENSIONS": json.dumps(
                    {"db.namespace": "DTAGENT_DB", "dsoa.export.plugin": "query_history", "dsoa.export.signal": signal}
                ),
                "ATTRIBUTES": json.dumps({"dsoa.heartbeat.window_hours": 24}),
                "METRICS": json.dumps({"dsoa.heartbeat.export.attempted": attempted, "dsoa.heartbeat.export.delivered": delivered}),
            }
            for signal, attempted, delivered in (("logs", 100, 98), ("metrics", 40, 40))
        ]

        class TestHeartbeatExportsPlugin(HeartbeatPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                if t_data == _T_HEARTBEAT_EXPORTS:
                    yield from export_rows

        from dtagent import plugins

        plugins._get_plugin_class = lambda source: TestHeartbeatExportsPlugin

        for disabled_telemetry in ([], ["metrics"], ["logs"], ["metrics", "logs"]):
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_heartbeat_exports",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={"heartbeat_exports": {"entries": 2, "log_lines": 2, "metrics": 4, "events": 0}},
            )

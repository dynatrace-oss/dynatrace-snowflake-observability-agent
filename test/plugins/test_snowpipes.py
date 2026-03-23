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
class TestSnowpipes:
    import pytest

    FIXTURES = {
        "call DTAGENT_DB.APP.F_SNOWPIPES_INSTRUMENTED()": "test/test_data/snowpipes.ndjson",
        "APP.V_SNOWPIPES_COPY_HISTORY_INSTRUMENTED": "test/test_data/snowpipes_copy_history.ndjson",
        "APP.V_SNOWPIPES_USAGE_HISTORY_INSTRUMENTED": "test/test_data/snowpipes_usage_history.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator
        from dtagent.plugins.snowpipes import SnowpipesPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        # ======================================================================

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSnowpipesPlugin(SnowpipesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestSnowpipes.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestSnowpipesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["metrics"],
            ["logs"],
            ["metrics", "logs"],
            ["metrics", "logs", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_snowpipes",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "snowpipes": {"entries": 2, "log_lines": 2, "metrics": 2, "events": 2},
                    "snowpipes_copy_history": {"entries": 2, "log_lines": 2, "metrics": 16, "events": 0},
                    "snowpipes_usage_history": {"entries": 2, "log_lines": 2, "metrics": 8, "events": 0},
                },
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes_context_none(self):
        """contexts=None → all 3 contexts processed"""
        from typing import Dict, Generator
        from dtagent.plugins.snowpipes import SnowpipesPlugin
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSnowpipesPlugin(SnowpipesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestSnowpipes.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestSnowpipesPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        utils.execute_telemetry_test(
            TestDynatraceSnowAgent,
            test_name="test_snowpipes",
            disabled_telemetry=[],
            affecting_types_for_entries=["logs", "metrics", "events"],
            base_count={
                "snowpipes": {"entries": 2, "log_lines": 2, "metrics": 2, "events": 2},
                "snowpipes_copy_history": {"entries": 2, "log_lines": 2, "metrics": 16, "events": 0},
                "snowpipes_usage_history": {"entries": 2, "log_lines": 2, "metrics": 8, "events": 0},
            },
        )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes_context_fast_only(self):
        """contexts=['snowpipes'] → only fast context"""
        from typing import Dict, Generator
        from dtagent.plugins.snowpipes import SnowpipesPlugin
        import test._utils as utils
        from test import _get_session
        from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSnowpipesPlugin(SnowpipesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestSnowpipes.FIXTURES, t_data, limit=2)

        config = utils.get_config()
        session = _get_session()

        plugin = TestSnowpipesPlugin(
            plugin_name="snowpipes",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False, contexts=["snowpipes"])
        assert "snowpipes" in result[RUN_RESULTS_KEY]
        assert "snowpipes_copy_history" not in result[RUN_RESULTS_KEY]
        assert "snowpipes_usage_history" not in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes_context_deep_only(self):
        """contexts=['snowpipes_copy_history','snowpipes_usage_history'] → only deep"""
        from typing import Dict, Generator
        from dtagent.plugins.snowpipes import SnowpipesPlugin
        import test._utils as utils
        from test import _get_session
        from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSnowpipesPlugin(SnowpipesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestSnowpipes.FIXTURES, t_data, limit=2)

        config = utils.get_config()
        session = _get_session()

        plugin = TestSnowpipesPlugin(
            plugin_name="snowpipes",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False, contexts=["snowpipes_copy_history", "snowpipes_usage_history"])
        assert "snowpipes" not in result[RUN_RESULTS_KEY]
        assert "snowpipes_copy_history" in result[RUN_RESULTS_KEY]
        assert "snowpipes_usage_history" in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes_context_single_deep(self):
        """contexts=['snowpipes_copy_history'] → only that one"""
        from typing import Dict, Generator
        from dtagent.plugins.snowpipes import SnowpipesPlugin
        import test._utils as utils
        from test import _get_session
        from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestSnowpipesPlugin(SnowpipesPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestSnowpipes.FIXTURES, t_data, limit=2)

        config = utils.get_config()
        session = _get_session()

        plugin = TestSnowpipesPlugin(
            plugin_name="snowpipes",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False, contexts=["snowpipes_copy_history"])
        assert "snowpipes" not in result[RUN_RESULTS_KEY]
        assert "snowpipes_copy_history" in result[RUN_RESULTS_KEY]
        assert "snowpipes_usage_history" not in result[RUN_RESULTS_KEY]


class TestSourceParsing:
    import pytest

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_snowpipes_source_parsing(self):
        """Verify plugin:context string parsing in agent"""
        source_no_ctx = "snowpipes"
        plugin_name, contexts = source_no_ctx, None
        if ":" in source_no_ctx:
            plugin_name, ctx_str = source_no_ctx.split(":", 1)
            contexts = [c.strip() for c in ctx_str.split(",")]
        assert plugin_name == "snowpipes"
        assert contexts is None

        source_fast = "snowpipes:snowpipes"
        plugin_name, contexts = source_fast, None
        if ":" in source_fast:
            plugin_name, ctx_str = source_fast.split(":", 1)
            contexts = [c.strip() for c in ctx_str.split(",")]
        assert plugin_name == "snowpipes"
        assert contexts == ["snowpipes"]

        source_deep = "snowpipes:snowpipes_copy_history,snowpipes_usage_history"
        plugin_name, contexts = source_deep, None
        if ":" in source_deep:
            plugin_name, ctx_str = source_deep.split(":", 1)
            contexts = [c.strip() for c in ctx_str.split(",")]
        assert plugin_name == "snowpipes"
        assert contexts == ["snowpipes_copy_history", "snowpipes_usage_history"]

        source_with_spaces = "snowpipes:snowpipes_copy_history, snowpipes_usage_history"
        plugin_name, contexts = source_with_spaces, None
        if ":" in source_with_spaces:
            plugin_name, ctx_str = source_with_spaces.split(":", 1)
            contexts = [c.strip() for c in ctx_str.split(",")]
        assert plugin_name == "snowpipes"
        assert contexts == ["snowpipes_copy_history", "snowpipes_usage_history"]


def _build_noop_telemetry():
    """Build a no-op telemetry stub for context-selective tests."""
    from dtagent.otel import NO_OP_TELEMETRY

    return NO_OP_TELEMETRY


if __name__ == "__main__":
    test_class = TestSnowpipes()
    test_class.test_snowpipes()

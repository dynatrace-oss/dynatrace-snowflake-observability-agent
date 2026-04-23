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
class TestTableHealth:
    import pytest

    FIXTURES = {
        "APP.V_TABLE_STORAGE": "test/test_data/table_health_storage.ndjson",
        "APP.V_TABLE_CLUSTERING": "test/test_data/table_health_clustering.ndjson",
        "APP.V_TABLE_HEALTH_DERIVED": "test/test_data/table_health_derived.ndjson",
    }

    def _make_plugin_class(self):
        """Return a TestTableHealthPlugin subclass wired to the mock fixtures."""
        from typing import Dict, Generator
        from dtagent.plugins.table_health import TableHealthPlugin
        import test._utils as utils

        fixtures = self.FIXTURES

        class TestTableHealthPlugin(TableHealthPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(fixtures, t_data, limit=2)

        return TestTableHealthPlugin

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_both_contexts(self):
        """Both table_storage and table_clustering contexts processed (clustering_enabled=True)."""
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        def __local_get_plugin_class(source: str):
            return self._make_plugin_class()

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        disabled_combinations = [
            [],
            ["metrics"],
            ["biz_events"],
            ["metrics", "biz_events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_table_health",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["metrics", "biz_events"],
                base_count={
                    "table_storage": {"entries": 2, "log_lines": 0, "metrics": 10, "events": 0},
                    "table_clustering": {"entries": 2, "log_lines": 0, "metrics": 8, "events": 0},
                },
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_derived_context(self):
        """table_health_derived context processed when history_retention_days > 0."""
        from test import _get_session
        from dtagent.context import RUN_RESULTS_KEY
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        plugin_cls = self._make_plugin_class()
        config = utils.get_config()
        config._config.setdefault("plugins", {}).setdefault("table_health", {})["history_retention_days"] = 30
        session = _get_session()

        plugin = plugin_cls(
            plugin_name="table_health",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False)
        assert "table_storage" in result[RUN_RESULTS_KEY]
        assert "table_clustering" in result[RUN_RESULTS_KEY]
        assert "table_health_derived" in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_derived_disabled_by_default(self):
        """table_health_derived context skipped when history_retention_days=0 (default)."""
        from test import _get_session
        from dtagent.context import RUN_RESULTS_KEY
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        plugin_cls = self._make_plugin_class()
        config = utils.get_config()
        session = _get_session()

        plugin = plugin_cls(
            plugin_name="table_health",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False)
        assert "table_health_derived" not in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_storage_context_only(self):
        """contexts=['table_storage'] → only storage context processed."""
        from test import _get_session
        from dtagent.context import RUN_RESULTS_KEY
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        plugin_cls = self._make_plugin_class()
        config = utils.get_config()
        session = _get_session()

        plugin = plugin_cls(
            plugin_name="table_health",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False, contexts=["table_storage"])
        assert "table_storage" in result[RUN_RESULTS_KEY]
        assert "table_clustering" not in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_clustering_context_only(self):
        """contexts=['table_clustering'] → only clustering context processed."""
        from test import _get_session
        from dtagent.context import RUN_RESULTS_KEY
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        plugin_cls = self._make_plugin_class()
        config = utils.get_config()
        session = _get_session()

        plugin = plugin_cls(
            plugin_name="table_health",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False, contexts=["table_clustering"])
        assert "table_storage" not in result[RUN_RESULTS_KEY]
        assert "table_clustering" in result[RUN_RESULTS_KEY]

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_table_health_clustering_disabled(self):
        """clustering_enabled=False → table_clustering context skipped even when contexts=None."""
        from test import _get_session
        from dtagent.context import RUN_RESULTS_KEY
        import test._utils as utils

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        plugin_cls = self._make_plugin_class()
        config = utils.get_config()
        config._config.setdefault("plugins", {}).setdefault("table_health", {})["clustering_enabled"] = False
        session = _get_session()

        plugin = plugin_cls(
            plugin_name="table_health",
            session=session,
            configuration=config,
            logs=_build_noop_telemetry(),
            spans=_build_noop_telemetry(),
            metrics=_build_noop_telemetry(),
            events=_build_noop_telemetry(),
            bizevents=_build_noop_telemetry(),
        )

        result = plugin.process("test_run_id", run_proc=False)
        assert "table_storage" in result[RUN_RESULTS_KEY]
        assert "table_clustering" not in result[RUN_RESULTS_KEY]


def _build_noop_telemetry():
    """Build a no-op telemetry stub for context-selective tests."""
    from dtagent.otel import NO_OP_TELEMETRY

    return NO_OP_TELEMETRY


if __name__ == "__main__":
    test_class = TestTableHealth()
    test_class.test_table_health_both_contexts()

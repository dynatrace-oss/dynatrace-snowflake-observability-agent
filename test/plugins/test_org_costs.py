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
class TestOrgCosts:
    import pytest

    FIXTURES = {
        "APP.V_ORG_METERING_DAILY": "test/test_data/org_costs_metering.ndjson",
        "APP.V_ORG_STORAGE_DAILY": "test/test_data/org_costs_storage.ndjson",
        "APP.V_ORG_DATA_TRANSFER_DAILY": "test/test_data/org_costs_data_transfer.ndjson",
    }

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_org_costs_metering(self):
        from dtagent.plugins.org_costs import OrgCostsPlugin
        from dtagent import plugins
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from unittest.mock import patch  # noqa: F401

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestOrgCostsPlugin(OrgCostsPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestOrgCosts.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestOrgCostsPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        disabled_combinations = [
            [],
            ["logs"],
            ["metrics"],
            ["logs", "metrics"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_org_costs",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={
                    "org_costs_metering": {"entries": 2, "log_lines": 2, "metrics": 8, "events": 0},
                    "org_costs_storage": {"entries": 2, "log_lines": 2, "metrics": 2, "events": 0},
                },
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_org_costs_storage(self):
        from dtagent.plugins.org_costs import OrgCostsPlugin
        from dtagent import plugins
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from unittest.mock import patch  # noqa: F401

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestOrgCostsPlugin(OrgCostsPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestOrgCosts.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestOrgCostsPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        disabled_combinations = [
            [],
            ["logs"],
            ["metrics"],
            ["logs", "metrics"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_org_costs",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={
                    "org_costs_metering": {"entries": 2, "log_lines": 2, "metrics": 8, "events": 0},
                    "org_costs_storage": {"entries": 2, "log_lines": 2, "metrics": 2, "events": 0},
                },
            )

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_org_costs_data_transfer(self):
        from dtagent.plugins.org_costs import OrgCostsPlugin
        from dtagent import plugins
        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from typing import Generator, Dict
        from unittest.mock import patch  # noqa: F401

        # -----------------------------------------------------

        utils._generate_all_fixtures(_get_session(), self.FIXTURES)

        class TestOrgCostsPlugin(OrgCostsPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestOrgCosts.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestOrgCostsPlugin

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["logs"],
            ["metrics"],
            ["logs", "metrics"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_org_costs",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics"],
                base_count={
                    "org_costs_data_transfer": {"entries": 2, "log_lines": 2, "metrics": 2, "events": 0},
                },
            )


if __name__ == "__main__":
    test_class = TestOrgCosts()
    test_class.test_org_costs_metering()
    test_class.test_org_costs_storage()
    test_class.test_org_costs_data_transfer()

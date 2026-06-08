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
"""Tests for the resource monitors plugin."""


class TestResMon:
    """Integration tests for ResourceMonitorsPlugin using fixture data."""

    import pytest

    T_DATA_RESMON = "APP.V_RESOURCE_MONITORS"
    T_DATA_WHS = "APP.V_WAREHOUSES"
    FIXTURES = {T_DATA_RESMON: "test/test_data/resource_monitors.ndjson", T_DATA_WHS: "test/test_data/resource_monitors_warehouses.ndjson"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_res_mon(self):
        """Run the resource monitors plugin against fixture data in all telemetry-disable combinations."""
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        import test._utils as utils
        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        # ======================================================================

        if utils.should_generate_fixtures(self.FIXTURES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RESOURCE_MONITORS", log_on_exception=True)
            utils._generate_fixture(
                session, self.T_DATA_RESMON, self.FIXTURES[self.T_DATA_RESMON], lambda df: df.sort("IS_ACCOUNT_LEVEL", ascending=False)
            )
            utils._generate_fixture(session, self.T_DATA_WHS, self.FIXTURES[self.T_DATA_WHS])

        class TestResourceMonitorsPlugin(ResourceMonitorsPlugin):
            """ResourceMonitorsPlugin subclass that reads from local fixture files."""

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_fixture_entries(TestResMon.FIXTURES, t_data, limit=2)

        def __local_get_plugin_class(source: str):
            return TestResourceMonitorsPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        disabled_combinations = [
            [],
            ["logs"],
            ["metrics"],
            ["events"],
            ["logs", "metrics"],
            ["logs", "events"],
            ["metrics", "events"],
            ["logs", "metrics", "events"],
        ]

        for disabled_telemetry in disabled_combinations:
            utils.execute_telemetry_test(
                TestDynatraceSnowAgent,
                test_name="test_resource_monitors",
                disabled_telemetry=disabled_telemetry,
                affecting_types_for_entries=["logs", "metrics", "events"],
                base_count={
                    "resource_monitors": {"entries": 2, "log_lines": 0, "metrics": 10, "events": 4},
                    "warehouses": {"entries": 2, "log_lines": 0, "metrics": 12, "events": 6},
                },
            )


class TestEscapeSqlStr:
    """Unit tests for _escape_sql_str against Snowflake quoted-identifier character space.

    Snowflake double-quoted identifiers allow virtually any character (ASCII, extended ASCII,
    Unicode, spaces, punctuation). The only character that requires escaping inside a
    single-quoted SQL string literal is the single quote itself — everything else is harmless.
    """

    import pytest

    @pytest.mark.parametrize(
        "name, expected_escaped, description",
        [
            # Unquoted identifiers — no special chars, nothing to escape
            ("MY_MONITOR", "MY_MONITOR", "plain unquoted identifier"),
            ("MONITOR_01", "MONITOR_01", "unquoted identifier with digit"),
            # Single quote — the only character that must be escaped
            ("it's", "it''s", "single quote mid-name"),
            ("Coś';tam", "Coś'';tam", "unicode + single quote + semicolon (Snowflake quoted identifier)"),
            ("' OR '1'='1", "'' OR ''1''=''1", "classic SQL injection pattern"),
            ("foo'; DROP TABLE t --", "foo''; DROP TABLE t --", "SQL injection with statement terminator"),
            ("''", "''''", "consecutive single quotes"),
            # Characters valid in Snowflake quoted identifiers that are harmless in string literals
            ('monitor"name', 'monitor"name', "double quote — harmless inside single-quoted literal"),
            ("my monitor", "my monitor", "space — valid in quoted identifier"),
            ("90%_used", "90%_used", "percent sign"),
            ("cost$center", "cost$center", "dollar sign"),
            ("monitor.sub", "monitor.sub", "period — valid in quoted identifier"),
            ("alert!high", "alert!high", "exclamation mark"),
            ("mon\\slash", "mon\\\\slash", "backslash — Snowflake treats it as escape char in string literals"),
            ("TEST\\NOT'TEST", "TEST\\\\NOT''TEST", "backslash + single quote combined"),
            # Unicode (non-ASCII) — valid in Snowflake quoted identifiers
            ("Płatności", "Płatności", "Polish unicode identifier, no quotes"),
            ("Cošta'Rica", "Cošta''Rica", "unicode with embedded single quote"),
            # Edge cases
            ("", "", "empty string"),
        ],
    )
    def test_escape_sql_str(self, name, expected_escaped, description):
        """Assert _escape_sql_str produces correct output for Snowflake identifier edge cases."""
        from dtagent.plugins.resource_monitors import _escape_sql_str

        assert _escape_sql_str(name) == expected_escaped, description

    @pytest.mark.parametrize(
        "name",
        [
            "it's",
            "Coś';tam",
            "foo'; DROP TABLE t --",
            "' OR '1'='1",
            'monitor"name',
            "my monitor",
        ],
    )
    def test_escape_sql_str_produces_safe_literal(self, name):
        """Assert that wrapping the escaped name in single quotes yields a single complete SQL token.

        A safe SQL string literal starts with ' and ends with ' with no unescaped ' inside.
        We verify this by checking the assembled literal contains an even number of single quotes
        (each internal ' is doubled to '').
        """
        from dtagent.plugins.resource_monitors import _escape_sql_str

        literal = f"'{_escape_sql_str(name)}'"
        # Strip the outer opening and closing quotes, then verify no lone quote remains
        inner = literal[1:-1]
        # After escaping, all internal quotes appear as ''. Replacing them leaves no ' behind.
        assert "'" not in inner.replace("''", ""), f"Unescaped quote in literal for name={name!r}"

    @pytest.mark.parametrize(
        "name",
        [
            "it's",
            "Coś';tam",
            "foo'; DROP TABLE t --",
            "' OR '1'='1",
            'monitor"name',
            "my monitor",
            "90%_used",
            "cost$center",
            "mon\\slash",
            "TEST\\NOT'TEST",
            "Płatności",
            "Cošta'Rica",
            "''",
        ],
    )
    def test_escape_sql_str_round_trip_live(self, name):
        """Execute SELECT with the escaped name against live Snowflake and verify round-trip equality.

        Skipped in local testing mode — Session.sql() is not supported by the Snowflake mock.
        Requires test/credentials.yml to run.
        """
        from test import _get_session, is_local_testing
        from dtagent.plugins.resource_monitors import _escape_sql_str

        if is_local_testing():
            self.pytest.skip("Session.sql not supported in local testing mode — requires live Snowflake connection")

        session = _get_session()
        literal = f"'{_escape_sql_str(name)}'"
        rows = session.sql(f"SELECT {literal} AS NAME").collect()
        assert len(rows) == 1
        assert rows[0]["NAME"] == name


class TestComputeBand:
    """Unit tests for ResourceMonitorsPlugin._compute_band — positional band mapping."""

    import pytest

    @pytest.mark.parametrize(
        "thresholds, used_pct, expected",
        [
            # Default thresholds [50, 80, 90, 100]
            ([50, 80, 90, 100], 49, None),
            ([50, 80, 90, 100], 50, "info"),
            ([50, 80, 90, 100], 79, "info"),
            ([50, 80, 90, 100], 80, "warn"),
            ([50, 80, 90, 100], 89, "warn"),
            ([50, 80, 90, 100], 90, "critical"),
            ([50, 80, 90, 100], 99, "critical"),
            ([50, 80, 90, 100], 100, "exhausted"),
            # Custom override without 100 — exhausted must still be reachable at index 3
            ([60, 75, 85, 95], 95, "exhausted"),
            ([60, 75, 85, 95], 85, "critical"),
            ([60, 75, 85, 95], 75, "warn"),
            ([60, 75, 85, 95], 60, "info"),
            ([60, 75, 85, 95], 59, None),
            # Short threshold lists — right-aligned: index 0 maps to the last N bands
            ([80], 80, "exhausted"),
            ([80], 79, None),
            ([70, 90], 90, "exhausted"),
            ([70, 90], 70, "critical"),
        ],
    )
    def test_compute_band(self, thresholds, used_pct, expected):
        """Assert that _compute_band returns the correct positional band for the given inputs."""
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        assert ResourceMonitorsPlugin._compute_band(used_pct, thresholds) == expected


if __name__ == "__main__":
    test_class = TestResMon()
    test_class.test_res_mon()

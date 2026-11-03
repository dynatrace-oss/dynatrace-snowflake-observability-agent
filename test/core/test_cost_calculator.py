#!/usr/bin/env python3
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

"""Tests for the pre-install DSOA cost estimate script generator (BIZOBS-3285)."""

import copy
import re

import pytest

from build import generate_cost_calculator as gen


@pytest.fixture(scope="module", name="model")
def _model():
    return gen.load_model()


@pytest.fixture(scope="module", name="sql")
def _sql(model):
    return gen.render_sql(model)


class TestCostCalculator:
    """The cost model must stay in sync with the plugins, and the generated script must stay read-only."""

    def test_model_matches_plugins(self, model):
        """Fails when a plugin's schedule, default scope, metric count or on/off default changed without updating cost_model.yml."""
        assert gen.validate_model(model) == []

    def test_drift_is_detected(self, model):
        """A changed schedule must be reported."""
        drifted = copy.deepcopy(model)
        drifted["plugins"]["tasks"]["expected_schedule"] = "USING CRON 0 0 * * * UTC"
        assert any("tasks: schedule" in problem for problem in gen.validate_model(drifted))

    def test_missing_plugin_is_detected(self, model):
        """A shipped plugin without a model entry must be reported."""
        drifted = copy.deepcopy(model)
        del drifted["plugins"]["users"]
        assert any("users: plugin has no entry" in problem for problem in gen.validate_model(drifted))

    def test_every_plugin_has_a_row(self, model, sql):
        """Each plugin appears in the credits table of the script."""
        for plugin in gen.discover_plugins():
            assert f"({gen._sql_str(plugin)}, '" in sql  # pylint: disable=protected-access

    def test_script_is_read_only(self, sql):
        """No DDL/DML outside string literals and comments."""
        code = re.sub(r"'(?:[^']|'')*'", "''", sql)
        code = re.sub(r"--[^\n]*", "", code)
        assert not re.search(r"\b(CREATE|ALTER|INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|GRANT|USE)\b", code, re.IGNORECASE)
        assert code.upper().count("EXECUTE IMMEDIATE") == 1

    def test_prices_only_in_rate_card(self, model, sql):
        """Re-pricing needs a single edit: prices are declared once and referenced by variable everywhere else."""
        for var in gen.RATE_VARS:
            assert len(re.findall(rf"^\s*{var} FLOAT DEFAULT", sql, re.MULTILINE)) == 1
        body = sql.split("BEGIN\n", 1)[1]
        assert not re.search(rf"\b{model['rate_card']['logs_ingest_per_gib']}\b\s*\*", body)

    def test_scripting_variables_are_bound_in_queries(self, sql):
        """Inside the final SELECT scripting variables must be bind variables (:v_org), a bare name is an invalid identifier."""
        query = re.search(r"res := \((.*)\n  \);\n  RETURN", sql, re.DOTALL).group(1)
        query = re.sub(r"'(?:[^']|'')*'", "''", query)
        query = re.sub(r"--[^\n]*", "", query)
        assert not re.findall(r"(?<![:\w.])(?:v|n|p)_[a-z_0-9]+\b", query)

    def test_permissions_are_checked_first(self, sql):
        """Every required source is probed before the first measurement, and a failure returns a short message."""
        first_measurement = sql.index(":v_tables_in_scope FROM")
        check_end = sql.index("RETURN TABLE(res_denied)")
        assert check_end < first_measurement
        for source in gen.REQUIRED_SOURCES:
            assert f"FROM {source} LIMIT 1" in sql[:check_end]
        assert "MISSING PERMISSIONS" in sql[:check_end]

    def test_all_measured_sources_are_classified(self):
        """Each source used by a measurement is either required (checked up front) or optional (n/a when unreadable)."""
        known = set(gen.REQUIRED_SOURCES) | set(gen.OPTIONAL_SOURCES)
        for item in gen.MEASUREMENTS:
            for source in re.findall(r"\b(SNOWFLAKE\.\w+\.\w+)\b", item["sql"]):
                assert source in known, f"{source} is neither in REQUIRED_SOURCES nor OPTIONAL_SOURCES"

    def test_unmeasured_inputs_are_flagged_on_plugin_rows(self, sql):
        """A plugin whose input could not be measured is marked as incomplete, so a default of 0 is not mistaken for a result."""
        assert "ESTIMATE INCOMPLETE" in sql
        assert "IFF(:n_log_rows_day <> 'measured'" in sql

    def test_null_measurements_are_reported_as_unavailable(self, sql):
        """A measurement that returns NULL must be shown as n/a, not as a measured value."""
        assert "IF (v_log_rows_day IS NULL) THEN v_log_rows_day := 0; n_log_rows_day := 'n/a, no data returned, using default'" in sql

    def test_fast_snowpipes_task_does_not_keep_the_warehouse_awake(self, model):
        """Snowpipes fast mode runs on cloud services only, so only the hourly history task counts for warehouse time."""
        entry = model["plugins"]["snowpipes"]
        assert len(gen.cron_run_minutes(entry["expected_awake_schedule"])) == 24
        assert gen.awake_seconds(["snowpipes"], model) < gen.awake_seconds(["tasks"], model) * 2

    def test_actuals_are_averaged_over_days_with_data(self, sql):
        """Actual credits and records are divided by the number of days that have data, not by the lookback window."""
        assert "COUNT(DISTINCT TO_DATE(START_TIME))" in sql
        assert "COUNT(DISTINCT TO_DATE(l.PROCESS_TIME))" in sql
        assert "'biz_events'" not in sql

    def test_header_states_assumptions(self, model, sql):
        """The output header carries the rate card date, retention, the no-config assumption and the query-cost disclaimer."""
        assert model["rate_card"]["as_of"] in sql
        assert f"retention {model['rate_card']['retention_days']} days" in sql
        assert "no config" in sql
        assert "query cost" in sql.lower()

    def test_allocated_credits_sum_to_total(self, model):
        """Allocated Snowflake credits add up to the total in every scenario."""
        for scenario in gen.snowflake_credits(model).values():
            assert sum(scenario["allocated"].values()) == pytest.approx(scenario["total"])

    def test_union_of_runs_is_cheaper_than_sum(self, model):
        """Overlapping schedules share warehouse awake time, so the total is below the sum of standalone costs."""
        scenario = gen.snowflake_credits(model)["with_org"]
        assert scenario["total"] < sum(scenario["standalone"].values())

    @pytest.mark.parametrize(
        "schedule,runs",
        [("USING CRON */30 * * * * UTC", 48), ("USING CRON 0 0,8,16 * * * UTC", 3), ("USING CRON 30 */12 * * * UTC", 2), ("USING CRON 0 0 * * * UTC", 1)],
    )
    def test_cron_runs_per_day(self, schedule, runs):
        """Cron expansion gives the number of runs per day."""
        assert len(gen.cron_run_minutes(schedule)) == runs

    def test_unsupported_cron_is_rejected(self):
        """Schedules restricted by day or weekday are not modelled."""
        with pytest.raises(ValueError):
            gen.cron_run_minutes("USING CRON 0 0 * * 1 UTC")

    def test_run_overhead_adds_warehouse_time(self, model):
        """The fitted per-run overhead is part of the awake time, so removing it lowers the estimate."""
        assert model["snowflake"]["run_overhead_seconds"] > 0
        lean = copy.deepcopy(model)
        lean["snowflake"]["run_overhead_seconds"] = 0
        assert gen.awake_seconds(["tasks"], lean) < gen.awake_seconds(["tasks"], model)

    def test_committed_script_is_up_to_date(self, sql):
        """The copy kept in the repository must equal what the generator produces, so a changed model needs a rebuild."""
        with open(gen.REPO_COPY, encoding="utf-8") as file:
            assert file.read() == sql

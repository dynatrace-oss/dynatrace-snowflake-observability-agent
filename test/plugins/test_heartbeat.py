"""Unit tests for the heartbeat plugin: expected runs calculation and row enrichment (no Snowflake connection required)."""

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
import datetime
import json
import logging

import pytest

from dtagent.plugins.heartbeat import HeartbeatPlugin, _expected_runs

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


class TestExpectedRuns:
    @pytest.mark.parametrize(
        "schedule,window_hours,expected",
        [
            ("USING CRON 0 6 * * * UTC", 24, 1),
            ("USING CRON */5 * * * * UTC", 24, 288),
            ("USING CRON 0 */12 * * * UTC", 24, 2),
            ("USING CRON 0 6 * * * UTC", 48, 2),
            ("USING CRON 0,30 * * * * UTC", 1, 2),
            ("using cron 0 6 * * * utc", 24, 1),  # prefix is case-insensitive
            ("USING CRON 0 6 * * * Europe/Warsaw", 24, 1),
            ("30 MINUTES", 24, 48),
            ("30 MINUTE", 24, 48),
            ("1 MINUTE", 24, 1440),
            ("2 HOURS", 24, 12),
        ],
    )
    def test_supported_schedules(self, schedule, window_hours, expected):
        assert _expected_runs(schedule, window_hours, NOW) == expected

    @pytest.mark.parametrize(
        "schedule",
        [None, "", "AFTER TASK_DTAGENT_BUDGETS", "USING CRON not a cron UTC", "USING CRON 0 6 * * * Not/AZone", "whenever"],
    )
    def test_unsupported_schedules(self, schedule):
        assert _expected_runs(schedule, 24, NOW) is None

    @pytest.mark.parametrize("schedule", ["0 MINUTES", "0 HOURS", "USING CRON", "USING CRON ", "USING CRON UTC", "USING CRON   "])
    def test_malformed_schedules_are_unsupported_instead_of_raising(self, schedule):
        assert _expected_runs(schedule, 24, NOW) is None

    @pytest.mark.parametrize("day", [datetime.datetime(2026, 10, 25, 12, tzinfo=UTC), datetime.datetime(2026, 3, 29, 12, tzinfo=UTC)])
    def test_hourly_cron_is_stable_across_dst_changes(self, day):
        # the window is 24 real hours, so an hourly schedule is expected 24 times even on 23h/25h local days
        assert _expected_runs("USING CRON 0 * * * * Europe/Warsaw", 24, day) == 24


def _plugin() -> HeartbeatPlugin:
    return HeartbeatPlugin.__new__(HeartbeatPlugin)  # bypass Snowflake-dependent __init__


def _row(attributes: dict, metrics: dict | None = None, as_json: bool = False) -> dict:
    return {
        "ATTRIBUTES": json.dumps(attributes) if as_json else attributes,
        "METRICS": json.dumps(metrics or {}) if as_json else (metrics or {}),
    }


class TestRowEnrichment:
    def test_expected_runs_added_for_enabled_task(self):
        row = _plugin()._add_expected_runs(
            _row(
                {
                    "dsoa.heartbeat.configured_enabled": True,
                    "dsoa.heartbeat.configured_schedule": "30 MINUTES",
                    "dsoa.heartbeat.window_hours": 24,
                }
            )
        )
        assert row["METRICS"]["dsoa.heartbeat.expected_runs"] == 48
        assert row["ATTRIBUTES"]["dsoa.heartbeat.schedule_supported"] is True

    def test_disabled_plugin_expects_no_runs(self):
        row = _plugin()._add_expected_runs(
            _row(
                {
                    "dsoa.heartbeat.configured_enabled": False,
                    "dsoa.heartbeat.configured_schedule": "30 MINUTES",
                    "dsoa.heartbeat.window_hours": 24,
                }
            )
        )
        assert row["METRICS"]["dsoa.heartbeat.expected_runs"] == 0

    def test_unsupported_schedule_is_flagged_without_expected_runs(self):
        row = _plugin()._add_expected_runs(
            _row(
                {
                    "dsoa.heartbeat.configured_enabled": True,
                    "dsoa.heartbeat.configured_schedule": "AFTER TASK_X",
                    "dsoa.heartbeat.window_hours": 24,
                }
            )
        )
        assert "dsoa.heartbeat.expected_runs" not in row["METRICS"]
        assert row["ATTRIBUTES"]["dsoa.heartbeat.schedule_supported"] is False

    def test_falls_back_to_actual_schedule_for_unconfigured_task(self):
        row = _plugin()._add_expected_runs(
            _row({"dsoa.heartbeat.actual_schedule": "USING CRON 0 6 * * * UTC", "dsoa.heartbeat.window_hours": 24})
        )
        assert row["METRICS"]["dsoa.heartbeat.expected_runs"] == 1

    def test_json_string_columns_are_handled_and_existing_metrics_kept(self):
        row = _plugin()._add_expected_runs(
            _row(
                {
                    "dsoa.heartbeat.configured_enabled": True,
                    "dsoa.heartbeat.configured_schedule": "1 MINUTE",
                    "dsoa.heartbeat.window_hours": 1,
                },
                {"dsoa.heartbeat.runs.succeeded": 7},
                as_json=True,
            )
        )
        assert row["METRICS"] == {"dsoa.heartbeat.runs.succeeded": 7, "dsoa.heartbeat.expected_runs": 60}


class TestLogLevel:
    @pytest.mark.parametrize(
        "attributes,level",
        [
            ({"dsoa.heartbeat.is_missing": True}, logging.ERROR),
            ({"dsoa.heartbeat.is_unexpected": True}, logging.WARNING),
            ({"dsoa.heartbeat.is_suspended": True}, logging.WARNING),
            ({"dsoa.heartbeat.has_schedule_drift": True}, logging.WARNING),
            ({"dsoa.heartbeat.schedule_supported": False}, logging.WARNING),
            ({"dsoa.heartbeat.schedule_supported": True}, logging.INFO),
            ({}, logging.INFO),
        ],
    )
    def test_log_level(self, attributes, level):
        assert _plugin().get_log_level({"ATTRIBUTES": attributes}) == level


class TestExportStatsReporting:
    """Export statistics stay unreported (and are replayed by the next heartbeat) unless their delivery was confirmed"""

    UNTIL = "2026-11-24T05:59:00.000000000+00:00"

    @staticmethod
    def _plugin_with_session():
        from unittest.mock import MagicMock

        plugin = _plugin()
        plugin._session = MagicMock()
        plugin._logs = MagicMock()
        return plugin

    @pytest.fixture(autouse=True)
    def _collector(self):
        from dtagent.otel.export_stats import ExportStatsCollector

        ExportStatsCollector.reset()
        yield
        ExportStatsCollector.reset()

    @staticmethod
    def _delivered(delivered: int = 3, signal: str = "logs"):
        from dtagent.otel.export_stats import ExportStatsCollector

        ExportStatsCollector.set_plugin("heartbeat", "run1")
        ExportStatsCollector.add_attempted(signal, 3)
        ExportStatsCollector.add_delivered(signal, delivered)

    def test_rows_remember_the_cutoff_they_report_until(self):
        from unittest.mock import patch
        from dtagent.plugins import Plugin
        from dtagent.plugins.heartbeat import _T_HEARTBEAT_EXPORTS

        plugin = _plugin()
        rows = [_row({"dsoa.heartbeat.export.reported_until": self.UNTIL}, as_json=True)]
        with patch.object(Plugin, "_get_table_rows", return_value=iter(rows)):
            assert list(plugin._get_table_rows(_T_HEARTBEAT_EXPORTS)) == rows
        assert plugin._export_stats_reported_until == self.UNTIL

    def test_marked_as_reported_when_delivery_is_confirmed(self):
        plugin = self._plugin_with_session()
        plugin._export_stats_reported_until = self.UNTIL
        self._delivered()

        plugin._mark_export_stats_reported("run1")

        plugin._logs.flush_logs.assert_called_once()
        statement = plugin._session.sql.call_args
        assert statement.args[0] == (
            "update DTAGENT_DB.STATUS.EXPORT_STATS set REPORTED_TS = current_timestamp() "
            "where REPORTED_TS is null and RUN_TS <= ?::timestamp_ltz"
        )
        assert statement.kwargs["params"] == [self.UNTIL]

    def test_not_marked_when_a_signal_delivered_nothing(self):
        """A failed signal leaves the rows unreported, so the next heartbeat reports them again."""
        plugin = self._plugin_with_session()
        plugin._export_stats_reported_until = self.UNTIL
        self._delivered(delivered=0)

        plugin._mark_export_stats_reported("run1")

        plugin._session.sql.assert_not_called()

    def test_not_marked_when_nothing_was_attempted(self):
        plugin = self._plugin_with_session()
        plugin._export_stats_reported_until = self.UNTIL

        plugin._mark_export_stats_reported("run1")

        plugin._session.sql.assert_not_called()

    def test_not_marked_when_nothing_was_reported(self):
        plugin = self._plugin_with_session()
        plugin._export_stats_reported_until = None
        self._delivered()

        plugin._mark_export_stats_reported("run1")

        plugin._session.sql.assert_not_called()

    def test_failure_to_mark_is_swallowed(self):
        plugin = self._plugin_with_session()
        plugin._export_stats_reported_until = self.UNTIL
        plugin._session.sql.side_effect = RuntimeError("no privileges")
        self._delivered()

        plugin._mark_export_stats_reported("run1")  # must not raise

    @pytest.mark.parametrize(
        "run_proc,entries,marked", [(True, 2, True), (False, 2, False), (True, 0, False)], ids=["reported", "no run_proc", "no rows"]
    )
    def test_process_marks_only_after_reporting_rows(self, run_proc, entries, marked):
        from unittest.mock import MagicMock

        plugin = _plugin()
        plugin._log_entries = MagicMock(return_value=(entries, entries, entries, 0))
        plugin._report_results = MagicMock(return_value={})
        plugin._mark_export_stats_reported = MagicMock()

        plugin.process("run1", run_proc=run_proc, contexts=["heartbeat_exports"])

        assert plugin._mark_export_stats_reported.called is marked

    def test_delivery_confirmed_requires_every_attempted_signal_to_deliver(self):
        from dtagent.otel.export_stats import ExportStatsCollector

        ExportStatsCollector.set_plugin("heartbeat", "run1")
        ExportStatsCollector.add_attempted("logs", 2)
        ExportStatsCollector.add_delivered("logs", 2)
        ExportStatsCollector.add_attempted("metrics", 4)
        assert ExportStatsCollector.delivery_confirmed("run1") is False
        ExportStatsCollector.add_delivered("metrics", 1)  # partially rejected: the endpoint was reachable
        assert ExportStatsCollector.delivery_confirmed("run1") is True
        assert ExportStatsCollector.delivery_confirmed("other run") is False

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

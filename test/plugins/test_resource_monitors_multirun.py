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
"""Unit tests for ResourceMonitorsPlugin threshold state machine (multi-run scenarios).

These tests exercise pure-function and stubbed-state code paths only — no Snowflake
connection or Dynatrace API calls are made.
"""


class TestPlanTransition:  # pylint: disable=too-many-public-methods
    """Tests for ResourceMonitorsPlugin._plan_transition (pure function)."""

    def _pt(self, curr_band, last_band):
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        return ResourceMonitorsPlugin._plan_transition(curr_band, last_band)

    # ------------------------------------------------------------------ #
    # No-state / below-threshold scenarios                                 #
    # ------------------------------------------------------------------ #

    def test_both_none_no_instructions(self):
        """No events emitted when below threshold on first run."""
        assert not self._pt(None, None)

    def test_none_to_info_emits_up_no_status(self):
        """First crossing into info band emits up event without ACTIVE status."""
        result = self._pt("info", None)
        assert result == [("info", "up", "")]

    def test_none_to_warn_emits_active(self):
        """First crossing into warn band emits ACTIVE up event."""
        result = self._pt("warn", None)
        assert result == [("warn", "up", "ACTIVE")]

    def test_none_to_critical_emits_active(self):
        """First crossing into critical band emits ACTIVE up event."""
        result = self._pt("critical", None)
        assert result == [("critical", "up", "ACTIVE")]

    def test_none_to_exhausted_emits_active(self):
        """Crossing into exhausted band emits ACTIVE up event."""
        result = self._pt("exhausted", None)
        assert result == [("exhausted", "up", "ACTIVE")]

    # ------------------------------------------------------------------ #
    # Stable (same band) scenarios                                         #
    # ------------------------------------------------------------------ #

    def test_info_stays_info_no_event(self):
        """Remaining in info band between runs emits no events (one-shot)."""
        assert not self._pt("info", "info")

    def test_warn_stays_warn_keepalive(self):
        """Remaining in warn band emits ACTIVE keepalive to hold Davis problem open."""
        result = self._pt("warn", "warn")
        assert result == [("warn", "up", "ACTIVE")]

    def test_critical_stays_critical_keepalive(self):
        """Remaining in critical band emits ACTIVE keepalive."""
        result = self._pt("critical", "critical")
        assert result == [("critical", "up", "ACTIVE")]

    def test_exhausted_stays_exhausted_keepalive(self):
        """Remaining in exhausted band emits ACTIVE keepalive."""
        result = self._pt("exhausted", "exhausted")
        assert result == [("exhausted", "up", "ACTIVE")]

    # ------------------------------------------------------------------ #
    # Upward transition scenarios                                          #
    # ------------------------------------------------------------------ #

    def test_info_to_warn_emits_active(self):
        """Escalation from info to warn emits ACTIVE warn event (no info close needed)."""
        result = self._pt("warn", "info")
        assert result == [("warn", "up", "ACTIVE")]

    def test_info_to_critical_emits_active(self):
        """Escalation from info to critical emits ACTIVE critical event."""
        result = self._pt("critical", "info")
        assert result == [("critical", "up", "ACTIVE")]

    def test_warn_to_critical_emits_active(self):
        """Escalation from warn to critical emits ACTIVE critical event."""
        result = self._pt("critical", "warn")
        assert result == [("critical", "up", "ACTIVE")]

    def test_critical_to_exhausted_emits_active(self):
        """Escalation from critical to exhausted emits ACTIVE exhausted event."""
        result = self._pt("exhausted", "critical")
        assert result == [("exhausted", "up", "ACTIVE")]

    # ------------------------------------------------------------------ #
    # Downward transition / recovery scenarios                             #
    # ------------------------------------------------------------------ #

    def test_warn_to_none_closes_warn(self):
        """Recovery below all thresholds closes the open warn problem."""
        result = self._pt(None, "warn")
        assert result == [("warn", "down", "CLOSED")]

    def test_critical_to_none_closes_critical(self):
        """Recovery below all thresholds closes the open critical problem."""
        result = self._pt(None, "critical")
        assert result == [("critical", "down", "CLOSED")]

    def test_exhausted_to_none_closes_exhausted(self):
        """Recovery below all thresholds closes the open exhausted problem."""
        result = self._pt(None, "exhausted")
        assert result == [("exhausted", "down", "CLOSED")]

    def test_critical_to_warn_closes_critical_opens_warn(self):
        """Drop from critical to warn: close critical AND open new warn ACTIVE."""
        result = self._pt("warn", "critical")
        assert result == [("critical", "down", "CLOSED"), ("warn", "up", "ACTIVE")]

    def test_exhausted_to_critical_closes_exhausted_opens_critical(self):
        """Drop from exhausted to critical: close exhausted AND open new critical."""
        result = self._pt("critical", "exhausted")
        assert result == [("exhausted", "down", "CLOSED"), ("critical", "up", "ACTIVE")]

    def test_exhausted_to_warn_closes_exhausted_opens_warn(self):
        """Drop from exhausted to warn: close exhausted AND open new warn."""
        result = self._pt("warn", "exhausted")
        assert result == [("exhausted", "down", "CLOSED"), ("warn", "up", "ACTIVE")]

    def test_warn_to_info_closes_warn_opens_info(self):
        """Drop from warn to info: close warn AND emit info (no status)."""
        result = self._pt("info", "warn")
        assert result == [("warn", "down", "CLOSED"), ("info", "up", "")]

    def test_critical_to_info_closes_critical_opens_info(self):
        """Drop from critical to info: close critical AND emit info (no status)."""
        result = self._pt("info", "critical")
        assert result == [("critical", "down", "CLOSED"), ("info", "up", "")]

    def test_info_to_none_no_close_needed(self):
        """Drop from info to below threshold: no CLOSED event (info has no lifecycle)."""
        assert not self._pt(None, "info")


class TestComputeBand:
    """Tests for ResourceMonitorsPlugin._compute_band (pure function)."""

    def _cb(self, used_pct, thresholds=None):
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        return ResourceMonitorsPlugin._compute_band(used_pct, thresholds or [50, 80, 90, 100])

    def test_below_info_threshold_returns_none(self):
        """Values below the lowest threshold return None."""
        assert self._cb(0) is None
        assert self._cb(49.9) is None

    def test_exactly_info_threshold(self):
        """Value exactly at info threshold returns info."""
        assert self._cb(50) == "info"

    def test_above_info_below_warn(self):
        """Value between info and warn thresholds returns info."""
        assert self._cb(79.9) == "info"

    def test_exactly_warn_threshold(self):
        """Value exactly at warn threshold returns warn."""
        assert self._cb(80) == "warn"

    def test_above_warn_below_critical(self):
        """Value between warn and critical thresholds returns warn."""
        assert self._cb(89.9) == "warn"

    def test_exactly_critical_threshold(self):
        """Value exactly at critical threshold returns critical."""
        assert self._cb(90) == "critical"

    def test_above_critical_below_exhausted(self):
        """Value between critical and exhausted thresholds returns critical."""
        assert self._cb(99.9) == "critical"

    def test_exactly_exhausted_threshold(self):
        """Value exactly at exhausted threshold (100%) returns exhausted."""
        assert self._cb(100) == "exhausted"

    def test_above_exhausted(self):
        """Value above 100% still returns exhausted."""
        assert self._cb(110) == "exhausted"

    def test_custom_two_band_thresholds(self):
        """Custom threshold list with only 2 bands."""
        assert self._cb(89, [90, 100]) is None
        assert self._cb(90, [90, 100]) == "critical"
        assert self._cb(100, [90, 100]) == "exhausted"


class TestResolveThresholds:
    """Tests for ResourceMonitorsPlugin._resolve_thresholds_for."""

    def _make_plugin(self):
        """Create a minimal plugin instance with mocked configuration."""
        from unittest.mock import MagicMock
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        mock_session = MagicMock()
        mock_conf = MagicMock()
        mock_conf.get.return_value = {}

        plugin = ResourceMonitorsPlugin.__new__(ResourceMonitorsPlugin)
        plugin._plugin_name = "resource_monitors"
        plugin._session = mock_session
        plugin._configuration = mock_conf
        plugin._davis_events = None
        return plugin

    def test_no_override_returns_defaults(self):
        """No override entry → global defaults returned unchanged."""
        plugin = self._make_plugin()
        defaults = [50, 80, 90, 100]
        result = plugin._resolve_thresholds_for("MY_MONITOR", defaults, {})
        assert result == defaults

    def test_valid_override_returned(self):
        """Valid per-monitor override is returned instead of defaults."""
        plugin = self._make_plugin()
        defaults = [50, 80, 90, 100]
        overrides = {"MY_MONITOR": [70, 85, 95, 100]}
        result = plugin._resolve_thresholds_for("MY_MONITOR", defaults, overrides)
        assert result == [70, 85, 95, 100]

    def test_invalid_override_falls_back_to_defaults(self):
        """Non-monotonic override is rejected; defaults returned."""
        plugin = self._make_plugin()
        defaults = [50, 80, 90, 100]
        # Non-monotonic override.
        overrides = {"MY_MONITOR": [80, 70, 90]}
        result = plugin._resolve_thresholds_for("MY_MONITOR", defaults, overrides)
        assert result == defaults

    def test_empty_override_falls_back_to_defaults(self):
        """Empty override list is rejected; defaults returned."""
        plugin = self._make_plugin()
        defaults = [50, 80, 90, 100]
        overrides = {"MY_MONITOR": []}
        result = plugin._resolve_thresholds_for("MY_MONITOR", defaults, overrides)
        assert result == defaults


class TestProcessThresholdForRM:
    """Integration-style tests for _process_threshold_for_rm with stubbed state I/O."""

    def _make_plugin(self, threshold_config=None):
        """Create plugin with mocked session + configuration."""
        from unittest.mock import MagicMock
        from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin

        mock_session = MagicMock()
        mock_conf = MagicMock()
        mock_conf.get.return_value = threshold_config or {}

        plugin = ResourceMonitorsPlugin.__new__(ResourceMonitorsPlugin)
        plugin._plugin_name = "resource_monitors"
        plugin._session = mock_session
        plugin._configuration = mock_conf
        plugin._davis_events = None
        return plugin

    def _make_rm_row(self, monitor_name, used_pct, quota=1000, is_active=True, is_account=False):
        """Build a synthetic resource monitor row dict matching V_RESOURCE_MONITORS shape."""
        import json

        level = "ACCOUNT" if is_account else "WAREHOUSE"
        return {
            "IS_ACTIVE": is_active,
            "IS_ACCOUNT_LEVEL": is_account,
            "DIMENSIONS": json.dumps({"snowflake.resource_monitor.name": monitor_name}),
            "ATTRIBUTES": json.dumps(
                {
                    "snowflake.resource_monitor.level": level,
                    "snowflake.resource_monitor.frequency": "MONTHLY",
                    "snowflake.resource_monitor.is_active": is_active,
                }
            ),
            "METRICS": json.dumps(
                {
                    "snowflake.credits.quota": str(quota),
                    "snowflake.credits.quota.used": str(round(quota * used_pct / 100, 2)),
                    "snowflake.credits.quota.remaining": str(round(quota * (100 - used_pct) / 100, 2)),
                    "snowflake.credits.quota.used_pct": used_pct,
                    "snowflake.resource_monitor.warehouses": 1,
                }
            ),
            "EVENT_TIMESTAMPS": "{}",
        }

    def test_below_threshold_no_events(self):
        """used_pct below lowest threshold → no Davis events emitted."""
        plugin = self._make_plugin()
        row = self._make_rm_row("MY_RM", used_pct=30)

        emitted_events = []

        def stub_emit(*args, **kwargs):  # pylint: disable=unused-argument
            emitted_events.append(args)
            return 1

        plugin._report_threshold_davis_event = stub_emit

        evts, new_band, mon_name = plugin._process_threshold_for_rm(row, [50, 80, 90, 100], {}, {"MY_RM": None}, {})
        assert evts == 0
        assert new_band is None
        assert mon_name == "MY_RM"
        assert not emitted_events

    def test_first_crossing_warn_emits_active(self):
        """First time used_pct crosses warn threshold → ACTIVE event emitted."""
        plugin = self._make_plugin()
        row = self._make_rm_row("MY_RM", used_pct=85)

        emitted_events = []

        def stub_emit(
            monitor_name, band, direction, status, used_pct, rm_level, thresholds, context
        ):  # pylint: disable=too-many-arguments,unused-argument
            emitted_events.append((band, direction, status))
            return 1

        plugin._report_threshold_davis_event = stub_emit
        plugin._write_band_state = lambda *a, **kw: None

        evts, new_band, _mon_name = plugin._process_threshold_for_rm(row, [50, 80, 90, 100], {}, {"MY_RM": None}, {})
        assert evts == 1
        assert new_band == "warn"
        assert emitted_events == [("warn", "up", "ACTIVE")]

    def test_inactive_monitor_skipped(self):
        """Inactive resource monitor produces no threshold events."""
        plugin = self._make_plugin()
        row = self._make_rm_row("MY_RM", used_pct=95, is_active=False)

        plugin._report_threshold_davis_event = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called"))

        evts, new_band, mon_name = plugin._process_threshold_for_rm(row, [50, 80, 90, 100], {}, {}, {})
        assert evts == 0
        assert new_band is None
        assert mon_name == "MY_RM"

    def test_zero_quota_monitor_skipped(self):
        """Monitor with zero quota produces no threshold events."""
        plugin = self._make_plugin()
        row = self._make_rm_row("MY_RM", used_pct=100, quota=0)

        plugin._report_threshold_davis_event = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called"))

        evts, _new_band, _mon = plugin._process_threshold_for_rm(row, [50, 80, 90, 100], {}, {}, {})
        assert evts == 0

    def test_recovery_emits_closed(self):
        """Drop from warn to below threshold emits CLOSED event."""
        plugin = self._make_plugin()
        row = self._make_rm_row("MY_RM", used_pct=30)

        emitted_events = []

        def stub_emit(
            monitor_name, band, direction, status, used_pct, rm_level, thresholds, context
        ):  # pylint: disable=too-many-arguments,unused-argument
            emitted_events.append((band, direction, status))
            return 1

        plugin._report_threshold_davis_event = stub_emit
        plugin._write_band_state = lambda *a, **kw: None

        evts, new_band, _mon = plugin._process_threshold_for_rm(row, [50, 80, 90, 100], {}, {"MY_RM": "warn"}, {})
        assert evts == 1
        assert new_band is None
        assert emitted_events == [("warn", "down", "CLOSED")]


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])

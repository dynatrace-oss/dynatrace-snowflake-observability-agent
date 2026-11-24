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
"""Tests for ExportStatsCollector: attempted / delivered record counting per plugin and signal."""

import threading

from dtagent.otel.export_stats import ExportStatsCollector, UNKNOWN_PLUGIN


class TestExportStatsCollector:
    """Unit tests for the ExportStatsCollector static-method collector."""

    def setup_method(self):
        """Resets the collector before each test."""
        ExportStatsCollector.reset()

    def teardown_method(self):
        """Resets the collector after each test."""
        ExportStatsCollector.reset()

    def test_empty(self):
        """Test empty."""
        assert ExportStatsCollector.get_stats() == []

    def test_unknown_plugin_by_default(self):
        """Test unknown plugin by default."""
        ExportStatsCollector.add_attempted("logs", 3)
        assert ExportStatsCollector.get_stats() == [
            {"plugin": UNKNOWN_PLUGIN, "run_id": None, "signal": "logs", "attempted": 3, "delivered": 0}
        ]

    def test_attempted_and_delivered_share_a_row(self):
        """Test attempted and delivered share a row."""
        ExportStatsCollector.set_plugin("query_history")
        ExportStatsCollector.add_attempted("metrics", 10)
        ExportStatsCollector.add_delivered("metrics", 8)
        assert ExportStatsCollector.get_stats() == [
            {"plugin": "query_history", "run_id": None, "signal": "metrics", "attempted": 10, "delivered": 8}
        ]

    def test_counts_accumulate(self):
        """Test counts accumulate."""
        ExportStatsCollector.set_plugin("p")
        for _ in range(3):
            ExportStatsCollector.add_attempted("logs", 2)
            ExportStatsCollector.add_delivered("logs", 2)
        assert ExportStatsCollector.get_stats()[0]["attempted"] == 6
        assert ExportStatsCollector.get_stats()[0]["delivered"] == 6

    def test_attribution_follows_set_plugin(self):
        """Test attribution follows set plugin."""
        ExportStatsCollector.set_plugin("a")
        ExportStatsCollector.add_attempted("logs", 1)
        ExportStatsCollector.set_plugin("b")
        ExportStatsCollector.add_attempted("logs", 5)
        ExportStatsCollector.add_attempted("spans", 7)
        assert ExportStatsCollector.get_stats() == [
            {"plugin": "a", "run_id": None, "signal": "logs", "attempted": 1, "delivered": 0},
            {"plugin": "b", "run_id": None, "signal": "logs", "attempted": 5, "delivered": 0},
            {"plugin": "b", "run_id": None, "signal": "spans", "attempted": 7, "delivered": 0},
        ]

    def test_run_id_separates_executions_of_the_same_plugin(self):
        """Run id separates executions of the same plugin."""
        ExportStatsCollector.set_plugin("p", "run1")
        ExportStatsCollector.add_attempted("logs", 1)
        ExportStatsCollector.set_plugin("p", "run2")
        ExportStatsCollector.add_attempted("logs", 2)
        assert [(r["run_id"], r["attempted"]) for r in ExportStatsCollector.get_stats()] == [("run1", 1), ("run2", 2)]

    def test_empty_plugin_name_falls_back_to_unknown(self):
        """Test empty plugin name falls back to unknown."""
        ExportStatsCollector.set_plugin("")
        ExportStatsCollector.add_attempted("logs", 1)
        assert ExportStatsCollector.get_stats()[0]["plugin"] == UNKNOWN_PLUGIN

    def test_non_positive_counts_are_ignored(self):
        """Test non positive counts are ignored."""
        ExportStatsCollector.add_attempted("logs", 0)
        ExportStatsCollector.add_attempted("logs", -4)
        ExportStatsCollector.add_delivered("logs", 0)
        assert ExportStatsCollector.get_stats() == []

    def test_snapshot_is_a_copy(self):
        """Test snapshot is a copy."""
        ExportStatsCollector.add_attempted("logs", 1)
        ExportStatsCollector.get_stats()[0]["attempted"] = 99
        assert ExportStatsCollector.get_stats()[0]["attempted"] == 1

    def test_reset_clears_counts_and_plugin(self):
        """Test reset clears counts and plugin."""
        ExportStatsCollector.set_plugin("p")
        ExportStatsCollector.add_attempted("logs", 1)
        ExportStatsCollector.reset()
        ExportStatsCollector.add_attempted("logs", 1)
        assert ExportStatsCollector.get_stats() == [
            {"plugin": UNKNOWN_PLUGIN, "run_id": None, "signal": "logs", "attempted": 1, "delivered": 0}
        ]

    def test_thread_safety(self):
        """Test thread safety."""
        ExportStatsCollector.set_plugin("p")

        def worker():
            for _ in range(500):
                ExportStatsCollector.add_attempted("logs", 1)
                ExportStatsCollector.add_delivered("logs", 1)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert ExportStatsCollector.get_stats() == [{"plugin": "p", "run_id": None, "signal": "logs", "attempted": 4000, "delivered": 4000}]

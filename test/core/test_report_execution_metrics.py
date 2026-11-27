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

"""Regression test: the peak-RSS metric emitted by ``Plugin._report_execution`` must match its semantic definition."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from dtagent.plugins import Plugin

INSTRUMENTS_DEF = Path("src/dtagent.conf/instruments-def.yml")


class _DummyPlugin(Plugin):
    """Minimal concrete plugin, only needed to instantiate the abstract base class."""

    def process(self, run_id, run_proc=True, contexts=None):
        return {}


def test_report_execution_emits_peak_rss_metric_defined_in_semantics():
    """Checks that regular mode emits the peak RSS value under a key declared in instruments-def.yml."""
    session = MagicMock()
    session.session_id = 123  # any id other than 1 means regular mode
    metrics = MagicMock(NOT_ENABLED=False)
    plugin = _DummyPlugin(plugin_name="dummy", session=session, logs=MagicMock(), metrics=metrics, configuration=MagicMock())

    with patch("dtagent.plugins._get_peak_memory_mb", return_value=42.5):
        plugin._report_execution("dummy_source", "2026-01-01", None, {}, run_id="run-1")

    metrics.report_via_metrics_api.assert_called_once()
    emitted = metrics.report_via_metrics_api.call_args.args[0]["METRICS"]
    assert list(emitted.values()) == [42.5]

    defined = yaml.safe_load(INSTRUMENTS_DEF.read_text(encoding="utf-8"))["metrics"]
    assert set(emitted) <= set(defined)
    metrics.flush_metrics.assert_called_once()

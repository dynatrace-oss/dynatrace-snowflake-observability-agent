"""Tests that the plugin base class tracks the minimum timestamp across all contexts of one execution."""

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
from unittest.mock import MagicMock

from dtagent.plugins import Plugin


class _TestPlugin(Plugin):
    """Minimal concrete plugin"""

    def process(self, run_id, run_proc=True, contexts=None):  # pylint: disable=missing-function-docstring
        return {}


def _plugin() -> Plugin:
    plugin = _TestPlugin.__new__(_TestPlugin)  # bypass Snowflake-dependent __init__
    plugin.processed_last_timestamp = None
    plugin.processed_min_timestamp = None
    plugin._gc_interval = 0  # pylint: disable=protected-access
    plugin._log_batch_flush_size = 0  # pylint: disable=protected-access
    plugin._span_batch_flush_size = 0  # pylint: disable=protected-access
    plugin._plugin_name = "test"  # pylint: disable=protected-access
    plugin._configuration = MagicMock()  # pylint: disable=protected-access
    plugin._configuration.get_last_measurement_update.return_value = 0  # pylint: disable=protected-access
    plugin._metrics = MagicMock(NOT_ENABLED=True)  # pylint: disable=protected-access
    plugin._logs = MagicMock()  # pylint: disable=protected-access
    plugin._events = MagicMock(NOT_ENABLED=True)  # pylint: disable=protected-access
    plugin._session = MagicMock()  # pylint: disable=protected-access
    plugin.report_log = MagicMock(return_value=True)
    plugin.get_log_level = MagicMock(return_value=20)
    plugin._report_execution = MagicMock()  # pylint: disable=protected-access
    return plugin


class TestMinTimestampAcrossContexts:
    def test_minimum_survives_later_and_empty_contexts(self):
        plugin = _plugin()

        plugin._log_entries(
            lambda: iter([{"TIMESTAMP": 100}, {"TIMESTAMP": 300}]), "first", run_uuid="r", log_completion=False
        )  # pylint: disable=W0212
        plugin._log_entries(
            lambda: iter([{"TIMESTAMP": 200}]), "second", run_uuid="r", log_completion=False
        )  # pylint: disable=protected-access
        plugin._log_entries(lambda: iter([]), "empty_last", run_uuid="r", log_completion=False)  # pylint: disable=protected-access

        assert plugin.processed_min_timestamp == 100

    def test_minimum_is_cleared_once_reported(self):
        plugin = _plugin()
        plugin._report_execution = Plugin._report_execution.__get__(plugin)  # pylint: disable=protected-access
        plugin._logs = MagicMock()  # pylint: disable=protected-access
        plugin._log_entries(
            lambda: iter([{"TIMESTAMP": 100}]), "first", run_uuid="r", log_completion=False
        )  # pylint: disable=protected-access

        plugin._report_execution("first", "100", None, {}, run_id="r")  # pylint: disable=protected-access

        assert plugin._logs.send_log.call_args.kwargs["extra"]["dsoa.run.first_timestamp"] == "100"  # pylint: disable=protected-access
        assert plugin.processed_min_timestamp is None

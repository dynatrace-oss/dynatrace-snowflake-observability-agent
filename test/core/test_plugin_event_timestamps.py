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

"""Tests ensuring plugins that declare non-empty EVENT_TIMESTAMPS in SQL allow 'events' telemetry.

The ``_log_entries`` base method processes EVENT_TIMESTAMPS by calling
``self._events.report_via_api()``.  When a plugin's telemetry list does not
include ``events``, ``self._events`` is set to ``NO_OP_TELEMETRY`` and all
timestamp events are silently dropped.  This test guards against that
misconfiguration by inspecting the SQL source files directly.
"""

import glob
import re
from pathlib import Path

import yaml

PLUGINS_BASE = Path("src/dtagent/plugins")
PLUGINS_CONFIG_GLOB = str(PLUGINS_BASE / "*.config")
PLUGINS_SQL_GLOB = str(PLUGINS_BASE / "*.sql")

# Matches the OBJECT_CONSTRUCT block that is aliased as EVENT_TIMESTAMPS.
# We capture the body between the opening parenthesis and the closing paren
# followed by "as EVENT_TIMESTAMPS".  A body that contains only whitespace
# (i.e. an empty OBJECT_CONSTRUCT) means no timestamps are emitted.
_EVENT_TIMESTAMPS_RE = re.compile(
    r"OBJECT_CONSTRUCT\s*\(([^)]*)\)\s+as\s+EVENT_TIMESTAMPS",
    re.IGNORECASE | re.DOTALL,
)


def _get_plugin_names() -> list:
    """Return all plugin names discovered from *.config directories.

    Returns:
        list: Sorted list of plugin name strings.
    """
    dirs = glob.glob(PLUGINS_CONFIG_GLOB)
    return sorted(Path(d).stem.removesuffix(".config") for d in dirs)


def _load_telemetry(plugin_name: str) -> list:
    """Load the telemetry list from a plugin's YAML config file.

    Args:
        plugin_name (str): Plugin name (e.g. ``data_volume``).

    Returns:
        list: Telemetry channel names declared for this plugin, or an empty
              list when the key is absent.
    """
    config_path = PLUGINS_BASE / f"{plugin_name}.config" / f"{plugin_name}-config.yml"
    if not config_path.exists():
        return []
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("plugins", {}).get(plugin_name, {}).get("telemetry", [])


def _has_non_empty_event_timestamps(plugin_name: str) -> tuple:
    """Scan all SQL files for a plugin and return whether any declare non-empty EVENT_TIMESTAMPS.

    An EVENT_TIMESTAMPS column is considered non-empty when the OBJECT_CONSTRUCT
    call that produces it contains at least one non-whitespace character (i.e. at
    least one key–value pair).  Empty ``OBJECT_CONSTRUCT()`` declarations are
    intentionally ignored because they produce no events at runtime.

    Args:
        plugin_name (str): Plugin name (e.g. ``data_volume``).

    Returns:
        tuple: ``(has_timestamps: bool, offending_files: list[str])`` where
               ``offending_files`` lists the SQL file paths that contain non-empty
               EVENT_TIMESTAMPS declarations.
    """
    sql_dir = PLUGINS_BASE / f"{plugin_name}.sql"
    if not sql_dir.is_dir():
        return False, []

    offending = []
    for sql_file in sorted(sql_dir.glob("*.sql")):
        content = sql_file.read_text(encoding="utf-8")
        for match in _EVENT_TIMESTAMPS_RE.finditer(content):
            body = match.group(1)
            if body.strip():  # non-empty OBJECT_CONSTRUCT
                offending.append(str(sql_file))
                break  # one hit per file is enough

    return bool(offending), offending


class TestPluginEventTimestamps:
    """Ensure plugins with non-empty EVENT_TIMESTAMPS declare 'events' in their telemetry config."""

    def test_event_timestamps_require_events_telemetry(self):
        """Plugins whose SQL declares non-empty EVENT_TIMESTAMPS must allow 'events' telemetry.

        When a plugin's SQL view returns a non-empty OBJECT_CONSTRUCT as
        EVENT_TIMESTAMPS, the ``_log_entries`` base method will attempt to send
        those timestamps via ``self._events.report_via_api()``.  If the plugin
        does not list ``events`` in its telemetry config, ``self._events`` is
        substituted with ``NO_OP_TELEMETRY`` and the events are silently
        discarded — a data-loss bug that is hard to detect at runtime.

        This test scans every plugin's SQL sources and fails if any plugin with
        a non-empty EVENT_TIMESTAMPS column is missing ``events`` from its
        telemetry declaration.
        """
        violations = []
        for plugin_name in _get_plugin_names():
            has_ts, offending_files = _has_non_empty_event_timestamps(plugin_name)
            if not has_ts:
                continue
            telemetry = _load_telemetry(plugin_name)
            if "events" not in telemetry:
                violations.append(
                    f"  Plugin '{plugin_name}' has non-empty EVENT_TIMESTAMPS in:\n"
                    + "\n".join(f"    - {f}" for f in offending_files)
                    + f"\n  but 'events' is NOT listed in its telemetry config "
                    f"({plugin_name}-config.yml). "
                    f"Current telemetry: {telemetry}"
                )

        assert not violations, (
            "The following plugins declare non-empty EVENT_TIMESTAMPS but do not allow 'events' telemetry.\n"
            "This means timestamp events are silently dropped at runtime.\n"
            "Fix: add 'events' to the telemetry list in the plugin's *-config.yml.\n\n" + "\n\n".join(violations)
        )

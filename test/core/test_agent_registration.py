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

"""Tests ensuring all plugins are properly registered in the agent SQL call template."""

import re
import glob

AGENT_SQL_PATH = "src/dtagent.sql/agents/700_dtagent.sql"
PLUGINS_CONFIG_GLOB = "src/dtagent/plugins/*.config"

# Regex to locate the commented-out manual-call block /* ... */ at the end of the file.
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# Regex to extract the plugin name from each individual per-plugin call, e.g.:
#   call APP.DTAGENT(ARRAY_CONSTRUCT('shares'));
_SINGLE_CALL_RE = re.compile(r"call\s+APP\.DTAGENT\s*\(\s*ARRAY_CONSTRUCT\s*\(\s*'([^']+)'\s*\)\s*\)", re.IGNORECASE)


def _get_registered_plugins_from_sql() -> set:
    """Parse the commented-out per-plugin CALL statements in 700_dtagent.sql and return the set of plugin names.

    The manual-call comment block contains one ``call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'))``
    statement per plugin. This function extracts the plugin name from each such statement.

    Returns:
        set: Plugin names listed in the per-plugin call statements inside the manual-call comment block.

    Raises:
        AssertionError: If the comment block or no plugin calls can be found in the file.
    """
    with open(AGENT_SQL_PATH, encoding="utf-8") as fh:
        content = fh.read()

    comment_match = _COMMENT_BLOCK_RE.search(content)
    assert comment_match, (
        f"Could not find a /* ... */ comment block in {AGENT_SQL_PATH}. " "Ensure the manual-call comment block is present."
    )

    comment_block = comment_match.group(0)
    plugins = _SINGLE_CALL_RE.findall(comment_block)
    assert plugins, (
        f"Could not find any per-plugin CALL statements in the comment block of {AGENT_SQL_PATH}. "
        "Expected lines like: call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'));"
    )

    return set(plugins)


def _get_known_plugins_from_config() -> set:
    """Discover all plugins by listing *.config directories under src/dtagent/plugins/.

    Returns:
        set: Plugin names derived from *.config directory names (e.g. 'snowpipes' from 'snowpipes.config').
    """
    dirs = glob.glob(PLUGINS_CONFIG_GLOB)
    return {d.split("/")[-1].removesuffix(".config") for d in dirs}


class TestAgentRegistration:
    """Verify that the agent SQL call template stays in sync with the deployed plugin set."""

    def test_all_plugins_listed_in_agent_sql(self):
        """Every plugin with a .config directory must appear as a separate per-plugin CALL in 700_dtagent.sql.

        The manual-call comment block must have one ``call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>'))``
        line per plugin. This guards against the common mistake of adding a new plugin but forgetting
        to register it in the agent call template.
        """
        known_plugins = _get_known_plugins_from_config()
        registered_plugins = _get_registered_plugins_from_sql()

        missing_from_sql = known_plugins - registered_plugins
        extra_in_sql = registered_plugins - known_plugins

        assert not missing_from_sql, (
            f"The following plugins have a .config directory but are NOT listed in {AGENT_SQL_PATH}:\n"
            f"  {sorted(missing_from_sql)}\n"
            f"Add a call APP.DTAGENT(ARRAY_CONSTRUCT('<plugin>')) line to the manual-call comment block."
        )

        assert not extra_in_sql, (
            f"The following plugin names appear in {AGENT_SQL_PATH} but have NO .config directory:\n"
            f"  {sorted(extra_in_sql)}\n"
            f"Either create the missing .config directory or remove the stale entry."
        )

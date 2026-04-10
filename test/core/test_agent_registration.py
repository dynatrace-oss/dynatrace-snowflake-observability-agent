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

# Regex to extract the ARRAY_CONSTRUCT block inside the commented call template.
# Matches quoted string tokens inside ARRAY_CONSTRUCT(...) in the /* ... */ comment block.
_ARRAY_CONSTRUCT_RE = re.compile(
    r"/\*.*?ARRAY_CONSTRUCT\s*\((.*?)\)\s*\)\s*;",
    re.DOTALL,
)
_PLUGIN_TOKEN_RE = re.compile(r"'([^']+)'")


def _get_registered_plugins_from_sql() -> set:
    """Parse the commented-out ARRAY_CONSTRUCT call in 700_dtagent.sql and return the set of plugin names.

    Returns:
        set: Plugin names listed inside ARRAY_CONSTRUCT in the manual-call comment block.

    Raises:
        AssertionError: If the ARRAY_CONSTRUCT block cannot be found in the file.
    """
    with open(AGENT_SQL_PATH, encoding="utf-8") as fh:
        content = fh.read()

    match = _ARRAY_CONSTRUCT_RE.search(content)
    assert match, (
        f"Could not find ARRAY_CONSTRUCT block in {AGENT_SQL_PATH}. "
        "Ensure the manual-call comment block is present."
    )

    tokens = _PLUGIN_TOKEN_RE.findall(match.group(1))
    return set(tokens)


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
        """Every plugin with a .config directory must appear in the ARRAY_CONSTRUCT block
        of the manual-call comment in 700_dtagent.sql.

        This guards against the common mistake of adding a new plugin but forgetting to
        register it in the agent call template — the pattern that caused `snowpipes` to
        be missed on first deploy.
        """
        known_plugins = _get_known_plugins_from_config()
        registered_plugins = _get_registered_plugins_from_sql()

        missing_from_sql = known_plugins - registered_plugins
        extra_in_sql = registered_plugins - known_plugins

        assert not missing_from_sql, (
            f"The following plugins have a .config directory but are NOT listed in {AGENT_SQL_PATH}:\n"
            f"  {sorted(missing_from_sql)}\n"
            f"Add them to the ARRAY_CONSTRUCT block in the commented call template."
        )

        assert not extra_in_sql, (
            f"The following plugin names appear in {AGENT_SQL_PATH} but have NO .config directory:\n"
            f"  {sorted(extra_in_sql)}\n"
            f"Either create the missing .config directory or remove the stale entry."
        )

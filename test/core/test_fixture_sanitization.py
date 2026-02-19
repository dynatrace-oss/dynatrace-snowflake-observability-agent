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
"""Guard tests: validate NDJSON fixture files.

Covers:
- Every line in every ``.ndjson`` fixture is valid JSON (no ``NaN``, no bare ``Infinity``).
- Fixture file names follow the ``{plugin_name}[_{view_suffix}].ndjson`` convention.
- No ``.pkl`` binary fixture files are committed to the repository.
"""

import json
import os

import pytest

FIXTURE_DIR = "test/test_data"
PLUGINS_DIR = "src/dtagent/plugins"


def _discover_fixture_prefixes() -> set:
    """Auto-discover valid fixture name prefixes from the plugins directory.

    Each ``.py`` file in the plugins directory (excluding ``__init__.py`` and
    private modules) defines a plugin whose name is a valid fixture prefix.
    Plugins whose names end in ``s`` also contribute the singular form as a
    valid prefix (e.g. ``dynamic_tables`` → ``dynamic_table``) because some
    views within a plugin use the singular noun.

    Returns:
        Set of valid fixture-name prefix strings.
    """
    prefixes = set()
    for fname in os.listdir(PLUGINS_DIR):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        plugin_name = fname[:-3]  # strip .py
        prefixes.add(plugin_name)
        # Add singular form so fixtures like dynamic_table_refresh_history.ndjson
        # are accepted even though the plugin is called dynamic_tables.
        if plugin_name.endswith("s"):
            prefixes.add(plugin_name[:-1])
    return prefixes


# Valid plugin name prefixes — auto-discovered at import time so the list
# never needs to be manually maintained when plugins are added or removed.
VALID_FIXTURE_PREFIXES = _discover_fixture_prefixes()

# Internal files that are not fixture data — excluded from naming checks.
_NON_FIXTURE_FILES = {"_deny_patterns.json", "telemetry_structured.json", "telemetry_unstructured.json"}


##region Fixture enumeration


def _get_ndjson_fixtures():
    """Return list of ``.ndjson`` fixture file paths under FIXTURE_DIR."""
    return sorted(os.path.join(FIXTURE_DIR, f) for f in os.listdir(FIXTURE_DIR) if f.endswith(".ndjson") and f not in _NON_FIXTURE_FILES)


##endregion

##region Tests


class TestFixtureValidation:

    @pytest.fixture(scope="class")
    def ndjson_fixtures(self):
        return _get_ndjson_fixtures()

    # ------------------------------------------------------------------
    # JSON validity

    def test_ndjson_fixtures_are_valid_json(self, ndjson_fixtures):
        """Every line in every NDJSON fixture file must be valid JSON (no NaN, no Infinity)."""
        errors = []
        for fpath in ndjson_fixtures:
            with open(fpath, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        errors.append(f"{fpath}:{lineno}: {exc}")
        assert not errors, "Invalid JSON lines in NDJSON fixtures:\n" + "\n".join(errors)

    # ------------------------------------------------------------------
    # Naming convention

    def test_ndjson_fixture_naming_convention(self, ndjson_fixtures):
        """Fixture files must follow the ``{plugin_name}[_{view_suffix}].ndjson`` convention."""
        violations = []
        for fpath in ndjson_fixtures:
            basename = os.path.basename(fpath)
            name_without_ext = os.path.splitext(basename)[0]
            if not any(name_without_ext == prefix or name_without_ext.startswith(prefix + "_") for prefix in VALID_FIXTURE_PREFIXES):
                violations.append(f"{basename}: does not start with a known plugin prefix {sorted(VALID_FIXTURE_PREFIXES)}")
        assert not violations, "Fixture files with non-standard names:\n" + "\n".join(violations)

    # ------------------------------------------------------------------
    # No lingering pkl files

    def test_no_pkl_files_in_fixture_dir(self):
        """Binary .pkl fixture files must not exist in the fixture directory."""
        pkl_files = [f for f in os.listdir(FIXTURE_DIR) if f.endswith(".pkl")]
        assert not pkl_files, f".pkl files found in {FIXTURE_DIR} (must be removed): {pkl_files}"


##endregion

"""JSON Schema compliance tests for instruments-def.yml files.

Validates that every field entry in every ``instruments-def.yml`` file conforms
to the schema defined in ``scripts/tools/instruments-def.schema.json``.

Expected behavior:
    Until all ``__type`` annotations are added this test suite is **expected to
    fail**.  The ``__type`` annotation is a new requirement introduced during the
    BIZOBS-151 Semantic Dictionary export work.  Non-``__type`` schema violations
    are always a hard failure — they indicate a genuine structural problem with
    the source file or schema definition.

    When all ``__type`` annotations have been added this test suite will be
    fully green.

Note:
    All tests use ``@pytest.mark.integration`` because they read real
    ``instruments-def.yml`` files from the repository.
"""

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

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

##region Constants

#: Repository root: test/core/ → test/ → repo root.
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Path to the instruments-def JSON Schema (relative to repo root).
_SCHEMA_PATH: Path = _REPO_ROOT / "scripts" / "tools" / "instruments-def.schema.json"

##endregion


##region Helpers


def _load_schema() -> Dict[str, Any]:
    """Load and return the instruments-def JSON Schema.

    Returns:
        Parsed JSON schema dict.

    Raises:
        FileNotFoundError: If the schema file does not exist.
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_instruments_def_files() -> List[Tuple[str, Dict[str, Any]]]:
    """Load all instruments-def.yml files from core and plugin config directories.

    Returns:
        List of ``(relative_path, parsed_yaml)`` tuples, one per file.
    """
    results: List[Tuple[str, Dict[str, Any]]] = []

    core_file = _REPO_ROOT / "src" / "dtagent.conf" / "instruments-def.yml"
    if core_file.exists():
        with open(core_file, encoding="utf-8") as fh:
            results.append((str(core_file.relative_to(_REPO_ROOT)), yaml.safe_load(fh) or {}))

    for path in sorted(_REPO_ROOT.glob("src/dtagent/plugins/*.config/instruments-def.yml")):
        with open(path, encoding="utf-8") as fh:
            results.append((str(path.relative_to(_REPO_ROOT)), yaml.safe_load(fh) or {}))

    return results


def _make_test_id(filepath: str) -> str:
    """Derive a short test ID from an instruments-def.yml file path.

    Args:
        filepath: Relative path string, e.g.
            ``src/dtagent/plugins/warehouse_usage.config/instruments-def.yml``.

    Returns:
        Short identifier such as ``warehouse_usage`` or ``_core``.
    """
    parent = Path(filepath).parent.name
    return parent.replace(".config", "") if parent.endswith(".config") else "_core"


def _is_type_annotation_error(error: ValidationError) -> bool:
    """Return True if *error* reports a missing ``__type`` annotation.

    The ``__type`` annotation is a new requirement being back-filled across all
    instruments-def.yml files.  These errors are tracked separately from genuine
    schema violations so that progress can be measured and the test can remain
    informative rather than just red-noise.

    Args:
        error: A :class:`~jsonschema.exceptions.ValidationError` instance from
            :meth:`~jsonschema.Draft202012Validator.iter_errors`.

    Returns:
        ``True`` if the error is a ``required``-validator violation specifically
        for the ``__type`` property.
    """
    return error.validator == "required" and "__type" in error.message


##endregion


##region Module-level state (computed once at import time for parametrize)

#: All instruments-def.yml files as (relative_path, data) pairs.
_INSTRUMENTS_DEF_FILES: List[Tuple[str, Dict[str, Any]]] = _load_instruments_def_files()

#: Test IDs derived from file paths (one per parametrize case).
_TEST_IDS: List[str] = [_make_test_id(fp) for fp, _ in _INSTRUMENTS_DEF_FILES]

#: Parsed JSON Schema loaded once at import time.
_SCHEMA: Dict[str, Any] = _load_schema()

##endregion


##region Tests


@pytest.mark.integration
@pytest.mark.parametrize("filepath,data", _INSTRUMENTS_DEF_FILES, ids=_TEST_IDS)
def test_instruments_def_schema_compliance(filepath: str, data: Dict[str, Any]) -> None:
    """Validate an instruments-def.yml file against the JSON Schema.

    **Expected state while back-filling ``__type`` annotations:**

    * All 21 files currently fail with ``__type`` required-property errors
      because most field entries do not yet have ``__type`` annotations.
    * This is intentional — the test acts as a progress tracker.
    * The test fails hard only when **non-**``__type`` schema violations occur,
      because those indicate a genuine structural problem (unknown annotation
      key, malformed value, etc.) that must be fixed immediately.

    **Target state (fully green):**

    * Every field entry in every file has a valid ``__type`` annotation.
    * All assertions pass.

    Args:
        filepath: Repository-relative path to the instruments-def.yml file
            under test (injected by parametrize).
        data:     Parsed YAML content of the file under test (injected by
            parametrize).
    """
    validator = Draft202012Validator(_SCHEMA)
    errors: List[ValidationError] = list(validator.iter_errors(data))

    type_errors: List[ValidationError] = [e for e in errors if _is_type_annotation_error(e)]
    other_errors: List[ValidationError] = [e for e in errors if not _is_type_annotation_error(e)]

    assert not other_errors, f"Non-__type schema violations in {filepath} ({len(other_errors)} error(s)):\n" + "\n".join(
        f"  [{e.validator}] {'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in other_errors
    )

    assert not type_errors, f"Missing __type annotations in {filepath} ({len(type_errors)} field(s)):\n" + "\n".join(
        f"  {'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in type_errors
    )


##endregion

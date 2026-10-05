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
import subprocess
from pathlib import Path

import pytest
from pytest import fixture

#: Repository root resolved relative to this file (test/core/ → test/ → repo root).
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Path to the semantic export shell script.
_SEMDICT_EXPORT_SCRIPT: Path = _REPO_ROOT / "scripts" / "dev" / "build_semantic_export.sh"

#: Expected output directory after a successful export.
_SEMDICT_SOURCE: Path = _REPO_ROOT / "build" / "_semdict" / "source"


def pytest_addoption(parser):
    """Register custom CLI options for the test suite."""
    parser.addoption(
        "--save_conf",
        action="store",
        help="Download and save config from Snowflake to local file (pass 'y' to enable).",
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow build/package integration tests (skipped by default).",
    )
    parser.addoption(
        "--skip-semdict-regen",
        action="store_true",
        default=False,
        help=(
            "Skip automatic regeneration of build/_semdict/source at session start. "
            "Integration tests that require the directory will skip silently if it is missing. "
            "Useful for debugging without re-running the export."
        ),
    )


@fixture(scope="session")
def save_conf(request):
    """Return the --save_conf CLI option value."""
    return request.config.getoption("--save_conf")


@fixture(scope="session", autouse=True)
def semdict_source(request):
    """Ensure build/_semdict/source is always up-to-date before integration tests run.

    Runs ``build_semantic_export.sh`` unconditionally at the start of every pytest session.
    The export is fast (~5 s) and guarantees that integration tests see the output of the
    *current* codebase, not a stale artifact from a previous session.

    Pass ``--skip-semdict-regen`` on the command line to restore the old skip-if-missing
    behaviour (useful when debugging test failures without re-running the full export).

    Raises:
        pytest.fail: If the export script exits non-zero.
    """
    if request.config.getoption("--skip-semdict-regen"):
        # Restore legacy behaviour: skip tests that need the directory if it is absent.
        return

    if not _SEMDICT_EXPORT_SCRIPT.exists():
        pytest.fail(f"semdict export script not found: {_SEMDICT_EXPORT_SCRIPT}")

    result = subprocess.run(
        [str(_SEMDICT_EXPORT_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"semdict export failed (exit {result.returncode}):\n" f"--- stdout ---\n{result.stdout}\n" f"--- stderr ---\n{result.stderr}"
        )

    assert _SEMDICT_SOURCE.exists() and any(
        _SEMDICT_SOURCE.iterdir()
    ), f"build/_semdict/source is missing or empty after successful export: {_SEMDICT_SOURCE}"

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
"""Structural validation of every example DQL query in the instruments-def files.

Each plugin's ``src/dtagent/plugins/<plugin>.config/instruments-def.yml`` (and the core
``src/dtagent.conf/instruments-def.yml``) may declare a ``dql_queries:`` list of example
queries. These examples are exported into the Dynatrace Semantic Dictionary model YAML files
and rendered into ``docs/PLUGINS.md``, so every one must be structurally valid DQL.

This module runs each ``query_string`` through ``dtctl verify query ... -o json`` and asserts
``valid == true``. Validation is *structural only* — the query does not have to return data —
which is exactly what ``dtctl verify query`` checks (it validates syntax + semantics without
executing against Grail).

Gating (mirrors ``test/workflows/test_workflow_dql.py``):
    - Marked ``live``; requires ``dtctl`` on PATH and authenticated to a Dynatrace tenant.
    - Skipped automatically when ``dtctl`` is absent.
    - dtctl exit code ``2`` (auth/permission) or ``3`` (network/server), or an auth-signature
      stderr, is treated as "environment not available" and skips cleanly — only exit ``1`` /
      ``valid: false`` is a genuine failure.

All failures are aggregated into one assertion message so a human can fix every offending
query in a single pass.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml

##region constants

#: Repository root (two levels above this file: test/core/ -> test/ -> repo root).
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: True when the dtctl CLI is available on PATH.
_DTCTL_AVAILABLE: bool = shutil.which("dtctl") is not None

#: Per-query dtctl timeout (seconds).
_DTCTL_TIMEOUT: int = 30

#: stderr substrings that indicate dtctl is not configured / not authenticated (skip, not fail).
_AUTH_ERROR_SIGNATURES: Tuple[str, ...] = (
    "token is required",
    "token expired",
    "refresh failed",
    "authentication",
    "config_error",
    "config file not found",
    "no context",
    "unauthorized",
)

##endregion


##region helpers


def _iter_instruments_def_files() -> List[Path]:
    """Return every instruments-def.yml file (core + all plugin configs).

    Returns:
        Sorted list of instruments-def.yml paths that exist on disk.
    """
    files: List[Path] = []
    core = _REPO_ROOT / "src" / "dtagent.conf" / "instruments-def.yml"
    if core.exists():
        files.append(core)
    files.extend(sorted(_REPO_ROOT.glob("src/dtagent/plugins/*.config/instruments-def.yml")))
    return files


def _collect_example_queries() -> List[Dict[str, Any]]:
    """Collect every ``dql_queries`` entry across all instruments-def files.

    Returns:
        List of dicts, each with keys ``file`` (str, repo-relative), ``description`` (str),
        and ``query_string`` (str).
    """
    collected: List[Dict[str, Any]] = []
    for path in _iter_instruments_def_files():
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        queries = data.get("dql_queries") or []
        rel = str(path.relative_to(_REPO_ROOT))
        for entry in queries:
            collected.append(
                {
                    "file": rel,
                    "description": (entry.get("description") or "").strip(),
                    "query_string": (entry.get("query_string") or "").strip(),
                }
            )
    return collected


def _verify_query(query_string: str) -> Tuple[str, subprocess.CompletedProcess]:
    """Run ``dtctl verify query`` on a single query string.

    The query is passed as a command argument (never piped) so the process exit code is
    preserved — piping into another command would mask it.

    Args:
        query_string: The DQL query to validate.

    Returns:
        Tuple of (outcome, completed_process) where outcome is one of ``"valid"``,
        ``"invalid"``, or ``"skip"``.
    """
    proc = subprocess.run(
        ["dtctl", "verify", "query", query_string, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=_DTCTL_TIMEOUT,
        check=False,
    )
    # Auth/permission (2) or network/server (3) => environment not available.
    if proc.returncode in (2, 3):
        return "skip", proc
    stderr_lower = (proc.stderr or "").lower()
    if any(sig in stderr_lower for sig in _AUTH_ERROR_SIGNATURES):
        return "skip", proc
    # Parse the structured result; the ``valid`` boolean is the authoritative signal.
    try:
        parsed = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        # Could not parse JSON and it was not an auth/network skip — treat as invalid.
        return "invalid", proc
    return ("valid" if parsed.get("valid") is True else "invalid"), proc


##endregion


##region tests


@pytest.mark.live
@pytest.mark.skipif(not _DTCTL_AVAILABLE, reason="dtctl not on PATH")
def test_all_example_dql_queries_are_structurally_valid():
    """Every ``dql_queries`` example must pass ``dtctl verify query`` (``valid: true``).

    Requires dtctl authenticated to a Dynatrace tenant. Skips cleanly when dtctl is not
    configured/authenticated (exit code 2/3 or an auth-signature stderr). Aggregates all
    genuinely-invalid queries into a single, actionable assertion message.
    """
    queries = _collect_example_queries()
    if not queries:
        pytest.skip("No dql_queries examples found in any instruments-def.yml")

    failures: List[str] = []
    for item in queries:
        query_string = item["query_string"]
        if not query_string:
            failures.append(f"{item['file']}: empty query_string for example '{item['description']}'")
            continue

        outcome, proc = _verify_query(query_string)
        if outcome == "skip":
            pytest.skip(
                "dtctl not configured/authenticated — run 'dtctl config set-context' and "
                f"'dtctl auth login' (exit {proc.returncode}): {proc.stderr.strip()[:200]}"
            )
        if outcome == "invalid":
            notifications = ""
            try:
                parsed = json.loads(proc.stdout or "{}")
                notifications = json.dumps(parsed.get("notifications", []), indent=2)
            except json.JSONDecodeError:
                notifications = (proc.stdout or proc.stderr or "").strip()
            failures.append(
                f"\n{item['file']}\n"
                f"  description: {item['description']}\n"
                f"  query_string:\n    " + query_string.replace("\n", "\n    ") + "\n"
                f"  notifications: {notifications}"
            )

    assert not failures, "Invalid example DQL queries found (dtctl verify query):\n" + "\n".join(failures)


##endregion

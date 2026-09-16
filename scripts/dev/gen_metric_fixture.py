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
"""Generate the metric ingest fixture used by the live unit-recognition QA check.

Reads every ``metrics:`` section across all ``instruments-def.yml`` files (core +
plugins) and emits one Dynatrace Metrics API v2 ingest line pair per metric:

    <metric.name> <example_value>
    #<metric.name> gauge dt.meta.displayName="...",dt.meta.unit="...",...

The metadata line format mirrors ``dtagent.otel.semantics.Semantics.gen_metric_definition_line``
and the data line mirrors ``dtagent.otel.metrics.Metrics.report_via_metrics_api`` (with
dimensions omitted — they are irrelevant to unit recognition).

The fixture is checked into ``test/qa/fixtures/all_metrics_ingest_payload.txt`` and used by:
    - ``test/core/test_metric_ingest_fixture.py`` (CI-safe, no network — asserts the fixture
      stays in sync with source)
    - ``scripts/test/verify_metric_units.sh`` (manual, live tenant — POSTs the fixture and
      checks Dynatrace's recognized unit via ``dtctl query``)

Usage::

    # Regenerate in-place (default)
    python scripts/dev/gen_metric_fixture.py

    # Exit 1 if the fixture is out of sync, without modifying it
    python scripts/dev/gen_metric_fixture.py --check

    # Show what would change without writing
    python scripts/dev/gen_metric_fixture.py --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_INSTRUMENTS_DEF = _REPO_ROOT / "src" / "dtagent.conf" / "instruments-def.yml"
_PLUGIN_INSTRUMENTS_DEFS_GLOB = "src/dtagent/plugins/*.config/instruments-def.yml"
FIXTURE_PATH = _REPO_ROOT / "test" / "qa" / "fixtures" / "all_metrics_ingest_payload.txt"

# NOTE: this file is POSTed verbatim to the Dynatrace Metrics API v2 ingest
# endpoint (see scripts/test/verify_metric_units.sh). The MINT line protocol has
# no comment syntax — every line starting with "#" is parsed as a metadata
# line, not a comment. So the fixture must contain ONLY data/metadata lines;
# do not add a "#"-prefixed header here (see this module's docstring instead).


def _esc(value: Any) -> str:
    """Escape a value for a metrics-ingest metadata line (mirrors ``dtagent.util._esc``)."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def load_all_instruments_defs() -> Dict[str, Dict[str, Any]]:
    """Load all instruments-def.yml files from core and all plugin configs.

    Returns:
        Dict mapping plugin name (or ``_core``) to parsed YAML data.
    """
    result: Dict[str, Dict[str, Any]] = {}
    if _CORE_INSTRUMENTS_DEF.exists():
        with open(_CORE_INSTRUMENTS_DEF, encoding="utf-8") as fh:
            result["_core"] = yaml.safe_load(fh) or {}
    for path in sorted(_REPO_ROOT.glob(_PLUGIN_INSTRUMENTS_DEFS_GLOB)):
        plugin_name = path.parent.name.replace(".config", "")
        with open(path, encoding="utf-8") as fh:
            result[plugin_name] = yaml.safe_load(fh) or {}
    return result


def _metric_definition_line(metric_name: str, entry: Dict[str, Any]) -> str:
    """Build the ``#<metric> gauge dt.meta...`` metadata line for one metric.

    Mirrors ``Semantics.gen_metric_definition_line`` / its ``__gen_metric_details`` helper.
    """
    metric_details = {k: v for k, v in entry.items() if not str(k).startswith("__")}
    combined = {
        "displayName": " ".join(metric_name.split(".")[-1:]).replace("_", " ").title(),
        **metric_details,
    }
    meta_str = ",".join(f'dt.meta.{k}="{_esc(v)}"' for k, v in combined.items())
    return f"#{metric_name} gauge {meta_str}"


def build_fixture_lines(all_defs: Dict[str, Dict[str, Any]]) -> List[str]:
    """Build ingest payload lines: one data line + one metadata line per unique metric.

    Metrics defined identically under multiple plugins only appear once (metric
    identity is global, not per-plugin).

    Args:
        all_defs: Output of :func:`load_all_instruments_defs`.

    Returns:
        List of payload lines (data line immediately followed by its metadata line).
    """
    lines: List[str] = []
    seen: set = set()
    all_metrics: Dict[str, Dict[str, Any]] = {}
    for data in all_defs.values():
        for metric_name, entry in (data.get("metrics") or {}).items():
            all_metrics.setdefault(metric_name, entry)

    for metric_name in sorted(all_metrics):
        if metric_name in seen:
            continue
        seen.add(metric_name)
        entry = all_metrics[metric_name]
        example = entry.get("__example", 1)
        lines.append(f"{metric_name} {example}")
        lines.append(_metric_definition_line(metric_name, entry))
    return lines


def render_fixture(all_defs: Dict[str, Dict[str, Any]]) -> str:
    """Render the full fixture file content (payload lines only, no comment header).

    The MINT line protocol has no comment syntax, so this file must contain only
    data/metadata lines — see the module-level NOTE above ``_esc``.
    """
    lines = build_fixture_lines(all_defs)
    return "\n".join(lines) + "\n"


def main() -> int:
    """Entry point: parse args, detect drift, and sync or report as requested."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Exit 1 if fixture is out of sync, without modifying it.")
    mode.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    args = parser.parse_args()

    all_defs = load_all_instruments_defs()
    new_content = render_fixture(all_defs)

    current_content = FIXTURE_PATH.read_text(encoding="utf-8") if FIXTURE_PATH.exists() else None
    in_sync = current_content == new_content
    metric_count = len(build_fixture_lines(all_defs)) // 2

    if in_sync:
        print(f"Already in sync: {metric_count} metrics in fixture.")
        return 0

    if args.check:
        print(
            f"ERROR: {FIXTURE_PATH.relative_to(_REPO_ROOT)} is out of sync with instruments-def.yml sources "
            "(run 'python scripts/dev/gen_metric_fixture.py' to fix).",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print(f"Dry run: would write {metric_count} metrics to fixture. No files written.")
        return 0

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated fixture: {metric_count} metrics written to {FIXTURE_PATH.relative_to(_REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

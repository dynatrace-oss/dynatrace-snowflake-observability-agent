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
"""Sync the MetricUnit enum in instruments-def.schema.json from units.json.

Reads all unit abbreviations from the otel-build-tool units registry
(.context/otel-build-tool/semantic-conventions/src/opentelemetry/semconv/units/units.json)
and writes them into the $defs/MetricUnit/enum of the instruments-def schema.

Usage::

    # Sync in-place (default)
    python scripts/dev/sync_metric_units.py

    # Check only — exit 1 if schema is out of sync (useful as CI gate)
    python scripts/dev/sync_metric_units.py --check

    # Show what would change without writing
    python scripts/dev/sync_metric_units.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

UNITS_JSON = (
    _REPO_ROOT
    / ".context"
    / "otel-build-tool"
    / "semantic-conventions"
    / "src"
    / "opentelemetry"
    / "semconv"
    / "units"
    / "units.json"
)

SCHEMA_JSON = _REPO_ROOT / "scripts" / "tools" / "instruments-def.schema.json"

_METRIC_UNIT_DEF = "$defs/MetricUnit"


def load_abbreviations(units_path: Path) -> list[str]:
    """Extract all abbreviation values from units.json and return sorted list."""
    with units_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    abbrs: set[str] = set()
    for units in data.values():
        for entry in units.values():
            if "abbreviation" in entry:
                abbrs.add(entry["abbreviation"])

    return sorted(abbrs, key=lambda x: (x.lower(), x))


def load_schema(schema_path: Path) -> dict:
    """Load and return the JSON schema from disk."""
    with schema_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_schema(schema_path: Path, schema: dict) -> None:
    """Write the JSON schema to disk with 2-space indentation and a trailing newline."""
    with schema_path.open("w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def get_current_enum(schema: dict) -> list[str]:
    """Return the current MetricUnit enum values from the schema."""
    return schema.get("$defs", {}).get("MetricUnit", {}).get("enum", [])


def main() -> int:
    """Entry point: parse args, detect drift, and sync or report as requested."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Exit 1 if schema is out of sync, without modifying it.")
    mode.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    args = parser.parse_args()

    if not UNITS_JSON.exists():
        print(f"ERROR: units.json not found at {UNITS_JSON}", file=sys.stderr)
        return 1
    if not SCHEMA_JSON.exists():
        print(f"ERROR: schema not found at {SCHEMA_JSON}", file=sys.stderr)
        return 1

    new_abbrs = load_abbreviations(UNITS_JSON)
    schema = load_schema(SCHEMA_JSON)
    current_abbrs = get_current_enum(schema)

    added = sorted(set(new_abbrs) - set(current_abbrs), key=lambda x: (x.lower(), x))
    removed = sorted(set(current_abbrs) - set(new_abbrs), key=lambda x: (x.lower(), x))
    in_sync = not added and not removed

    if in_sync:
        print(f"Already in sync: {len(new_abbrs)} abbreviations in MetricUnit enum.")
        return 0

    print(f"Drift detected: {len(added)} added, {len(removed)} removed.")
    if added:
        print(f"  + {added}")
    if removed:
        print(f"  - {removed}")

    if args.check:
        print("ERROR: MetricUnit enum is out of sync with units.json. Run 'make sync-units' to fix.", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Dry run: would update MetricUnit enum to {len(new_abbrs)} abbreviations. No files written.")
        return 0

    schema["$defs"]["MetricUnit"]["enum"] = new_abbrs
    write_schema(SCHEMA_JSON, schema)
    print(f"Updated MetricUnit enum: {len(new_abbrs)} abbreviations written to {SCHEMA_JSON.relative_to(_REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

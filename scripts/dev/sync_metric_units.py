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
"""Sync the MetricUnit enum in instruments-def.schema.json.

The Dynatrace Metrics API (``dt.meta.unit``) only *recognizes* unit strings
that match the ``universal-units`` library's ``UnitId`` vocabulary (~70
entries, cached at ``.context/universal-units/UnitId.java``). The OTel
semantic-conventions ``units.json`` registry is a *different*, much larger
vocabulary (825 entries) that is only relevant to the Semantic Dictionary
export step (``UNIT_MAP`` in ``src/build/export_semantics.py``), since SD
abbreviations do not always match ``universal-units`` UCUM symbols.

This script:

1. Parses ``UnitId.java`` to get the recognized ``dt.meta.unit`` vocabulary
   (preferring the UCUM/``caseSensitiveSymbol`` form for each entry).
2. Loads ``units.json`` and looks up each ``UnitId`` by name to find its SD
   abbreviation.
3. Writes the recognized UCUM symbols, plus a small DSOA allowlist of
   domain-specific free-text exceptions, into ``$defs/MetricUnit/enum``.
4. Prints a summary of every case where the ``universal-units`` UCUM symbol
   differs from the ``units.json`` abbreviation — these are exactly the
   entries that need an explicit ``UNIT_MAP`` translation for SD export.

Usage::

    # Sync in-place (default)
    python scripts/dev/sync_metric_units.py

    # Check only — exit 1 if schema is out of sync (useful as CI gate)
    python scripts/dev/sync_metric_units.py --check

    # Show what would change without writing
    python scripts/dev/sync_metric_units.py --dry-run

Refreshing the cached ``UnitId.java`` (requires ``bbctl`` + Bitbucket auth)::

    bbctl repo cat src/main/java/com/dynatrace/metrics/units/identifier/UnitId.java \\
        --project DEUS --repo universal-units \\
        > .context/universal-units/UnitId.java
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

UNIT_ID_JAVA = _REPO_ROOT / ".context" / "universal-units" / "UnitId.java"

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

# DSOA-approved free-text unit values with no recognized universal-units
# equivalent (singular or plural). These are intentionally NOT translated
# in instruments-def.yml — they are harmless, human-readable domain nouns
# that Dynatrace simply echoes back verbatim. See UNIT_MAP in
# export_semantics.py for their Semantic Dictionary translation.
DSOA_ALLOWLIST = frozenset(
    {
        "credits",
        "currency",
        "files",
        "partitions",
        "rows",
        "clusters",
        "warehouses",
        "queries",
    }
)

# universal-units recognizes SI-decimal and binary prefixes composed with a
# base unit's UCUM symbol (e.g. milli+second="ms", mebi+byte="MiBy"). These
# compositions are NOT literal UnitId enum constants, so the parser can't see
# them. List only the prefixed forms actually used in DSOA instruments-def.yml
# — extend this set if a new prefixed unit is introduced.
RECOGNIZED_PREFIXED_FORMS = frozenset(
    {
        "ms",  # milli + second
        "MiBy",  # mebi + byte (binary prefix)
    }
)

_ENUM_CONSTANT_RE = re.compile(r"^\s*[A-Z][A-Z0-9_]*\s*\(")
_QUOTED_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


class UnitIdEntry(NamedTuple):
    """A single parsed universal-units UnitId enum constant."""

    constant: str
    print_symbol: str
    ucum_symbol: str
    name: str
    plural_name: str


def parse_unit_id_java(path: Path) -> list[UnitIdEntry]:
    """Parse UnitId.java and return every enum constant's (printSymbol, ucumSymbol, name, pluralName)."""
    entries: list[UnitIdEntry] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not _ENUM_CONSTANT_RE.match(line):
                continue
            constant = line.split("(", 1)[0].strip()
            quoted = _QUOTED_STRING_RE.findall(line)
            if len(quoted) < 5:
                continue
            print_symbol, ucum_symbol, name, plural_name = quoted[0], quoted[1], quoted[2], quoted[3]
            entries.append(UnitIdEntry(constant, print_symbol, ucum_symbol, name, plural_name))
    return entries


def load_units_json_by_name(units_path: Path) -> dict[str, str]:
    """Return a map of unit name (lowercase) -> SD abbreviation, from units.json."""
    with units_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    by_name: dict[str, str] = {}
    for group in data.values():
        for key, entry in group.items():
            abbreviation = entry.get("abbreviation")
            if not abbreviation:
                continue
            by_name[key.lower()] = abbreviation
            display_name = entry.get("displayName")
            if display_name:
                by_name.setdefault(display_name.lower(), abbreviation)
    return by_name


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


def build_enum(entries: list[UnitIdEntry]) -> list[str]:
    """Build the sorted MetricUnit enum: recognized UCUM symbols + prefixed forms + DSOA allowlist."""
    values = {e.ucum_symbol for e in entries} | RECOGNIZED_PREFIXED_FORMS | DSOA_ALLOWLIST
    return sorted(values, key=lambda x: (x.lower(), x))


def find_divergences(entries: list[UnitIdEntry], units_by_name: dict[str, str]) -> list[tuple[str, str, str]]:
    """Return (name, ucum_symbol, sd_abbreviation) for every UnitId whose UCUM symbol != SD abbreviation."""
    divergences: list[tuple[str, str, str]] = []
    for e in entries:
        sd_abbr = units_by_name.get(e.name.lower())
        if sd_abbr is not None and sd_abbr != e.ucum_symbol:
            divergences.append((e.name, e.ucum_symbol, sd_abbr))
    return divergences


def main() -> int:
    """Entry point: parse args, detect drift, and sync or report as requested."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Exit 1 if schema is out of sync, without modifying it.")
    mode.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    args = parser.parse_args()

    if not UNIT_ID_JAVA.exists():
        print(f"ERROR: UnitId.java not found at {UNIT_ID_JAVA}. See module docstring to refresh it.", file=sys.stderr)
        return 1
    if not UNITS_JSON.exists():
        print(f"ERROR: units.json not found at {UNITS_JSON}", file=sys.stderr)
        return 1
    if not SCHEMA_JSON.exists():
        print(f"ERROR: schema not found at {SCHEMA_JSON}", file=sys.stderr)
        return 1

    entries = parse_unit_id_java(UNIT_ID_JAVA)
    units_by_name = load_units_json_by_name(UNITS_JSON)
    new_enum = build_enum(entries)

    divergences = find_divergences(entries, units_by_name)
    print(f"universal-units entries parsed: {len(entries)}")
    print(f"UCUM symbol vs. SD abbreviation divergences: {len(divergences)}")
    for name, ucum_symbol, sd_abbr in divergences:
        print(f"  {name}: universal-units={ucum_symbol!r} vs units.json={sd_abbr!r}  -> add UNIT_MAP[{ucum_symbol!r}] = {sd_abbr!r}")

    schema = load_schema(SCHEMA_JSON)
    current_enum = get_current_enum(schema)

    added = sorted(set(new_enum) - set(current_enum), key=lambda x: (x.lower(), x))
    removed = sorted(set(current_enum) - set(new_enum), key=lambda x: (x.lower(), x))
    in_sync = not added and not removed

    if in_sync:
        print(f"Already in sync: {len(new_enum)} values in MetricUnit enum.")
        return 0

    print(f"Drift detected: {len(added)} added, {len(removed)} removed.")
    if added:
        print(f"  + {added}")
    if removed:
        print(f"  - {removed}")

    if args.check:
        print("ERROR: MetricUnit enum is out of sync. Run 'make sync-units' to fix.", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Dry run: would update MetricUnit enum to {len(new_enum)} values. No files written.")
        return 0

    schema["$defs"]["MetricUnit"]["enum"] = new_enum
    write_schema(SCHEMA_JSON, schema)
    print(f"Updated MetricUnit enum: {len(new_enum)} values written to {SCHEMA_JSON.relative_to(_REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

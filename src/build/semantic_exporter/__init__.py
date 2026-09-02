"""Export DSOA instruments-def.yml files as Semantic Dictionary-compliant YAML.

Reads all instruments-def.yml files from plugin configuration directories,
classifies each field using the Semantic Dictionary resource/signal definition
from ``source/readme.md``, and emits schema-valid YAML documents under
``build/_semdict/source/``.

SD definition (source/readme.md)::

    resource field  — describes the *source* of telemetry (host, process,
                       container). Value STABLE for the lifetime of the resource.
    signal field    — present on a single signal event (span ID, HTTP URL,
                       DB statement, query execution status, warehouse name…).
                       Everything that is not a resource field.

Classification rules::

    key in RESOURCE_ATTRIBUTE_KEYS   → resource_fields  (stable lifetime, on ALL records)
    __field_type: resource           → resource_fields  (explicit override)
    __field_type: signal             → signal_fields    (explicit override)
    all other fields (any section)   → signal_fields    (default — metric dimensions
                                        like warehouse.name, db.namespace, db.user
                                        vary per observation, NOT per resource lifetime)
    metrics section                  → metrics/
    event_timestamps section         → model/snowflake/ + signal_fields (timestamp fields)

Note on metric dimension resolution:
    Metric ``attributes:`` lists use DSOA ``dimensions`` section entries (not SD
    resource classification) because dimensions are the low-cardinality metric-
    splitting fields.  SD resource/signal classification only governs which
    *fields file* a field is emitted into — it does not determine metric dims.
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

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from build.semantic_exporter.yaml_helpers import ExportError, _IndentedDumper, _make_ruamel_yaml, _merge_into_ruamel
from build.semantic_exporter.field_emitters import (
    INTERFACE_DATABASE_KEYS,
    INTERFACE_WAREHOUSE_KEYS,
    KNOWN_REFS,
    RESOURCE_ATTRIBUTE_KEYS,
    UNIT_MAP,
    VALID_STABILITY_VALUES,
    _RES_NS,
    _SIG_NS,
    _build_type_node,
    _classify_field,
    _coerce_attribute_example,
    _coerce_string_array_examples,
    _emit_id_entry,
    _emit_metric_entry,
    _emit_ref_entry,
    _make_title,
    _map_attr_type,
    _map_metric_instrument,
    _merge_field_entries,
    _ns_group,
    _plugin_label,
    _validate_entry,
)

from build.semantic_exporter.exporter import SemanticExporter

log = logging.getLogger("build.export_semantics")

__all__ = [
    "ExportError",
    "INTERFACE_DATABASE_KEYS",
    "INTERFACE_WAREHOUSE_KEYS",
    "KNOWN_REFS",
    "RESOURCE_ATTRIBUTE_KEYS",
    "SemanticExporter",
    "UNIT_MAP",
    "VALID_STABILITY_VALUES",
    "_RES_NS",
    "_SIG_NS",
    "_IndentedDumper",
    "_build_type_node",
    "_classify_field",
    "_coerce_attribute_example",
    "_coerce_string_array_examples",
    "_emit_id_entry",
    "_emit_metric_entry",
    "_emit_ref_entry",
    "_make_ruamel_yaml",
    "_make_title",
    "_map_attr_type",
    "_map_metric_instrument",
    "_merge_field_entries",
    "_merge_into_ruamel",
    "_ns_group",
    "_plugin_label",
    "_validate_entry",
    "main",
]


##region CLI


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv).

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="Export DSOA instruments-def.yml files as Semantic Dictionary YAML.")
    parser.add_argument("--output", default="build/_semdict/source", help="Output directory (default: build/_semdict/source)")
    parser.add_argument("--schema", default="scripts/tools/semconv.schema.json", help="Path to semconv.schema.json")
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    parser.add_argument(
        "--sd-metadata",
        action="store_true",
        help=(
            "Write SD metadata files alongside the YAML source: OWNERS, "
            "definitions/mapping/global_field_categories.json, and doc/ model/field stubs. "
            "Only for SD repo exports (e.g. via --generate-docs). "
            "Do NOT pass this for the regular 'make semantic-dictionary' export."
        ),
    )
    parser.add_argument(
        "--no-display-name",
        action="store_true",
        dest="no_display_name",
        help=(
            "Suppress the display_name property on all emitted attribute and enum member nodes. "
            "Use when the target SD PR should not include display_name fields "
            "(e.g. when the SD committee has not yet approved them for a namespace)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    args = _parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    repo_root = Path(__file__).resolve().parents[3]
    output_dir = Path(args.output) if Path(args.output).is_absolute() else repo_root / args.output
    schema_path = Path(args.schema) if Path(args.schema).is_absolute() else repo_root / args.schema
    log.info("Repo root : %s", repo_root)
    log.info("Output dir: %s", output_dir)
    exporter = SemanticExporter(
        repo_root=repo_root,
        output_dir=output_dir,
        schema_path=schema_path,
        sd_metadata=args.sd_metadata,
        no_display_name=args.no_display_name,
    )
    try:
        summary = exporter.export()
    except ExportError as exc:
        log.error("Export failed: %s", exc)
        return 1
    total = summary["ref"] + summary["new"] + summary["deprecated_alias"] + summary["otel_only"] + summary["otel_dsoa"]
    print("✓ Export complete")
    print(f"Files generated            : {summary['files']}")
    print(f"Total classified fields    : {total}")
    print(f"  - ref                    : {summary['ref']}")
    print(f"  - new                    : {summary['new']}")
    print(f"  - deprecated-alias       : {summary['deprecated_alias']}")
    print(f"  - otel-only              : {summary['otel_only']}")
    print(f"  - otel-dsoa              : {summary['otel_dsoa']}")
    print(f"Resource fields emitted    : {summary['resource_fields']}")
    print(f"Signal fields emitted      : {summary['signal_fields']}")
    print(f"Metric fields emitted      : {summary['metric_fields']}")
    print(f"Event timestamp fields     : {summary['event_timestamp_fields']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

##endregion

"""Export DSOA instruments-def.yml files as Semantic Dictionary-compliant YAML.

Reads all instruments-def.yml files from the DSOA plugin configuration directories,
classifies each field by its semantic-dictionary status (ref/new/deprecated-alias/otel-only),
and emits schema-valid YAML documents under build/_semdict/source/.
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
from typing import Any, Dict, List, Optional, Tuple

import yaml

##region Constants

#: Fields that already exist in the Dynatrace Semantic Dictionary.
KNOWN_REFS = {
    "db.system",
    "host.name",
    "service.name",
    "telemetry.exporter.name",
    "telemetry.exporter.version",
    "db.query.text",
    "event.id",
    "authentication.type",
}

#: Fields that belong in the global fields file (not plugin-specific).
#: All non-metric attributes and dimensions are also promoted to global
#: under the first-class citizen principle — models ref them rather than
#: defining them locally.
GLOBAL_FIELD_KEYS = {
    "dsoa.run.id",
    "dsoa.run.context",
    "dsoa.run.plugin",
    "deployment.environment",
    "deployment.environment.tag",
    "observed_timestamp",
    "snowflake.event.type",
    "dsoa.agent.memory.peak_rss",
}

#: Known acronyms / abbreviations that must stay ALL-CAPS in display_name.
#: Order matters: longer tokens checked first to avoid partial replacement.
DISPLAY_NAME_ACRONYMS = (
    "DSOA",
    "OTel",
    "DDL",
    "DML",
    "RSS",
    "URL",
    "API",
    "ID",
    "DB",
    "QA",
    "SQL",
)

#: Instrument type mappings from instruments-def __type to semconv instrument.
METRIC_TYPE_MAP: Dict[str, str] = {
    "gauge": "gauge",
    "count": "counter",
    "counter": "counter",
    "updowncounter": "updowncounter",
    "histogram": "histogram",
}

#: Attribute type mappings from instruments-def __type to semconv type.
ATTR_TYPE_MAP: Dict[str, str] = {
    "long": "long",
    "int": "long",
    "double": "double",
    "float": "double",
    "boolean": "boolean",
    "string": "string",
}

#: Valid semdict classification values.
VALID_SEMDICT_FLAGS = {"ref", "new", "deprecated-alias", "otel-only"}

##endregion


##region Logging setup

log = logging.getLogger(__name__)

##endregion


##region Data structures


class ExportError(Exception):
    """Raised when export encounters a fatal validation error."""


##endregion


##region Classification helpers


def _restore_acronyms(text: str) -> str:
    """Restore known acronyms to their correct casing in a title-cased string.

    After title-casing a display name, tokens like ``Db``, ``Id``, ``Dsoa``
    must be restored to ``DB``, ``ID``, ``DSOA`` respectively.  Comparison is
    case-insensitive so this handles any capitalisation produced by
    ``str.title()``.

    Args:
        text: Title-cased string that may contain incorrectly-cased acronyms.

    Returns:
        String with known acronyms restored to their canonical casing.
    """
    words = text.split(" ")
    restored = []
    for word in words:
        # Strip trailing punctuation before comparing, re-attach after
        suffix = ""
        stem = word
        if word and not word[-1].isalnum():
            suffix = word[-1]
            stem = word[:-1]
        match = next((a for a in DISPLAY_NAME_ACRONYMS if a.lower() == stem.lower()), None)
        restored.append((match if match else stem) + suffix)
    return " ".join(restored)


def _make_display_name(key: str) -> str:
    """Convert a dot-notation field key to a human-readable display name.

    All segments of the key are included to produce an unambiguous name.
    Known acronyms (DB, ID, DSOA, OTel, RSS, …) are preserved in their
    canonical casing.

    Args:
        key: Dot-notation field key, e.g. ``dsoa.run.id``.

    Returns:
        Human-readable display name string, e.g. ``DSOA Run ID``.
    """
    parts = key.replace("_", " ").replace("-", " ").replace(".", " ").split()
    title_parts = " ".join(p.title() for p in parts)
    return _restore_acronyms(title_parts)


def _map_attr_type(raw_type: Optional[str]) -> str:
    """Map an instruments-def ``__type`` value to a semconv attribute type.

    Args:
        raw_type: Value of ``__type`` from instruments-def, or ``None``.

    Returns:
        Semconv type string (default ``"string"``).
    """
    if not raw_type:
        return "string"
    return ATTR_TYPE_MAP.get(str(raw_type).lower(), "string")


def _map_metric_instrument(raw_type: Optional[str]) -> str:
    """Map an instruments-def ``__type`` value to a semconv instrument.

    Args:
        raw_type: Value of ``__type`` from instruments-def, or ``None``.

    Returns:
        Semconv instrument string (default ``"gauge"``).
    """
    if not raw_type:
        log.warning("Metric has no __type; defaulting to gauge")
        return "gauge"
    mapped = METRIC_TYPE_MAP.get(str(raw_type).lower())
    if not mapped:
        log.warning("Unknown metric __type '%s'; defaulting to gauge", raw_type)
        return "gauge"
    return mapped


##endregion


##region Entry validation


def _validate_entry(key: str, entry: Dict[str, Any], section: str, source_file: str) -> List[str]:
    """Validate a single instruments-def entry for required semdict metadata.

    Args:
        key:         Field key, e.g. ``dsoa.run.id``.
        entry:       Dict of entry metadata from instruments-def.
        section:     Section name: ``attributes``, ``dimensions``, or ``metrics``.
        source_file: File path for error messages.

    Returns:
        List of error strings (empty when validation passes).
    """
    errors: List[str] = []
    if not entry.get("__description"):
        errors.append(f"[{source_file}] {section}.{key}: missing __description")
    # Allow 0, False, and "" as valid example values — only None (key absent) is an error
    if entry.get("__example") is None:
        errors.append(f"[{source_file}] {section}.{key}: missing __example")

    semdict = entry.get("__semdict", "new")
    if semdict == "deprecated-alias" and not entry.get("__otel_replacement"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: deprecated-alias requires __otel_replacement")
    if semdict == "otel-only" and not entry.get("__otel_note"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: otel-only requires __otel_note")
    return errors


##endregion


##region Emit helpers


def _emit_ref_entry(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a ``ref:`` attribute entry.

    Args:
        key:   Field key to reference.
        entry: Source instruments-def entry (used for optional note).

    Returns:
        Dict representing ``{ref: key}`` plus optional ``note:``.
    """
    node: Dict[str, Any] = {"ref": key}
    note = entry.get("__otel_note")
    if note:
        node["note"] = str(note).strip()
    return node


def _emit_id_entry(key: str, entry: Dict[str, Any], semdict_flag: str) -> Dict[str, Any]:
    """Build a full ``id:`` attribute definition block.

    ``deprecated-alias`` entries represent fields that OTel has renamed but
    DSOA still emits for backward compatibility.  They are NOT marked as
    ``stability: deprecated`` — that is reserved for fields from deprecated
    plugins.  Instead a ``note:`` is added citing the OTel rename, and
    stability stays ``experimental``.

    Args:
        key:          Field key, e.g. ``dsoa.run.id``.
        entry:        Source instruments-def entry dict.
        semdict_flag: Classification: ``new``, ``deprecated-alias``, or ``otel-only``.

    Returns:
        Dict with all required semconv attribute fields.
    """
    raw_type = entry.get("__type")
    attr_type = _map_attr_type(raw_type)
    description = str(entry["__description"]).strip()
    example_raw = entry["__example"]
    # Handle None/empty: use empty string as fallback for nullable fields
    if example_raw is None:
        example_raw = ""
    examples = [str(example_raw).strip()] if not isinstance(example_raw, list) else [str(e).strip() for e in example_raw]

    node: Dict[str, Any] = {
        "id": key,
        "display_name": _make_display_name(key),
        "type": attr_type,
        "stability": "experimental",
        "brief": description,
        "examples": examples,
    }

    # deprecated-alias: OTel renamed this field, but DSOA still emits it
    # → NOT stability:deprecated; add a note warning about the OTel rename
    if semdict_flag == "deprecated-alias":
        replacement = entry.get("__otel_replacement", "")
        otel_note = entry.get("__otel_note", "")
        warning = f"OTel renamed this field to {replacement}. DSOA continues to emit it for backward compatibility."
        if otel_note:
            warning = f"{otel_note} DSOA continues to emit it for backward compatibility."
        node["note"] = warning
    elif entry.get("__otel_note"):
        node["note"] = str(entry["__otel_note"]).strip()

    return node


def _emit_metric_entry(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a ``type: metric`` group entry.

    Args:
        key:   Metric key, e.g. ``snowflake.warehouse.credits.used``.
        entry: Source instruments-def metric entry.

    Returns:
        Dict representing a semconv metric definition.
    """
    raw_type = entry.get("__type")
    instrument = _map_metric_instrument(raw_type)
    description = str(entry.get("__description", "")).strip()
    example_raw = entry.get("__example", "0")
    examples = [str(example_raw).strip()] if not isinstance(example_raw, list) else [str(e).strip() for e in example_raw]

    unit = entry.get("unit") or entry.get("__unit")
    if not unit:
        log.warning("Metric '%s' has no unit; omitting unit field", key)

    display_name = entry.get("displayName") or _make_display_name(key)

    node: Dict[str, Any] = {
        "id": key,
        "type": "metric",
        "metric_name": key,
        "instrument": instrument,
        "stability": "experimental",
        "brief": description,
        "examples": examples,
        "title": display_name,
    }
    if unit:
        node["unit"] = str(unit)

    note = entry.get("__otel_note")
    if note:
        node["note"] = str(note).strip()

    return node


##endregion


##region Core export class


class SemanticExporter:
    """Reads instruments-def.yml files and emits Semantic Dictionary YAML.

    Attributes:
        repo_root:  Absolute path to the repository root.
        output_dir: Directory where generated YAML files are written.
        schema_path: Optional path to ``semconv.schema.json`` for validation.
    """

    def __init__(self, repo_root: Path, output_dir: Path, schema_path: Optional[Path] = None) -> None:
        """Initialise the exporter.

        Args:
            repo_root:   Absolute path to the repository root.
            output_dir:  Directory to write generated YAML files (will be created).
            schema_path: Optional path to semconv JSON schema for validation.
        """
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.schema_path = schema_path
        self._schema: Optional[Dict[str, Any]] = None
        self._counters: Dict[str, int] = {"files": 0, "ref": 0, "new": 0, "deprecated_alias": 0, "otel_only": 0}

    ##region Discovery

    def _discover_files(self) -> List[Tuple[str, Path]]:
        """Glob all instruments-def.yml files in the repository.

        Returns:
            List of ``(plugin_name, path)`` tuples.
            The core file uses plugin name ``"_core"``.
        """
        files: List[Tuple[str, Path]] = []

        # Core global file
        core_file = self.repo_root / "src" / "dtagent.conf" / "instruments-def.yml"
        if core_file.exists():
            files.append(("_core", core_file))
        else:
            log.warning("Core instruments-def.yml not found at %s", core_file)

        # Plugin files  (pattern: src/dtagent/plugins/<name>.config/instruments-def.yml)
        plugin_glob = sorted(self.repo_root.glob("src/dtagent/plugins/*.config/instruments-def.yml"))
        for path in plugin_glob:
            # Extract plugin name from the directory: e.g. "warehouse_usage.config" → "warehouse_usage"
            config_dir = path.parent.name  # e.g. "warehouse_usage.config"
            plugin_name = config_dir.replace(".config", "")
            files.append((plugin_name, path))

        log.info("Found %d instruments-def.yml files", len(files))
        return files

    ##endregion

    ##region Parsing

    def _parse_file(self, plugin_name: str, path: Path) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """Parse a single instruments-def.yml file.

        Args:
            plugin_name: Plugin name used for error messages.
            path:        Absolute path to the instruments-def.yml file.

        Returns:
            Tuple of ``(errors, entries)`` where ``entries`` is a dict
            keyed by field key with values containing section + metadata.

        Raises:
            ExportError: If the file cannot be parsed.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:
            raise ExportError(f"Failed to parse {path}: {exc}") from exc

        if not data:
            log.warning("Empty instruments-def.yml: %s", path)
            return [], {}

        errors: List[str] = []
        entries: Dict[str, Dict[str, Any]] = {}

        for section in ("attributes", "dimensions", "metrics"):
            section_data = data.get(section) or {}
            for key, raw_entry in section_data.items():
                entry = raw_entry or {}
                semdict_flag = entry.get("__semdict", "new")
                if semdict_flag not in VALID_SEMDICT_FLAGS:
                    log.warning("[%s] %s.%s: unknown __semdict value '%s'; treating as 'new'", plugin_name, section, key, semdict_flag)
                    semdict_flag = "new"

                validation_errors = _validate_entry(key, entry, section, str(path))
                errors.extend(validation_errors)

                if semdict_flag == "ref" and key not in KNOWN_REFS:
                    log.warning("[%s] %s.%s: __semdict: ref but key not in KNOWN_REFS", plugin_name, section, key)

                entries[key] = {
                    "section": section,
                    "semdict": semdict_flag,
                    "plugin": plugin_name,
                    "entry": entry,
                }

        return errors, entries

    ##endregion

    ##region Grouping

    def _group_entries(self, all_entries: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Separate entries into global fields and per-plugin metric groups.

        First-class citizen principle: ALL attributes and dimensions are
        promoted to the global fields file regardless of their origin plugin.
        Plugin model files reference global fields via ``ref:`` entries and
        only define their own ``type: metric`` nodes directly.

        Metrics from the ``_core`` plugin (e.g. ``dsoa.agent.memory.peak_rss``)
        are also treated as global.

        Args:
            all_entries: Flat dict of ``{key: entry_metadata}`` across all files.

        Returns:
            Tuple of ``(global_entries, plugin_metric_entries)`` where:
            - ``global_entries``: ``{key: meta}`` for all attributes, dimensions,
              and core metrics.
            - ``plugin_metric_entries``: ``{plugin_name: {key: meta}}`` for
              per-plugin metric-section entries only.
        """
        global_entries: Dict[str, Any] = {}
        plugin_metric_entries: Dict[str, Dict[str, Any]] = {}

        for key, meta in all_entries.items():
            section = meta["section"]
            plugin = meta["plugin"]

            if section == "metrics" and plugin != "_core":
                # Per-plugin metrics stay in model files
                plugin_metric_entries.setdefault(plugin, {})[key] = meta
            else:
                # All attributes, all dimensions, and core metrics → global
                global_entries[key] = meta

        return global_entries, plugin_metric_entries

    ##endregion

    ##region YAML emission

    def _build_attribute_node(self, key: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Build a single attribute node (ref or id block).

        Args:
            key:  Field key.
            meta: Entry metadata dict.

        Returns:
            Semconv-compliant attribute dict.
        """
        semdict_flag = meta["semdict"]
        entry = meta["entry"]

        if semdict_flag == "ref":
            self._counters["ref"] += 1
            return _emit_ref_entry(key, entry)

        node = _emit_id_entry(key, entry, semdict_flag)
        if semdict_flag == "deprecated-alias":
            self._counters["deprecated_alias"] += 1
        elif semdict_flag == "otel-only":
            self._counters["otel_only"] += 1
        else:
            self._counters["new"] += 1
        return node

    def _build_global_yaml(self, global_entries: Dict[str, Any]) -> Dict[str, Any]:
        """Build the snowflake_global.yaml document structure.

        Args:
            global_entries: Dict of ``{key: meta}`` for global fields.

        Returns:
            Semconv-compliant YAML document dict with ``groups`` top-level key.
        """
        attributes = []
        for key in sorted(global_entries):
            meta = global_entries[key]
            if meta["section"] == "metrics":
                # Metrics in global go as metric definitions directly
                continue
            attributes.append(self._build_attribute_node(key, meta))

        group: Dict[str, Any] = {
            "id": "dsoa.fields.global",
            "type": "attribute_group",
            "title": "DSOA global fields",
            "brief": "Global fields emitted by the Dynatrace Snowflake Observability Agent across all plugin contexts.",
            "attributes": attributes,
        }
        groups = [group]

        # Emit global metrics separately
        for key in sorted(global_entries):
            meta = global_entries[key]
            if meta["section"] == "metrics":
                groups.append(self._build_metric_node(key, meta))

        return {"groups": groups}

    def _build_plugin_yaml(self, plugin_name: str, plugin_metric_entries: Dict[str, Any]) -> Dict[str, Any]:
        """Build a per-plugin model YAML document.

        Structure (Fix 3 — proper semdict grouping):
        - One ``type: metric_group`` listing ``ref:`` links to all global
          attribute/dimension fields used by this plugin's metrics.
        - One ``type: metric`` entry per metric key.

        Attributes and dimensions are NOT defined inline here — they are
        first-class citizens in the global fields file and referenced by key.

        Args:
            plugin_name:          Plugin name, e.g. ``warehouse_usage``.
            plugin_metric_entries: Dict of ``{key: meta}`` for this plugin's
                                   metrics section entries only.

        Returns:
            Semconv-compliant YAML document dict.
        """
        plugin_title = plugin_name.replace("_", " ").title()
        plugin_title = _restore_acronyms(plugin_title)

        groups: List[Dict[str, Any]] = []

        # metric_group header — refs to standard global fields used by this plugin
        standard_refs = [{"ref": k} for k in sorted(KNOWN_REFS)]
        metric_group: Dict[str, Any] = {
            "id": f"snowflake.metrics.{plugin_name}",
            "type": "metric_group",
            "title": f"Snowflake {plugin_title} metrics",
            "brief": f"Metrics collected by the DSOA {plugin_name} plugin.",
            "attributes": standard_refs,
        }
        groups.append(metric_group)

        # Individual metric definitions
        for key in sorted(plugin_metric_entries):
            groups.append(self._build_metric_node(key, plugin_metric_entries[key]))

        return {"groups": groups}

    def _build_metric_node(self, key: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Build a metric definition node.

        Args:
            key:  Metric key.
            meta: Entry metadata dict.

        Returns:
            Semconv-compliant metric dict.
        """
        self._counters["new"] += 1
        return _emit_metric_entry(key, meta["entry"])

    ##endregion

    ##region Schema validation

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """Load the semconv JSON schema if available.

        Returns:
            Parsed JSON schema dict, or ``None`` if not found.
        """
        if not self.schema_path or not self.schema_path.exists():
            log.warning("semconv.schema.json not found at %s; skipping schema validation", self.schema_path)
            return None
        import json  # pylint: disable=import-outside-toplevel

        with open(self.schema_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _validate_against_schema(self, doc: Dict[str, Any], yaml_path: Path) -> bool:
        """Validate a generated YAML document against semconv.schema.json.

        Args:
            doc:       Parsed YAML document to validate.
            yaml_path: File path used for error messages.

        Returns:
            ``True`` if validation passed (or schema unavailable), ``False`` on error.
        """
        if self._schema is None:
            return True
        try:
            import jsonschema  # pylint: disable=import-outside-toplevel

            jsonschema.validate(instance=doc, schema=self._schema)
            log.debug("Schema validation PASS: %s", yaml_path)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Schema validation FAIL: %s — %s", yaml_path, exc)
            return False

    ##endregion

    ##region File writing

    def _write_yaml(self, doc: Dict[str, Any], rel_path: str) -> Path:
        """Write a YAML document to the output directory.

        Args:
            doc:      YAML-serialisable dict.
            rel_path: Relative path under ``output_dir``.

        Returns:
            Absolute path to the written file.
        """
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            yaml.dump(doc, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    ##endregion

    ##region Main export

    def export(self) -> Dict[str, int]:
        """Run the full semantic dictionary export pipeline.

        Steps:
        1. Discover all instruments-def.yml files.
        2. Parse and validate each file.
        3. Group entries into global and per-plugin buckets.
        4. Emit YAML files.
        5. Validate output against semconv.schema.json.
        6. Return summary counters.

        Returns:
            Dict with keys ``files``, ``ref``, ``new``, ``deprecated_alias``, ``otel_only``.

        Raises:
            ExportError: If any required metadata is missing or a fatal error occurs.
        """
        ##region Step 1: Discovery
        files = self._discover_files()
        if not files:
            raise ExportError("No instruments-def.yml files found")
        ##endregion

        ##region Step 2: Parse + validate all files
        all_errors: List[str] = []
        all_entries: Dict[str, Any] = {}

        for plugin_name, path in files:
            log.info("Parsing %s (%s)", plugin_name, path)
            errors, entries = self._parse_file(plugin_name, path)
            all_errors.extend(errors)
            # De-duplicate: first occurrence wins; warn on conflict
            for key, meta in entries.items():
                if key in all_entries:
                    log.warning(
                        "Duplicate field key '%s' in %s (first seen in %s); using first", key, plugin_name, all_entries[key]["plugin"]
                    )
                else:
                    all_entries[key] = meta

        if all_errors:
            error_text = "\n".join(all_errors)
            raise ExportError(f"Validation errors found:\n{error_text}")
        ##endregion

        ##region Step 3: Group entries
        global_entries, plugin_entries = self._group_entries(all_entries)
        log.info("Global fields: %d; Plugin groups: %d", len(global_entries), len(plugin_entries))
        ##endregion

        ##region Step 4: Load schema
        self._schema = self._load_schema()
        ##endregion

        ##region Step 5: Emit global fields YAML
        if global_entries:
            doc = self._build_global_yaml(global_entries)
            path_out = self._write_yaml(doc, "fields/snowflake/snowflake_global.yaml")
            self._validate_against_schema(doc, path_out)
        ##endregion

        ##region Step 6: Emit per-plugin YAML files
        for plugin_name in sorted(plugin_entries):
            entries = plugin_entries[plugin_name]
            if not entries:
                continue
            doc = self._build_plugin_yaml(plugin_name, entries)
            rel = f"model/smartscape/db/snowflake/metrics/snowflake_{plugin_name}.yaml"
            path_out = self._write_yaml(doc, rel)
            self._validate_against_schema(doc, path_out)
        ##endregion

        return dict(self._counters)

    ##endregion


##endregion


##region CLI entry point


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to ``sys.argv``).

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="Export DSOA instruments-def.yml files as Semantic Dictionary YAML.")
    parser.add_argument(
        "--output",
        default="build/_semdict/source",
        help="Output directory for generated YAML files (default: build/_semdict/source)",
    )
    parser.add_argument(
        "--schema",
        default="_otel-build-tool/semantic-conventions/semconv.schema.json",
        help="Path to semconv.schema.json for validation",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for the semantic export tool.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv``).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output) if Path(args.output).is_absolute() else repo_root / args.output
    schema_path = Path(args.schema) if Path(args.schema).is_absolute() else repo_root / args.schema

    log.info("Repo root : %s", repo_root)
    log.info("Output dir: %s", output_dir)

    exporter = SemanticExporter(repo_root=repo_root, output_dir=output_dir, schema_path=schema_path)

    try:
        summary = exporter.export()
    except ExportError as exc:
        log.error("Export failed: %s", exc)
        return 1

    total = summary["ref"] + summary["new"] + summary["deprecated_alias"] + summary["otel_only"]
    print("✓ Export complete")
    print(f"Files generated : {summary['files']}")
    print(f"Total fields    : {total}")
    print(f"  - ref               : {summary['ref']}")
    print(f"  - new               : {summary['new']}")
    print(f"  - deprecated-alias  : {summary['deprecated_alias']}")
    print(f"  - otel-only         : {summary['otel_only']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

##endregion

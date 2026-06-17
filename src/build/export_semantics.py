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
    event_timestamps section         → model/dsoa/ + signal_fields (timestamp fields)

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
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

##region Constants

#: Fields that already exist in the Dynatrace Semantic Dictionary (emit as ref: only).
#: Note: db.system is in OTel semconv but NOT yet in the SD as a global field.
#: It is annotated __semdict: otel-only in instruments-def and emitted as id:.
KNOWN_REFS = {
    "host.name",
    "service.name",
    "telemetry.exporter.name",
    "telemetry.exporter.version",
    "db.query.text",
    "event.id",
    "authentication.type",
}

#: Keys present on every DSOA telemetry record — synced with config.py RESOURCE_ATTRIBUTES.
RESOURCE_ATTRIBUTE_KEYS: Set[str] = {
    "db.system",
    "service.name",
    "deployment.environment",
    "host.name",
    "telemetry.exporter.version",
    "telemetry.exporter.name",
    "dsoa.run.id",
    "dsoa.run.context",
    "dsoa.run.plugin",
    "deployment.environment.tag",
}

#: Dimension keys covered by the i.dsoa_warehouse interface.
INTERFACE_WAREHOUSE_KEYS: Set[str] = {"snowflake.warehouse.name", "snowflake.warehouse.id"}

#: Dimension keys covered by the i.dsoa_database interface.
INTERFACE_DATABASE_KEYS: Set[str] = {"db.namespace", "snowflake.schema.name"}

#: Valid __field_type override values.
VALID_FIELD_TYPES = {"resource", "signal"}

#: Acronyms that must stay ALL-CAPS in display_name (longer tokens first).
DISPLAY_NAME_ACRONYMS = ("DSOA", "OTel", "DDL", "DML", "RSS", "URL", "API", "ID", "DB", "QA", "SQL")

#: instruments-def unit value → SD-valid unit abbreviation.
#: Sources: .context/otel-build-tool/semantic-conventions/src/opentelemetry/semconv/units/unit_registry.py
#: and juno_docs/define-data-in-grail/definition/yaml/attribute/units.md
#: Note: OTel UCUM curly-brace annotations ({request}, {partition}, etc.) are NOT in
#: the SD unit registry — use 'count' for such domain-specific counting units.
UNIT_MAP: Dict[str, str] = {
    # Data — UCUM abbreviation required
    "bytes": "By",
    "Byte": "By",
    # Time
    "days": "d",
    "seconds": "s",
    # Percentage
    "percent": "%",
    # Dimensionless
    "factor": "1",
    # Domain-specific counts — map to 'count' (SD Unspecified category)
    "rows": "count",
    "files": "count",
    "clusters": "count",
    "queries": "count",
    "warehouses": "count",
    "partitions": "count",
    "credits": "count",
    # Currency — use ISO/SD abbreviation
    "currency": "US$",
}

#: Units that should carry a note explaining the original source unit when mapped to 'count'.
#: This preserves the semantic context that is lost by collapsing domain units to 'count'.
UNIT_NOTE_ORIGINALS: Set[str] = {
    "rows",
    "files",
    "clusters",
    "queries",
    "warehouses",
    "partitions",
    "credits",
}

#: instruments-def __type → semconv instrument.
METRIC_TYPE_MAP: Dict[str, str] = {
    "gauge": "gauge",
    "count": "counter",
    "counter": "counter",
    "updowncounter": "updowncounter",
    "histogram": "histogram",
}

#: instruments-def __type → semconv attribute type.
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

# (prefix, group_id, group_type) for signal fields — order matters (longest prefix first).
# All DSOA-owned signal groups use type: attribute_group — they appear on multiple signal
# types (logs + spans + events) and are not canonically span-wire-format fields.
# See IA guidance: type:span is reserved for groups whose semantics are exclusively
# span/trace wire-format (HTTP, RPC). Using it for DSOA fields would be incorrect.
# TODO(BIZOBS-151-IA): Re-evaluate after @information-architect review of span semantics.
_SIG_NS: List[Tuple[str, str, str]] = [
    ("snowflake.warehouse", "snowflake.warehouse", "attribute_group"),
    ("snowflake.query", "snowflake.query", "attribute_group"),
    ("snowflake.time", "snowflake.time", "attribute_group"),
    ("snowflake.object", "snowflake.object", "attribute_group"),
    ("snowflake.user", "snowflake.user", "attribute_group"),
    ("snowflake.session", "snowflake.session", "attribute_group"),
    ("snowflake.error", "snowflake.error", "attribute_group"),
    ("snowflake.data", "snowflake.data", "attribute_group"),
    ("snowflake.table", "snowflake.table", "attribute_group"),
    ("snowflake.pipe", "snowflake.pipe", "attribute_group"),
    ("snowflake.task", "snowflake.task", "attribute_group"),
    ("snowflake.share", "snowflake.share", "attribute_group"),
    ("snowflake.role", "snowflake.role", "attribute_group"),
    ("snowflake.database", "snowflake.database", "attribute_group"),
    ("snowflake.schema", "snowflake.schema", "attribute_group"),
    ("snowflake.credits", "snowflake.credits", "attribute_group"),
    ("snowflake.resource_monitor", "snowflake.resource_monitor", "attribute_group"),
    ("snowflake.budget", "snowflake.budget", "attribute_group"),
    ("snowflake.event", "snowflake.event", "attribute_group"),
    ("snowflake.acceleration", "snowflake.acceleration", "attribute_group"),
    ("snowflake.load", "snowflake.load", "attribute_group"),
    ("snowflake.rows", "snowflake.rows", "attribute_group"),
    ("snowflake.partitions", "snowflake.partitions", "attribute_group"),
    ("snowflake.warehouses", "snowflake.warehouses", "attribute_group"),
    ("snowflake.cost", "snowflake.cost", "attribute_group"),
    ("snowflake.external", "snowflake.external", "attribute_group"),
    ("snowflake.release", "snowflake.release", "attribute_group"),
    ("snowflake.cluster", "snowflake.cluster", "attribute_group"),
    ("snowflake.service", "snowflake.service", "attribute_group"),
    ("snowflake.secondary", "snowflake.secondary", "attribute_group"),
    ("snowflake.trust_center", "snowflake.trust_center", "attribute_group"),
    ("client", "client", "attribute_group"),
    ("db", "db", "attribute_group"),
    ("authentication", "authentication", "attribute_group"),
    ("session", "session", "attribute_group"),
    ("plugins", "plugins", "attribute_group"),
    ("error", "error", "attribute_group"),
    ("status", "status", "attribute_group"),
    ("event", "event", "attribute_group"),
    ("vulnerability", "vulnerability", "attribute_group"),
]

# (prefix, group_id, group_type) for resource fields.
_RES_NS: List[Tuple[str, str, str]] = [
    # DSOA execution metadata — always resource (in RESOURCE_ATTRIBUTE_KEYS)
    ("dsoa", "dsoa", "resource"),
    ("deployment", "deployment", "resource"),
    # snowflake.* fields that may be marked __field_type: resource by annotation
    # (e.g. snowflake.warehouse.size, snowflake.warehouse.type when they describe
    # a stable property of the warehouse resource rather than per-event context)
    # NOTE: group IDs use a ".resource" suffix to avoid collision with the signal-field
    # attribute_groups of the same namespace (snowflake.warehouse and db) defined in _SIG_NS.
    ("snowflake.warehouse", "snowflake.warehouse.resource", "resource"),
    ("snowflake.resource_monitor", "snowflake.resource_monitor", "resource"),
    ("snowflake.account", "snowflake.account", "resource"),
    ("snowflake.org", "snowflake.account", "resource"),
    ("db", "db.resource", "resource"),
]

##endregion

log = logging.getLogger(__name__)


##region Data structures


class ExportError(Exception):
    """Raised when export encounters a fatal validation error."""


##endregion


##region Pure helpers


def _restore_acronyms(text: str) -> str:
    """Restore known acronyms to ALL-CAPS in a title-cased string.

    Args:
        text: Title-cased string.

    Returns:
        String with acronyms restored.
    """
    words = text.split(" ")
    restored = []
    for word in words:
        suffix = ""
        stem = word
        if word and not word[-1].isalnum():
            suffix = word[-1]
            stem = word[:-1]
        match = next((a for a in DISPLAY_NAME_ACRONYMS if a.lower() == stem.lower()), None)
        restored.append((match if match else stem) + suffix)
    return " ".join(restored)


def _make_display_name(key: str) -> str:
    """Convert dot-notation key to human-readable display name.

    Args:
        key: Dot-notation field key.

    Returns:
        Human-readable display name with acronyms preserved.
    """
    parts = key.replace("_", " ").replace("-", " ").replace(".", " ").split()
    return _restore_acronyms(" ".join(p.title() for p in parts))


def _map_attr_type(raw_type: Optional[str]) -> str:
    """Map instruments-def __type to semconv attribute type string.

    Args:
        raw_type: Raw __type value or None.

    Returns:
        Semconv type string (default ``"string"``).
    """
    if not raw_type:
        return "string"
    return ATTR_TYPE_MAP.get(str(raw_type).lower(), "string")


def _map_metric_instrument(raw_type: Optional[str]) -> str:
    """Map instruments-def __type to semconv instrument string.

    Args:
        raw_type: Raw __type value or None.

    Returns:
        Semconv instrument string (default ``"gauge"``).
    """
    if not raw_type:
        return "gauge"
    mapped = METRIC_TYPE_MAP.get(str(raw_type).lower())
    if not mapped:
        log.warning("Unknown metric __type '%s'; defaulting to gauge", raw_type)
        return "gauge"
    return mapped


def _classify_field(key: str, section: str, field_type_override: Optional[str]) -> str:
    """Determine the SD bucket for a field.

    SD definition (source/readme.md):
    - Resource field: stable for the **lifetime of the resource** (host, process,
      container, cloud). Must be present on ALL signals from that resource.
    - Signal field: present on a single signal event. Everything that does not
      meet the resource field definition.

    For DSOA the "resource" is the Snowflake account / agent instance.  Only
    the fields in ``RESOURCE_ATTRIBUTE_KEYS`` (synced with config.py
    ``RESOURCE_ATTRIBUTES``) are stable for the agent's lifetime.  Metric
    dimensions such as ``snowflake.warehouse.name``, ``db.namespace``, and
    ``db.user`` vary per observation — they are signal fields even though
    DSOA uses them as low-cardinality metric-splitting dimensions.

    Args:
        key:                 Dot-notation field key.
        section:             instruments-def section name.
        field_type_override: Value of ``__field_type`` or None.

    Returns:
        One of ``"resource"``, ``"signal"``, ``"metric"``, ``"event_timestamp"``.
    """
    if section == "metrics":
        return "metric"
    if section == "event_timestamps":
        return "event_timestamp"
    # Explicit override always wins
    if field_type_override == "resource":
        return "resource"
    if field_type_override == "signal":
        return "signal"
    # Keys that are on EVERY DSOA record and stable for the agent lifetime
    if key in RESOURCE_ATTRIBUTE_KEYS:
        return "resource"
    # Everything else — including metric dimensions — is a signal field
    return "signal"


def _ns_group(key: str, ns_map: List[Tuple[str, str, str]], default_id: str, default_type: str) -> Tuple[str, str]:
    """Map a field key to (group_id, group_type) via prefix matching.

    Args:
        key:          Dot-notation field key.
        ns_map:       Ordered list of (prefix, group_id, group_type) tuples.
        default_id:   Default group_id when no prefix matches.
        default_type: Default group_type when no prefix matches.

    Returns:
        Tuple of (group_id, group_type).
    """
    for prefix, group_id, group_type in ns_map:
        if key.startswith(prefix + ".") or key == prefix:
            return group_id, group_type
    return default_id, default_type


def _merge_field_entries(key: str, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two definitions of the same field key, preferring richer enum metadata.

    Rules:
    - If only incoming has ``__enum``: upgrade existing to the incoming (enum-rich) definition.
    - If both have ``__enum``: union members by value (first-seen wins for duplicate values);
      ``allow_custom_values`` = logical OR of both.
    - Otherwise: keep existing (first-seen wins, no enum to merge).

    Args:
        key:      Field key name (for logging).
        existing: Current winning definition dict (has keys: entry, plugin, section, …).
        incoming: New challenger definition dict.

    Returns:
        The winning definition after merge.
    """
    existing_enum = existing["entry"].get("__enum")
    incoming_enum = incoming["entry"].get("__enum")

    if existing_enum is None and incoming_enum is not None:
        # Upgrade: incoming has enum info that existing is missing
        log.debug("Enum upgrade for '%s': replacing no-enum definition from %s with enum-rich one from %s", key, existing["plugin"], incoming["plugin"])
        return incoming

    if existing_enum is not None and incoming_enum is not None:
        # Union: merge members, OR the allow_custom_values flag
        seen_values: Set[str] = {m["value"] for m in existing_enum.get("members", [])}
        merged_members = list(existing_enum.get("members", []))
        for m in incoming_enum.get("members", []):
            if m["value"] not in seen_values:
                merged_members.append(m)
                seen_values.add(m["value"])
        merged_allow = bool(existing_enum.get("allow_custom_values", True)) or bool(incoming_enum.get("allow_custom_values", True))
        merged_enum = {"allow_custom_values": merged_allow, "members": merged_members}
        # Return a copy of existing with the merged enum injected
        merged_entry = dict(existing["entry"])
        merged_entry["__enum"] = merged_enum
        merged_meta = dict(existing)
        merged_meta["entry"] = merged_entry
        log.debug("Enum union for '%s': merged %d member(s) from %s into %s", key, len(merged_members), incoming["plugin"], existing["plugin"])
        return merged_meta

    # No enum to merge — keep existing (first-seen wins)
    log.debug("Duplicate key '%s' in %s (first in %s); using first definition", key, incoming["plugin"], existing["plugin"])
    return existing


##endregion


##region Validation


def _validate_entry(key: str, entry: Dict[str, Any], section: str, source_file: str) -> List[str]:
    """Validate a single instruments-def entry for required semdict metadata.

    Args:
        key:         Field key.
        entry:       Entry metadata dict.
        section:     Section name.
        source_file: Path string for error messages.

    Returns:
        List of error strings (empty when validation passes).
    """
    errors: List[str] = []
    if not entry.get("__description"):
        errors.append(f"[{source_file}] {section}.{key}: missing __description")
    if entry.get("__example") is None:
        errors.append(f"[{source_file}] {section}.{key}: missing __example")
    semdict = entry.get("__semdict", "new")
    if semdict == "deprecated-alias" and not entry.get("__otel_replacement"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: deprecated-alias requires __otel_replacement")
    if semdict == "otel-only" and not entry.get("__semdict_note"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: otel-only requires __semdict_note")
    field_type = entry.get("__field_type")
    if field_type is not None and field_type not in VALID_FIELD_TYPES:
        errors.append(f"[{source_file}] {section}.{key}: unknown __field_type '{field_type}'")
    return errors


##endregion


##region Emit helpers


def _emit_ref_entry(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a ref: attribute entry.

    Args:
        key:   Field key to reference.
        entry: Source entry (used for optional semdict_note).

    Returns:
        Dict with ``ref`` key and optional ``note``.
    """
    node: Dict[str, Any] = {"ref": key}
    note = entry.get("__semdict_note")
    if note:
        node["note"] = str(note).strip()
    return node


def _build_type_node(entry: Dict[str, Any]) -> Any:
    """Build the ``type:`` value — enum dict when __enum present, else type string.

    Args:
        entry: instruments-def entry dict.

    Returns:
        Type string or enum dict.
    """
    enum_def = entry.get("__enum")
    if enum_def:
        members = []
        for m in enum_def.get("members", []):
            member: Dict[str, Any] = {"id": m["id"], "value": m["value"], "brief": m["brief"]}
            if "display_name" in m:
                member["display_name"] = m["display_name"]
            members.append(member)
        return {"allow_custom_values": bool(enum_def.get("allow_custom_values", True)), "members": members}
    return _map_attr_type(entry.get("__type"))


def _emit_id_entry(key: str, entry: Dict[str, Any], semdict_flag: str) -> Dict[str, Any]:
    """Build a full id: attribute definition block.

    Args:
        key:          Field key.
        entry:        instruments-def entry dict.
        semdict_flag: ``new``, ``deprecated-alias``, or ``otel-only``.

    Returns:
        Dict with all required semconv attribute fields.
    """
    attr_type = _build_type_node(entry)
    description = str(entry["__description"]).strip()
    example_raw = entry.get("__example", "")
    if example_raw is None:
        example_raw = ""
    examples = (
        [_coerce_attribute_example(example_raw)]
        if not isinstance(example_raw, list)
        else [_coerce_attribute_example(e) for e in example_raw]
    )
    node: Dict[str, Any] = {
        "id": key,
        "display_name": _make_display_name(key),
        "type": attr_type,
        "stability": "experimental",
        "brief": description,
        "examples": examples,
    }
    if semdict_flag == "deprecated-alias":
        replacement = entry.get("__otel_replacement", "")
        otel_note = entry.get("__semdict_note", "")
        warning = f"OTel renamed this field to {replacement}. DSOA continues to emit it for backward compatibility."
        if otel_note:
            warning = f"{otel_note} DSOA continues to emit it for backward compatibility."
        node["note"] = warning
    elif entry.get("__semdict_note"):
        node["note"] = str(entry["__semdict_note"]).strip()
    return node


def _coerce_metric_example(value: Any) -> Any:
    """Coerce a metric example value to a numeric type.

    Metric examples must be numbers (int or float), not strings.
    instruments-def stores examples as strings (YAML scalar); convert back.

    Args:
        value: Raw example value from instruments-def.

    Returns:
        int or float if parseable, otherwise the original value.
    """
    if isinstance(value, (int, float)):
        return value
    try:
        as_str = str(value).strip()
        if "." in as_str:
            return float(as_str)
        return int(as_str)
    except (ValueError, TypeError):
        return value


def _coerce_attribute_example(value: Any) -> str:
    """Coerce an attribute example value to a string suitable for semconv ``examples:``.

    Handles Python booleans produced by YAML ``true``/``false`` scalars so that
    ``True`` → ``"true"`` and ``False`` → ``"false"`` (lowercase, per semconv convention).
    All other values are converted with ``str()``.

    Args:
        value: Raw example value from instruments-def.

    Returns:
        String representation of the example.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _emit_metric_entry(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a type: metric group entry.

    Args:
        key:   Metric key.
        entry: instruments-def metric entry.

    Returns:
        Dict representing a semconv metric definition.
    """
    instrument = _map_metric_instrument(entry.get("__type"))
    description = str(entry.get("__description", "")).strip()
    example_raw = entry.get("__example", "0")
    raw_list = example_raw if isinstance(example_raw, list) else [example_raw]
    examples = [_coerce_metric_example(e) for e in raw_list]
    raw_unit = entry.get("unit") or entry.get("__unit")
    if not raw_unit:
        log.warning("Metric '%s' has no unit; omitting unit field", key)
    # Strip surrounding quotes that may appear in YAML (e.g. unit: "1" → 1)
    raw_unit_str = str(raw_unit).strip('"').strip("'") if raw_unit else None
    mapped_unit = UNIT_MAP.get(raw_unit_str, raw_unit_str) if raw_unit_str else None
    if raw_unit_str and mapped_unit != raw_unit_str:
        log.debug("Metric '%s': unit '%s' → '%s'", key, raw_unit_str, mapped_unit)
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
    if mapped_unit:
        node["unit"] = mapped_unit
    # Build note: start from __semdict_note (if any), then append original-unit note for
    # domain-specific units that were collapsed to 'count' (e.g. rows, credits, partitions).
    note_parts = []
    if entry.get("__semdict_note"):
        note_parts.append(str(entry["__semdict_note"]).strip())
    if raw_unit_str and raw_unit_str in UNIT_NOTE_ORIGINALS and mapped_unit == "count":
        note_parts.append(f"Original unit: {raw_unit_str}.")
    if note_parts:
        node["note"] = " ".join(note_parts)
    return node


##endregion


##region SemanticExporter


class SemanticExporter:
    """Reads instruments-def.yml files and emits Semantic Dictionary YAML.

    Attributes:
        repo_root:   Absolute path to the repository root.
        output_dir:  Directory where generated YAML files are written.
        schema_path: Optional path to ``semconv.schema.json`` for validation.
    """

    def __init__(self, repo_root: Path, output_dir: Path, schema_path: Optional[Path] = None) -> None:
        """Initialise the exporter.

        Args:
            repo_root:   Repository root path.
            output_dir:  Output directory (created on demand).
            schema_path: Optional semconv JSON schema for validation.
        """
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.schema_path = schema_path
        self._schema: Optional[Dict[str, Any]] = None
        self._counters: Dict[str, int] = {
            "files": 0,
            "ref": 0,
            "new": 0,
            "deprecated_alias": 0,
            "otel_only": 0,
            "resource_fields": 0,
            "signal_fields": 0,
            "metric_fields": 0,
            "event_timestamp_fields": 0,
        }

    ##region Discovery + Parsing

    def _discover_files(self) -> List[Tuple[str, Path]]:
        """Glob all instruments-def.yml files. Returns list of (plugin_name, path)."""
        files: List[Tuple[str, Path]] = []
        core_file = self.repo_root / "src" / "dtagent.conf" / "instruments-def.yml"
        if core_file.exists():
            files.append(("_core", core_file))
        else:
            log.warning("Core instruments-def.yml not found at %s", core_file)
        for path in sorted(self.repo_root.glob("src/dtagent/plugins/*.config/instruments-def.yml")):
            plugin_name = path.parent.name.replace(".config", "")
            files.append((plugin_name, path))
        log.info("Found %d instruments-def.yml files", len(files))
        return files

    def _parse_file(self, plugin_name: str, path: Path) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """Parse a single instruments-def.yml file.

        Args:
            plugin_name: Plugin name for error messages.
            path:        Path to the file.

        Returns:
            Tuple of (errors, entries).

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
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, raw_entry in (data.get(section) or {}).items():
                entry = raw_entry or {}
                if not isinstance(entry, dict):
                    log.warning("[%s] %s.%s: skipping non-dict entry", plugin_name, section, key)
                    continue
                semdict_flag = entry.get("__semdict", "new")
                if semdict_flag not in VALID_SEMDICT_FLAGS:
                    log.warning("[%s] %s.%s: unknown __semdict '%s'; treating as 'new'", plugin_name, section, key, semdict_flag)
                    semdict_flag = "new"
                if semdict_flag != "ref":
                    errors.extend(_validate_entry(key, entry, section, str(path)))
                if semdict_flag == "ref" and key not in KNOWN_REFS:
                    log.warning("[%s] %s.%s: __semdict: ref but key not in KNOWN_REFS", plugin_name, section, key)
                entries[key] = {
                    "section": section,
                    "semdict": semdict_flag,
                    "plugin": plugin_name,
                    "entry": entry,
                    "classification": _classify_field(key, section, entry.get("__field_type")),
                }
        return errors, entries

    ##endregion

    ##region Grouping

    def _group_entries(
        self, all_entries: Dict[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Separate entries into resource/signal/event_timestamp/metric buckets.

        Args:
            all_entries: All parsed entries keyed by field key.

        Returns:
            Tuple of (resource_entries, signal_entries, event_ts_entries, plugin_metric_entries).
        """
        resource_entries: Dict[str, Any] = {}
        signal_entries: Dict[str, Any] = {}
        event_ts_entries: Dict[str, Any] = {}
        plugin_metric_entries: Dict[str, Dict[str, Any]] = {}
        for key, meta in all_entries.items():
            classification = meta["classification"]
            if classification == "metric":
                plugin_metric_entries.setdefault(meta["plugin"], {})[key] = meta
            elif classification == "event_timestamp":
                event_ts_entries[key] = meta
            elif classification == "resource":
                resource_entries[key] = meta
            else:
                signal_entries[key] = meta
        return resource_entries, signal_entries, event_ts_entries, plugin_metric_entries

    ##endregion

    ##region Attribute node building

    def _build_attribute_node(self, key: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Build a ref: or id: attribute node.

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
        self._counters[
            "deprecated_alias" if semdict_flag == "deprecated-alias" else "otel_only" if semdict_flag == "otel-only" else "new"
        ] += 1
        return node

    ##endregion

    ##region YAML document builders

    def _build_resource_fields_yaml(self, resource_entries: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Build resource_fields/snowflake_resource.yaml and resource_fields/dsoa.yaml.

        Ref entries (``semdict == "ref"``) are intentionally excluded from both output files.
        They belong exclusively in the ``i.dsoa_resource`` interface (emitted by
        ``_build_interfaces_yaml``), which already declares ``{"ref": key}`` for every key
        in ``RESOURCE_ATTRIBUTE_KEYS``.  Including refs here would produce duplicate ``ref:``
        nodes in field definition files, which is incorrect SD structure.

        Args:
            resource_entries: All resource-classified entries.

        Returns:
            Tuple of (snowflake_resource_doc, dsoa_resource_doc).
        """
        # Route to dsoa.yaml: DSOA/deployment-namespaced fields only.
        # Refs go ONLY to the interface (already in _build_interfaces_yaml) — never to field files.
        dsoa_keys = {
            k: v
            for k, v in resource_entries.items()
            if (k.startswith("dsoa.") or k.startswith("deployment.")) and v["semdict"] != "ref"
        }
        snowflake_keys = {
            k: v
            for k, v in resource_entries.items()
            if k not in dsoa_keys and v["semdict"] != "ref"
        }

        sf_groups: Dict[str, Dict[str, Any]] = {}
        for key in sorted(snowflake_keys):
            group_id, group_type = _ns_group(key, _RES_NS, "snowflake.resource", "resource")
            if group_id not in sf_groups:
                sf_groups[group_id] = {"type": group_type, "attrs": []}
            sf_groups[group_id]["attrs"].append(self._build_attribute_node(key, snowflake_keys[key]))
            self._counters["resource_fields"] += 1

        sf_group_list = [
            {
                "id": gid,
                "type": sf_groups[gid]["type"],
                "title": _make_display_name(gid) + " resource fields",
                "brief": f"Resource-level fields describing Snowflake {_make_display_name(gid)} entities.",
                "attributes": sf_groups[gid]["attrs"],
            }
            for gid in sorted(sf_groups)
        ]

        dsoa_attrs = []
        for key in sorted(dsoa_keys):
            dsoa_attrs.append(self._build_attribute_node(key, dsoa_keys[key]))
            self._counters["resource_fields"] += 1

        return (
            {"groups": sf_group_list},
            {
                "groups": [
                    {
                        "id": "dsoa",
                        "type": "resource",
                        "title": "DSOA resource fields",
                        "brief": "Resource-level DSOA execution metadata and deployment context.",
                        "attributes": dsoa_attrs,
                    }
                ]
            },
        )

    def _build_signal_fields_yaml(self, signal_entries: Dict[str, Any], event_ts_entries: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Build one signal_fields YAML file per namespace group.

        Each namespace group (snowflake.query, snowflake.user, etc.) gets its own
        file under ``fields/signal_fields/`` for easier review and future maintenance.
        Groups that share no natural prefix fall into ``snowflake_misc.yaml``.

        Args:
            signal_entries:   Signal-classified entries.
            event_ts_entries: Event-timestamp entries (excluding trigger key).

        Returns:
            Dict mapping relative path → YAML doc dict.
        """
        all_signal = dict(signal_entries)
        for key, meta in event_ts_entries.items():
            if key != "snowflake.event.trigger":
                all_signal[key] = meta

        groups_map: Dict[str, Dict[str, Any]] = {}
        for key in sorted(all_signal):
            group_id, group_type = _ns_group(key, _SIG_NS, "snowflake.misc", "attribute_group")
            if group_id not in groups_map:
                groups_map[group_id] = {"type": group_type, "attrs": []}
            groups_map[group_id]["attrs"].append(self._build_attribute_node(key, all_signal[key]))
            self._counters["signal_fields"] += 1

        # One file per group_id — replace dots with underscores for filenames
        docs: Dict[str, Dict[str, Any]] = {}
        for gid in sorted(groups_map):
            filename = gid.replace(".", "_") + ".yaml"
            doc = {
                "groups": [
                    {
                        "id": gid,
                        "type": groups_map[gid]["type"],
                        "title": _make_display_name(gid) + " signal fields",
                        "brief": f"Signal-level fields for {_make_display_name(gid)} telemetry.",
                        "attributes": groups_map[gid]["attrs"],
                    }
                ]
            }
            docs[f"fields/signal_fields/{filename}"] = doc
        return docs

    def _build_interfaces_yaml(self) -> Dict[str, Any]:
        """Build metrics/interfaces_dsoa.yaml with i.dsoa_resource/warehouse/database.

        Returns:
            Semconv-compliant YAML doc dict.
        """
        return {
            "groups": [
                {
                    "id": "i.dsoa_resource",
                    "type": "interface",
                    "title": "DSOA resource fields",
                    "brief": "Fields present on all DSOA telemetry records. Synced with config.py RESOURCE_ATTRIBUTES.",
                    "attributes": [{"ref": k} for k in sorted(RESOURCE_ATTRIBUTE_KEYS)],
                },
                {
                    "id": "i.dsoa_warehouse",
                    "type": "interface",
                    "title": "DSOA warehouse dimension fields",
                    "brief": "Common warehouse dimensions for per-warehouse metrics.",
                    "attributes": [{"ref": "snowflake.warehouse.name"}, {"ref": "snowflake.warehouse.id"}],
                },
                {
                    "id": "i.dsoa_database",
                    "type": "interface",
                    "title": "DSOA database dimension fields",
                    "brief": "Common database/schema dimensions for per-database metrics.",
                    "attributes": [{"ref": "db.namespace"}, {"ref": "snowflake.schema.name"}],
                },
            ]
        }

    def _select_interfaces(
        self, metric_entries: Dict[str, Any], all_entries: Dict[str, Any], dim_plugins: Optional[Dict[str, Set[str]]] = None
    ) -> List[str]:
        """Determine which DSOA interfaces to declare for a metric model.

        Args:
            metric_entries: Per-plugin metric entries.
            all_entries:    All parsed entries (for dimension lookup).
            dim_plugins:    Map of dimension key → set of all plugins that define it.
                            When provided, a dim without ``__context_names`` is accepted
                            for a plugin if that plugin is in ``dim_plugins[dim_key]``,
                            not only if the dedup winner happened to be that plugin.

        Returns:
            Ordered list of interface IDs.
        """
        uses_warehouse = uses_database = False
        for _mk, m_meta in metric_entries.items():
            mc_names = set(m_meta["entry"].get("__context_names") or [])
            m_plugin = m_meta["plugin"]
            for dim_key, dim_meta in all_entries.items():
                # Interface selection uses DSOA dimensions (section == "dimensions")
                # not SD classification — same reasoning as metric dim resolution.
                if dim_meta["section"] != "dimensions":
                    continue
                dc_names = set(dim_meta["entry"].get("__context_names") or [])
                # A dim with context_names is applicable only when it overlaps the metric.
                # A dim WITHOUT context_names is applicable if the plugin defined the dim
                # in any of its own instruments-def files (per dim_plugins map), or —
                # when dim_plugins is not provided — only if the dedup winner was this plugin.
                if dc_names:
                    if not dc_names.intersection(mc_names):
                        continue
                else:
                    if dim_plugins is not None:
                        if m_plugin not in dim_plugins.get(dim_key, set()):
                            continue
                    else:
                        if dim_meta["plugin"] != m_plugin:
                            continue
                if dim_key in INTERFACE_WAREHOUSE_KEYS:
                    uses_warehouse = True
                if dim_key in INTERFACE_DATABASE_KEYS:
                    uses_database = True
        interfaces = ["i.dsoa_resource"]
        if uses_warehouse:
            interfaces.append("i.dsoa_warehouse")
        if uses_database:
            interfaces.append("i.dsoa_database")
        return interfaces

    def _build_metric_model_yaml(
        self,
        plugin_name: str,
        metric_entries: Dict[str, Any],
        all_entries: Dict[str, Any],
        dim_plugins: Optional[Dict[str, Set[str]]] = None,
    ) -> Dict[str, Any]:
        """Build a per-plugin metric model YAML document.

        Args:
            plugin_name:    Plugin name.
            metric_entries: Plugin's metric entries.
            all_entries:    All parsed entries for dimension resolution.
            dim_plugins:    Map of dimension key → set of all plugins that define it.
                            When provided, dimensions are resolved by ownership across all
                            plugin definitions, not just the dedup winner.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_title = _restore_acronyms(plugin_name.replace("_", " ").title())
        interfaces = self._select_interfaces(metric_entries, all_entries, dim_plugins)
        covered: Set[str] = set(RESOURCE_ATTRIBUTE_KEYS)
        if "i.dsoa_warehouse" in interfaces:
            covered |= INTERFACE_WAREHOUSE_KEYS
        if "i.dsoa_database" in interfaces:
            covered |= INTERFACE_DATABASE_KEYS

        groups = []
        for metric_key in sorted(metric_entries):
            m_meta = metric_entries[metric_key]
            mc_names = set(m_meta["entry"].get("__context_names") or [])
            m_plugin = m_meta["plugin"]
            dim_refs = []
            for dim_key in sorted(all_entries):
                dim_meta = all_entries[dim_key]
                # Metric attributes: list contains DSOA dimensions (section == "dimensions")
                # regardless of SD resource/signal classification.  Dimensions are the
                # low-cardinality metric-splitting fields; attributes section fields are
                # high-cardinality per-event context and must NOT appear in metrics.
                if dim_meta["section"] != "dimensions":
                    continue
                if dim_key in covered:
                    continue
                dc_names = set(dim_meta["entry"].get("__context_names") or [])
                # A dim with context_names is applicable only when it overlaps the metric.
                # A dim WITHOUT context_names is applicable if the plugin defined the dim
                # in any of its own instruments-def files (per dim_plugins map), or —
                # when dim_plugins is not provided — only if the dedup winner was this plugin.
                if dc_names:
                    if not dc_names.intersection(mc_names):
                        continue
                else:
                    if dim_plugins is not None:
                        if m_plugin not in dim_plugins.get(dim_key, set()):
                            continue
                    else:
                        if dim_meta["plugin"] != m_plugin:
                            continue
                dim_refs.append({"ref": dim_key})
            metric_node = _emit_metric_entry(metric_key, m_meta["entry"])
            if dim_refs:
                metric_node["attributes"] = dim_refs
            groups.append(metric_node)
            self._counters["metric_fields"] += 1

        return {
            "model": {
                "id": f"dsoa.metrics.{plugin_name}",
                "title": f"Snowflake {plugin_title} Metrics",
                "brief": f"Metrics collected by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
                "model_group_id": "dsoa.metrics",
                "data_object": "metric",
                "interfaces": interfaces,
                "groups": groups,
            }
        }

    def _build_event_model_yaml(self, plugin_name: str, event_ts_entries: Dict[str, Any]) -> Dict[str, Any]:
        """Build a per-plugin event model YAML document.

        Args:
            plugin_name:      Plugin name.
            event_ts_entries: All event_timestamp entries across all plugins.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_title = _restore_acronyms(plugin_name.replace("_", " ").title())
        plugin_ts_keys = sorted(
            k for k, meta in event_ts_entries.items() if meta["plugin"] == plugin_name and k != "snowflake.event.trigger"
        )
        attrs = [{"ref": "snowflake.event.type"}] + [{"ref": k} for k in plugin_ts_keys]
        for _ in plugin_ts_keys:
            self._counters["event_timestamp_fields"] += 1
        return {
            "model": {
                "id": f"dsoa.events.{plugin_name}",
                "title": f"Snowflake {plugin_title} Lifecycle Events",
                "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin as business events.",
                "model_group_id": "dsoa.events",
                "data_object": "bizevents",
                "interfaces": ["i.dsoa_resource"],
                "groups": [
                    {
                        "id": f"dsoa.events.{plugin_name}.fields",
                        "type": "attribute_group",
                        "title": f"{plugin_title} event fields",
                        "attributes": attrs,
                    }
                ],
            }
        }

    ##endregion

    ##region Schema validation

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """Load semconv JSON schema if available.

        Returns:
            Parsed schema dict or None.
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
            doc:       Parsed YAML document.
            yaml_path: Path for error messages.

        Returns:
            True if valid (or schema unavailable), False on error.
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
            rel_path: Relative path under output_dir.

        Returns:
            Absolute path to the written file.
        """
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            yaml.dump(doc, fh, default_flow_style=False, allow_unicode=True, sort_keys=False, width=200)
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    ##endregion

    ##region Main export

    def export(self) -> Dict[str, int]:
        """Run the full semantic dictionary export pipeline.

        Returns:
            Dict with counter keys: ``files``, ``ref``, ``new``,
            ``deprecated_alias``, ``otel_only``, ``resource_fields``,
            ``signal_fields``, ``metric_fields``, ``event_timestamp_fields``.

        Raises:
            ExportError: On missing metadata or parse failure.
        """
        # Step 1: Discovery
        files = self._discover_files()
        if not files:
            raise ExportError("No instruments-def.yml files found")

        # Step 2: Parse + validate
        all_errors: List[str] = []
        all_entries: Dict[str, Any] = {}
        dim_plugins: Dict[str, Set[str]] = {}
        for plugin_name, path in files:
            log.debug("Parsing %s (%s)", plugin_name, path)
            errors, entries = self._parse_file(plugin_name, path)
            all_errors.extend(errors)
            for key, meta in entries.items():
                # Track all plugins that define each dimension key (for A3 ownership)
                if meta["section"] == "dimensions":
                    dim_plugins.setdefault(key, set()).add(plugin_name)
                if key in all_entries:
                    all_entries[key] = _merge_field_entries(key, all_entries[key], meta)
                else:
                    all_entries[key] = meta
        if all_errors:
            raise ExportError("Validation errors found:\n" + "\n".join(all_errors))

        # Step 3: Group
        resource_entries, signal_entries, event_ts_entries, plugin_metric_entries = self._group_entries(all_entries)
        log.info(
            "Resource: %d  Signal: %d  EventTS: %d  PluginMetricGroups: %d",
            len(resource_entries),
            len(signal_entries),
            len(event_ts_entries),
            len(plugin_metric_entries),
        )

        # Step 4: Load schema
        self._schema = self._load_schema()

        # Step 5: resource_fields
        sf_res_doc, dsoa_res_doc = self._build_resource_fields_yaml(resource_entries)
        if sf_res_doc.get("groups"):
            p = self._write_yaml(sf_res_doc, "fields/resource_fields/snowflake_resource.yaml")
            self._validate_against_schema(sf_res_doc, p)
        if dsoa_res_doc.get("groups") and dsoa_res_doc["groups"][0].get("attributes"):
            p = self._write_yaml(dsoa_res_doc, "fields/resource_fields/dsoa.yaml")
            self._validate_against_schema(dsoa_res_doc, p)

        # Step 6: signal_fields — one file per namespace group
        sig_docs = self._build_signal_fields_yaml(signal_entries, event_ts_entries)
        for rel_path, sig_doc in sig_docs.items():
            if sig_doc.get("groups"):
                p = self._write_yaml(sig_doc, rel_path)
                self._validate_against_schema(sig_doc, p)

        # Step 7: interfaces + model group
        p = self._write_yaml(self._build_interfaces_yaml(), "metrics/interfaces_dsoa.yaml")
        self._validate_against_schema(self._build_interfaces_yaml(), p)
        self._write_yaml(
            {
                "model_group": {
                    "id": "dsoa.metrics",
                    "title": "DSOA Snowflake Metrics",
                    "brief": "Metrics collected by the DSOA from Snowflake ACCOUNT_USAGE views.",
                }
            },
            "metrics/dsoa_metrics_model_group.yaml",
        )

        # Step 8: per-plugin metric models
        for plugin_name in sorted(plugin_metric_entries):
            if plugin_name == "_core":
                continue
            entries = plugin_metric_entries[plugin_name]
            if not entries:
                continue
            doc = self._build_metric_model_yaml(plugin_name, entries, all_entries, dim_plugins)
            p = self._write_yaml(doc, f"metrics/dsoa_metrics_{plugin_name}.yaml")
            self._validate_against_schema(doc, p)

        # Step 9: per-plugin event models
        plugins_with_events: Set[str] = {meta["plugin"] for k, meta in event_ts_entries.items() if k != "snowflake.event.trigger"}
        if plugins_with_events:
            self._write_yaml(
                {
                    "model_group": {
                        "id": "dsoa.events",
                        "title": "DSOA Snowflake Lifecycle Events",
                        "brief": "Timestamp-based lifecycle events emitted by DSOA as business events.",
                    }
                },
                "model/dsoa/model_group_dsoa_events.yaml",
            )
            for plugin_name in sorted(plugins_with_events):
                doc = self._build_event_model_yaml(plugin_name, event_ts_entries)
                p = self._write_yaml(doc, f"model/dsoa/dsoa.events.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        return dict(self._counters)

    ##endregion


##endregion


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
    parser.add_argument("--schema", default="_otel-build-tool/semantic-conventions/semconv.schema.json", help="Path to semconv.schema.json")
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
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
    print(f"Files generated            : {summary['files']}")
    print(f"Total classified fields    : {total}")
    print(f"  - ref                    : {summary['ref']}")
    print(f"  - new                    : {summary['new']}")
    print(f"  - deprecated-alias       : {summary['deprecated_alias']}")
    print(f"  - otel-only              : {summary['otel_only']}")
    print(f"Resource fields emitted    : {summary['resource_fields']}")
    print(f"Signal fields emitted      : {summary['signal_fields']}")
    print(f"Metric fields emitted      : {summary['metric_fields']}")
    print(f"Event timestamp fields     : {summary['event_timestamp_fields']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

##endregion

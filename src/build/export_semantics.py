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
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

##region Constants

#: Plugins that emit OpenTelemetry spans (in addition to log records).
#: Only these plugins get ``dsoa.spans.<plugin_name>.yaml`` model files.
SPAN_PLUGINS: frozenset = frozenset({"query_history", "event_log"})

#: Fields that already exist in the Dynatrace Semantic Dictionary (emit as ref: only).
#: Note: db.system is in OTel semconv but NOT yet in the SD as a global field.
#: It is annotated __semdict: otel-only in instruments-def and emitted as id:.
KNOWN_REFS = {
    "authentication.type",
    "db.operation.name",
    "db.query.text",
    "db.system",
    "event.category",
    "event.description",
    "event.id",
    "event.name",
    "host.name",
    "metric.key",
    "service.name",
    "telemetry.exporter.name",
    "telemetry.exporter.version",
    "vulnerability.risk.level",
}

#: Keys present on every DSOA telemetry record — synced with config.py RESOURCE_ATTRIBUTES.
RESOURCE_ATTRIBUTE_KEYS: Set[str] = {
    "db.system",
    "deployment.environment.name",
    "deployment.environment.tag",
    "deployment.environment",
    "dsoa.run.context",
    "dsoa.run.id",
    "dsoa.run.plugin",
    "host.name",
    "service.name",
    "telemetry.exporter.name",
    "telemetry.exporter.version",
}

#: Dimension keys covered by the i.dsoa_warehouse interface.
INTERFACE_WAREHOUSE_KEYS: Set[str] = {"snowflake.warehouse.name", "snowflake.warehouse.id"}

#: Dimension keys covered by the i.dsoa_database interface.
INTERFACE_DATABASE_KEYS: Set[str] = {"db.namespace", "snowflake.schema.name"}

#: Valid __field_type override values.
VALID_FIELD_TYPES = {"resource", "signal"}

#: Valid __stability annotation values for SD attribute/field definitions.
#: Note: OTel's "development" tier maps to SD's "experimental" — "development" is not a valid SD value.
VALID_STABILITY_VALUES = {"stable", "experimental", "deprecated"}

#: Acronyms that must stay ALL-CAPS in display_name (longer tokens first).
DISPLAY_NAME_ACRONYMS = ("DSOA", "OTel", "DDL", "DML", "RSS", "URL", "API", "ID", "DB", "QA", "SQL")

#: instruments-def.yml unit: value -> Semantic Dictionary unit abbreviation.
#:
#: instruments-def.yml uses the recognized Dynatrace universal-units UCUM
#: vocabulary directly for dt.meta.unit (see scripts/tools/instruments-def.schema.json
#: $defs/MetricUnit, maintained via internal Dynatrace tooling) plus a small
#: DSOA allowlist of domain-specific free-text nouns with no recognized equivalent.
#: The Semantic Dictionary uses a *different* abbreviation vocabulary (the
#: OTel semantic-conventions units registry). This map only needs entries
#: where the two vocabularies diverge — most
#: universal-units UCUM symbols (By, s, d, 1, ms, min, count, ratio, MiBy, ...)
#: already match their SD abbreviation and require no translation.
UNIT_MAP: Dict[str, str] = {
    # Domain-specific counts with no recognized universal-units equivalent —
    # map to 'count' (SD Unspecified category). Original meaning is preserved
    # via UNIT_NOTE_ORIGINALS below.
    "row": "count",
    "file": "count",
    "cluster": "count",
    "query": "count",
    "warehouse": "count",
    "partition": "count",
    "credit": "count",
    # Currency — SD abbreviation uses the $ glyph (units.json 'usd' -> 'US$');
    # this differs from the universal-units UCUM code (USD) used for dt.meta.unit.
    "currency": "US$",
}

#: Units that should carry a note explaining the original source unit when mapped to 'count'.
#: This preserves the semantic context that is lost by collapsing domain units to 'count'.
UNIT_NOTE_ORIGINALS: Set[str] = {
    "row",
    "file",
    "cluster",
    "query",
    "warehouse",
    "partition",
    "credit",
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
    # Grail array and record types (confirmed via dtctl investigation 2026-06-19)
    "string[]": "string[]",
    "long[]": "long[]",
    "array": "array",
    "record": "record",
    "record[]": "record[]",
}

#: Valid semdict classification values.
VALID_SEMDICT_FLAGS = {"ref", "new", "deprecated-alias", "otel-only"}

# (prefix, group_id, group_type) for signal fields — order matters (longest prefix first).
# All DSOA-owned signal groups use type: attribute_group — they appear on multiple signal
# types (logs + spans + events) and are not canonically span-wire-format fields.
# See IA guidance: type:span is reserved for groups whose semantics are exclusively
# span/trace wire-format (HTTP, RPC). Using it for DSOA fields would be incorrect.
# TODO: Re-evaluate after @information-architect review of span semantics.
_SIG_NS: List[Tuple[str, str, str]] = [
    ("snowflake.warehouse", "snowflake.warehouse", "attribute_group"),
    ("snowflake.query", "snowflake.query", "attribute_group"),
    ("snowflake.time", "snowflake.time", "attribute_group"),
    ("snowflake.object", "snowflake.object", "attribute_group"),
    ("snowflake.user", "snowflake.user", "attribute_group"),
    ("snowflake.session", "snowflake.session", "attribute_group"),
    ("snowflake.error", "snowflake.error", "attribute_group"),
    ("snowflake.data", "snowflake.data", "attribute_group"),
    # Dedicated sub-group for the dynamic-table dependency-graph fields — must precede the
    # generic "snowflake.table" entry below since _ns_group returns the first prefix match.
    ("snowflake.table.dynamic.graph", "snowflake.table.dynamic.graph", "attribute_group"),
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
    # Snowflake namespaces extracted from the snowflake.misc grab-bag
    ("snowflake.account", "snowflake.account", "attribute_group"),
    ("snowflake.copy", "snowflake.copy", "attribute_group"),
    ("snowflake.cost_attribution", "snowflake.cost_attribution", "attribute_group"),
    ("snowflake.entity", "snowflake.entity", "attribute_group"),
    ("snowflake.grant", "snowflake.grant", "attribute_group"),
    ("snowflake.org", "snowflake.org", "attribute_group"),
    ("snowflake.status", "snowflake.status", "attribute_group"),
    # Bare fields that don't match their sibling group's dotted prefix (no trailing "."
    # segment) — exact-match routing into the existing, semantically-obvious group.
    ("snowflake.cluster_number", "snowflake.cluster", "attribute_group"),
    ("snowflake.release_version", "snowflake.release", "attribute_group"),
    ("snowflake.secondary_role_stats", "snowflake.secondary", "attribute_group"),
    ("client", "client", "attribute_group"),
    ("db", "db", "attribute_group"),
    ("authentication", "authentication", "attribute_group"),
    ("session", "session", "attribute_group"),
    ("plugins", "plugins", "attribute_group"),
    ("error", "error", "attribute_group"),
    ("status", "status", "attribute_group"),
    ("event", "event", "attribute_group"),
    ("vulnerability", "vulnerability", "attribute_group"),
    # Non-Snowflake namespaces extracted from the snowflake.misc grab-bag
    ("anomaly", "anomaly", "attribute_group"),
    ("dsoa.debug", "dsoa.debug", "attribute_group"),
    ("dsoa.plugins", "dsoa.plugins", "attribute_group"),
    ("deployment", "deployment", "attribute_group"),
    ("observed_timestamp", "observed_timestamp", "attribute_group"),
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
    ("snowflake.resource_monitor", "snowflake.resource_monitor.resource", "resource"),
    ("snowflake.account", "snowflake.account", "resource"),
    ("snowflake.org", "snowflake.account", "resource"),
    ("db", "db.resource", "resource"),
]

##endregion

log = logging.getLogger(__name__)


##region YAML output helpers


class _IndentedDumper(yaml.Dumper):  # pylint: disable=too-many-ancestors
    """YAML Dumper that properly indents block sequence items and preserves multi-line strings.

    The default PyYAML Dumper uses compact (indentless) block sequences, where
    list items (``-``) appear at the same indentation level as the parent key.
    The Dynatrace Semantic Dictionary convention requires sequence items to be
    indented 2 spaces beneath their parent key.

    Additionally, this Dumper uses block literal style (``|``) for multi-line strings,
    preventing the default PyYAML behaviour of wrapping them in single-quoted flow scalars
    with embedded ``\\n`` characters.  This keeps DQL ``query_string`` values readable and
    avoids spurious blank lines in generated YAML files.

    Example — default (compact, incorrect for SD)::

        groups:
        - id: foo
          attributes:
          - ref: bar

    Example — _IndentedDumper (correct for SD)::

        groups:
          - id: foo
            attributes:
              - ref: bar
    """

    def increase_indent(self, flow=False, indentless=False):  # pylint: disable=arguments-differ
        """Override to force non-indentless block sequences.

        Args:
            flow:       Whether this is a flow-style container.
            indentless: Ignored; always forced to False so block sequences are indented.

        Returns:
            The result of the parent increase_indent with indentless=False.
        """
        return super().increase_indent(flow=flow, indentless=False)

    def represent_str(self, data: str):
        """Represent strings containing newlines as YAML literal block scalars (``|`` style).

        PyYAML's default string representer serialises multi-line strings as single-quoted
        flow scalars with embedded ``\\n`` sequences.  When the output file is re-read the
        content is semantically identical, but the visual representation has an extra blank
        line inserted after every original DQL line because the flow scalar preserves the
        literal newlines verbatim while the surrounding indentation adds apparent spacing.

        Using ``|`` (literal block style) preserves the original line structure and produces
        clean, human-readable YAML that round-trips without extra blank lines.

        Args:
            data: String value to represent.

        Returns:
            YAML node; block-literal for multi-line strings, default scalar otherwise.
        """
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return self.represent_scalar("tag:yaml.org,2002:str", data)


_IndentedDumper.add_representer(str, _IndentedDumper.represent_str)


##endregion


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
    normalised = str(raw_type).lower()
    mapped = METRIC_TYPE_MAP.get(normalised)
    if mapped:
        return mapped
    # Physical data types (long, double, string, …) on metric entries express the
    # value type, not the instrument kind — silently treat them as gauge.
    if normalised in ATTR_TYPE_MAP:
        return "gauge"
    log.warning("Unknown metric __type '%s'; defaulting to gauge", raw_type)
    return "gauge"


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
        log.debug(
            "Enum upgrade for '%s': replacing no-enum definition from %s with enum-rich one from %s",
            key,
            existing["plugin"],
            incoming["plugin"],
        )
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
        log.debug(
            "Enum union for '%s': merged %d member(s) from %s into %s", key, len(merged_members), incoming["plugin"], existing["plugin"]
        )
        return merged_meta

    # No enum to merge — keep existing (first-seen wins)
    log.debug("Duplicate key '%s' in %s (first in %s); using first definition", key, incoming["plugin"], existing["plugin"])
    return existing


def _dql_for_context(queries: Optional[List[Dict[str, Any]]], target: str) -> List[Dict[str, Any]]:
    """Filter a plugin's DQL example queries down to those applicable to one model type.

    Each entry's ``context`` list declares which model types it illustrates
    (``metrics``, ``logs``, ``events``, ``spans``). This routes each example to the
    matching Semantic Dictionary model(s) only, so a ``fetch logs`` example never lands
    on a metric/span model, a ``timeseries`` example never lands on a log/event model, etc.

    The ``context`` key is a routing directive, not part of the SD ``DqlQuery`` shape, so
    it is stripped from every returned dict — it must never appear in the generated YAML.

    Args:
        queries: The plugin's raw ``dql_queries`` list (may be ``None``).
        target:  Target model type — one of ``metrics``, ``logs``, ``events``, ``spans``.

    Returns:
        Queries whose ``context`` includes ``target``, each with ``context`` removed.
    """
    result: List[Dict[str, Any]] = []
    for query in queries or []:
        if target in (query.get("context") or []):
            result.append({k: v for k, v in query.items() if k != "context"})
    return result


##endregion


##region Validation


def _validate_entry(key: str, entry: Dict[str, Any], section: str, source_file: str) -> List[str]:
    """Validate a single instruments-def entry for required semdict metadata.

    Checks:
    - ``__description`` is present and non-empty.
    - ``__example`` is present, non-null, and non-blank.
    - ``__semdict: deprecated-alias`` requires ``__otel_replacement``.
    - ``__semdict: otel-only`` requires ``__semdict_note``.
    - ``__field_type`` is one of the valid values.
    - ``__stability`` (when set) is one of the valid SD values.
    - ``__example`` type matches ``__type`` when both present (non-metrics only).

    Type-match rules (skipped when ``__enum`` is present — schema enforces ``string``):
    - ``long``     → Python ``int`` (not ``bool``)
    - ``double``   → Python ``int`` or ``float`` (not ``bool``)
    - ``boolean``  → Python ``bool``
    - ``string``   → Python ``str``
    - ``string[]`` / ``array`` → Python ``list``

    In the ``metrics`` section ``__type`` is the instrument kind (gauge/counter/…),
    not the SD value type, so type-match is not enforced there.

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
    example = entry.get("__example")
    if example is None:
        errors.append(f"[{source_file}] {section}.{key}: missing or null __example")
    elif isinstance(example, str) and example.strip() == "":
        errors.append(f"[{source_file}] {section}.{key}: __example must not be empty or blank")
    semdict = entry.get("__semdict", "new")
    if semdict == "deprecated-alias" and not entry.get("__otel_replacement"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: deprecated-alias requires __otel_replacement")
    if semdict == "otel-only" and not entry.get("__semdict_note"):
        errors.append(f"[{source_file}] {section}.{key}: __semdict: otel-only requires __semdict_note")
    field_type = entry.get("__field_type")
    if field_type is not None and field_type not in VALID_FIELD_TYPES:
        errors.append(f"[{source_file}] {section}.{key}: unknown __field_type '{field_type}'")
    stability = entry.get("__stability")
    if stability is not None and str(stability).lower() not in VALID_STABILITY_VALUES:
        errors.append(
            f"[{source_file}] {section}.{key}: invalid __stability '{stability}' " f"(valid values: {sorted(VALID_STABILITY_VALUES)})"
        )
    # Type-match: enforce that __example Python type is consistent with __type annotation.
    # Only for attribute/dimension/event_timestamp sections — in metrics, __type is the
    # instrument kind (gauge/counter/…) not the SD value type, so skip there.
    # Also skip when __enum is present; schema already enforces __type: string for enums.
    _TYPE_TO_EXPECTED: Dict[str, Any] = {
        "long": int,
        "double": (int, float),
        "boolean": bool,
        "string": str,
        "string[]": list,
        "array": list,
    }
    if section != "metrics" and example is not None and not (isinstance(example, str) and example.strip() == ""):
        attr_type = entry.get("__type")
        has_enum = "__enum" in entry
        if attr_type and not has_enum:
            expected = _TYPE_TO_EXPECTED.get(attr_type)
            if expected is not None:
                is_bool = isinstance(example, bool)
                if attr_type in ("long", "double") and is_bool:
                    errors.append(
                        f"[{source_file}] {section}.{key}: __type={attr_type} but __example is bool {example!r}"
                        f" — use an integer/float value instead"
                    )
                elif not isinstance(example, expected):
                    errors.append(
                        f"[{source_file}] {section}.{key}: __type={attr_type} but __example is"
                        f" {type(example).__name__} {example!r} — expected {expected if isinstance(expected, type) else expected}"
                    )
        elif attr_type is None and isinstance(example, (int, float)) and not isinstance(example, bool):
            log.warning(
                "[%s] %s.%s: numeric example %r with no __type annotation — "
                "SD will default to string type; add __type: long or __type: double",
                source_file,
                section,
                key,
                example,
            )
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


def _coerce_string_array_examples(key: str, example_raw: Any) -> List[List[str]]:
    """Coerce a raw ``__example`` value into SD-valid list-of-lists format for ``string[]`` fields.

    The Semantic Dictionary build tool requires ``string[]`` attribute examples to be a
    **list of arrays** — each top-level element is itself a list of strings.  The canonical
    YAML spelling is::

        examples:
          - ["val1", "val2"]

    This function normalises the three input shapes encountered in instruments-def files:

    - **Already list-of-lists** (each element is a list): returned as-is.
    - **Flat list** (``["val1", "val2"]``): wrapped in an outer list → ``[["val1", "val2"]]``.
    - **Scalar string** that is a JSON array (``'["val1", "val2"]'``): parsed and wrapped →
      ``[["val1", "val2"]]``.  If JSON parsing fails, the string is wrapped as a
      single-element inner list → ``[["val1"]]``.
    - **Any other scalar**: coerced to string and wrapped as a single-element inner list.

    Args:
        key:         Field key (for debug logging).
        example_raw: Raw ``__example`` value from instruments-def (may be str, list, …).

    Returns:
        List of string arrays suitable for the SD ``examples:`` key.
    """
    if isinstance(example_raw, list):
        if example_raw and isinstance(example_raw[0], list):
            # Already list-of-lists — validate/coerce inner elements to str
            return [[str(item) for item in inner] for inner in example_raw]
        # Flat list — wrap in outer list
        log.debug("string[] field '%s': wrapping flat list example in outer list", key)
        return [[str(item) for item in example_raw]]

    # Scalar — try JSON parse first
    as_str = str(example_raw).strip()
    if as_str.startswith("["):
        try:
            parsed = json.loads(as_str)
            if isinstance(parsed, list):
                log.debug("string[] field '%s': parsed JSON array scalar example", key)
                return [[str(item) for item in parsed]]
        except (json.JSONDecodeError, ValueError):
            log.debug("string[] field '%s': JSON parse failed on scalar; wrapping as single string", key)

    return [[as_str]]


def _emit_id_entry(key: str, entry: Dict[str, Any], semdict_flag: str) -> Dict[str, Any]:
    """Build a full id: attribute definition block.

    Respects the ``__stability`` annotation in instruments-def.  When
    ``__stability: deprecated`` is set, the deprecated field is also emitted
    using ``__otel_replacement`` (if present).  OTel-only fields that have no
    explicit ``__semdict_note`` receive an auto-generated provenance note.

    For ``string[]`` fields the SD build tool requires examples to be a list of
    arrays — each example is itself an array of strings (list-of-lists format).
    This function normalises the raw ``__example`` value into the correct shape:

    - Already a list of lists (e.g. ``[["a", "b"]]``) — emitted as-is.
    - A flat list (e.g. ``["a", "b"]``) — wrapped in an outer list: ``[["a", "b"]]``.
    - A scalar string that looks like a JSON array (e.g. ``'["a", "b"]'``) — parsed
      and wrapped: ``[["a", "b"]]``.
    - Any other scalar — wrapped in a single-element list-of-lists: ``[["value"]]``.

    Args:
        key:          Field key.
        entry:        instruments-def entry dict.
        semdict_flag: ``new``, ``deprecated-alias``, or ``otel-only``.

    Returns:
        Dict with all required semconv attribute fields.
    """
    attr_type = _build_type_node(entry)
    description = str(entry["__description"]).strip()
    field_type = str(entry.get("__type") or "").strip().lower()
    example_raw = entry.get("__example", "")
    if example_raw is None:
        example_raw = ""

    if field_type == "string[]":
        # SD requires examples for string[] to be a list of arrays (list-of-lists).
        examples = _coerce_string_array_examples(key, example_raw)
    else:
        examples = (
            [_coerce_attribute_example(example_raw, field_type)]
            if not isinstance(example_raw, list)
            else [_coerce_attribute_example(e, field_type) for e in example_raw]
        )

    # Determine stability: respect __stability annotation, default to experimental.
    # SD schema rule: ``deprecated:`` and ``stability:`` are mutually exclusive.
    # - When stability is "deprecated": emit only ``deprecated:`` key, omit ``stability:``.
    # - All other values: emit only ``stability:`` key, omit ``deprecated:``.
    stability = str(entry.get("__stability") or "experimental").lower()
    if stability == "deprecated":
        deprecated_msg = f"Use {entry['__otel_replacement']} instead." if entry.get("__otel_replacement") else "Deprecated."
        node: Dict[str, Any] = {
            "id": key,
            "display_name": _make_display_name(key),
            "type": attr_type,
            "deprecated": deprecated_msg,
            "brief": description,
            "examples": examples,
        }
    else:
        node = {
            "id": key,
            "display_name": _make_display_name(key),
            "type": attr_type,
            "stability": stability,
            "brief": description,
            "examples": examples,
        }
    if semdict_flag == "deprecated-alias":
        replacement = entry.get("__otel_replacement", "")
        otel_note = entry.get("__semdict_note", "")
        boilerplate = "DSOA continues to emit it for backward compatibility."
        if otel_note:
            note_text = str(otel_note).strip()
            # Avoid double-appending the boilerplate sentence when the authored note already
            # explains the backward-compatibility rationale (e.g. deployment.environment).
            warning = note_text if "backward compatibility" in note_text.lower() else f"{note_text} {boilerplate}"
        else:
            warning = f"OTel renamed this field to {replacement}. {boilerplate}"
        node["note"] = warning
    elif entry.get("__semdict_note"):
        node["note"] = str(entry["__semdict_note"]).strip()
    elif semdict_flag == "otel-only":
        # Auto-generate OTel provenance note when no explicit __semdict_note is provided.
        auto_note = (
            f"Defined in OTel Semantic Conventions ({key}, {stability}). "
            "Not yet present as a globally referenceable field in the Dynatrace "
            "Semantic Dictionary. Emitting as id: pending global SD registration."
        )
        node["note"] = auto_note
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


def _coerce_attribute_example(value: Any, field_type: str = "") -> Any:
    """Coerce an attribute example to the Python type matching the declared SD field type.

    The Semantic Dictionary build tool rejects examples whose Python type does not match
    the declared field type — e.g. a string ``"2"`` for a ``long`` field causes a schema
    validation error.  This function converts the raw example (typically a YAML scalar)
    to the correct Python native type so that PyYAML serialises it correctly:

    - ``long`` / ``int``    → Python :class:`int` (arbitrary precision — safe for 19-digit
                              nanosecond timestamps)
    - ``double`` / ``float`` → Python :class:`float`
    - ``boolean``            → Python :class:`bool` (PyYAML serialises as ``true``/``false``)
    - ``string`` / ``string[]`` / any other / unset → :class:`str` (strip whitespace)

    Args:
        value:      Raw example value from instruments-def (may be str, int, float, or bool).
        field_type: Declared ``__type`` of the field (e.g. ``"long"``, ``"boolean"``).
                    Defaults to empty string which maps to the ``str`` branch.

    Returns:
        Python value coerced to the appropriate native type.
    """
    normalised = (field_type or "").strip().lower()
    if normalised in ("long", "int"):
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            pass
    elif normalised in ("double", "float"):
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            pass
    elif normalised == "boolean":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        return lowered not in ("false", "0", "no", "")
    # Default: string (also handles string[], array, record, enum, timestamp, unknown)
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
    stability = str(entry.get("__stability") or "experimental").lower()
    node: Dict[str, Any] = {
        "id": key,
        "type": "metric",
        "metric_name": key,
        "instrument": instrument,
        "stability": stability,
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
            k: v for k, v in resource_entries.items() if (k.startswith("dsoa.") or k.startswith("deployment.")) and v["semdict"] != "ref"
        }
        snowflake_keys = {k: v for k, v in resource_entries.items() if k not in dsoa_keys and v["semdict"] != "ref"}

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
            # Skip ref: entries — they belong in interfaces only, not in field definition files.
            # Refs are included via i.dsoa_resource and related interfaces by _build_interfaces_yaml().
            if all_signal[key]["semdict"] == "ref":
                continue
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

    def _build_interfaces_yaml(self, all_entries: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build metrics/interfaces_dsoa.yaml with i.dsoa_resource/warehouse/database.

        Args:
            all_entries: All parsed field entries keyed by field key. When provided,
                         ``__interface_note`` values are read from each entry to annotate
                         ``ref:`` attributes in ``i.dsoa_resource`` with contextual notes.

        Returns:
            Semconv-compliant YAML doc dict.
        """

        def _ref_entry(key: str) -> Dict[str, Any]:
            """Build a ref: attribute entry with optional note: from __interface_note."""
            entry: Dict[str, Any] = {"ref": key}
            if all_entries:
                meta = all_entries.get(key)
                if meta:
                    note = (meta.get("entry") or meta).get("__interface_note", "")
                    if note:
                        entry["note"] = str(note).strip()
            return entry

        return {
            "groups": [
                {
                    "id": "i.dsoa_resource",
                    "type": "interface",
                    "title": "DSOA resource fields",
                    "brief": "Fields present on all DSOA telemetry records. Synced with config.py RESOURCE_ATTRIBUTES.",
                    "attributes": [_ref_entry(k) for k in sorted(RESOURCE_ATTRIBUTE_KEYS)],
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
        self,
        metric_entries: Dict[str, Any],
        all_entries: Dict[str, Any],
        dim_plugins: Optional[Dict[str, Set[str]]] = None,
        dim_context_by_plugin: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    ) -> List[str]:
        """Determine which DSOA interfaces to declare for a metric model.

        Args:
            metric_entries:        Per-plugin metric entries.
            all_entries:           All parsed entries (for dimension lookup).
            dim_plugins:           Map of dimension key → set of all plugins that define it.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.
            dim_plugins:           Map of dimension key → set of all plugins that define it.
                                   When provided, a dim without ``__context_names`` is accepted
                                   for a plugin if that plugin is in ``dim_plugins[dim_key]``,
                                   not only if the dedup winner happened to be that plugin.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.

        Returns:
            Ordered list of interface IDs.
        """
        uses_warehouse = uses_database = False
        for _mk, m_meta in metric_entries.items():
            mc_names = set(m_meta["entry"].get("__context_names") or [])
            m_plugin = m_meta["plugin"]
            # Use dim_plugins as authoritative source (same logic as _build_metric_model_yaml).
            dim_source = sorted(dim_plugins.keys()) if dim_plugins is not None else all_entries.keys()
            for dim_key in dim_source:
                if dim_plugins is not None:
                    if m_plugin not in dim_plugins.get(dim_key, set()):
                        continue
                else:
                    dim_meta = all_entries.get(dim_key)
                    if not dim_meta or dim_meta["section"] != "dimensions":
                        continue
                    if dim_meta["plugin"] != m_plugin:
                        continue
                # Use per-plugin context names when available (avoids dedup winner mismatch).
                if dim_context_by_plugin is not None:
                    dc_names: Set[str] = dim_context_by_plugin.get(m_plugin, {}).get(dim_key, set())
                else:
                    dim_meta = all_entries.get(dim_key)
                    dc_names = set(dim_meta["entry"].get("__context_names") or []) if dim_meta else set()
                if dc_names and not dc_names.intersection(mc_names):
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
        dim_context_by_plugin: Optional[Dict[str, Dict[str, Set[str]]]] = None,
        dql_queries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a per-plugin metric model YAML document.

        Args:
            plugin_name:           Plugin name.
            metric_entries:        Plugin's metric entries.
            all_entries:           All parsed entries for dimension resolution.
            dim_plugins:           Map of dimension key → set of all plugins that define it.
                                   When provided, dimensions are resolved by ownership across all
                                   plugin definitions, not just the dedup winner.
            dim_context_by_plugin: Per-plugin map of dim_key → context name set.
            dql_queries:           Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_title = _restore_acronyms(plugin_name.replace("_", " ").title())
        interfaces = self._select_interfaces(metric_entries, all_entries, dim_plugins, dim_context_by_plugin)
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
            # Use dim_plugins as the canonical source for which keys are dimensions.
            # This handles the case where cross-plugin dedup promotes an "attributes"-section
            # definition as the winning entry, masking the "dimensions"-section definition
            # from another plugin.  Iterating over dim_plugins ensures all dimension keys
            # are considered for metric attribute lists regardless of which plugin won dedup.
            dim_source = sorted(dim_plugins.keys()) if dim_plugins is not None else sorted(all_entries.keys())
            for dim_key in dim_source:
                if dim_plugins is not None:
                    # Skip if the current metric's plugin didn't define this as a dimension
                    if m_plugin not in dim_plugins.get(dim_key, set()):
                        continue
                else:
                    # Fallback: use section check on all_entries
                    dim_meta = all_entries.get(dim_key)
                    if not dim_meta or dim_meta["section"] != "dimensions":
                        continue
                    if dim_meta["plugin"] != m_plugin:
                        continue
                if dim_key in covered:
                    continue
                # Use per-plugin context names when available (avoids dedup winner mismatch
                # where shares.inbound_shares wins over table_health.table_clustering).
                if dim_context_by_plugin is not None:
                    dc_names: Set[str] = dim_context_by_plugin.get(m_plugin, {}).get(dim_key, set())
                else:
                    dim_meta = all_entries.get(dim_key)
                    dc_names = set(dim_meta["entry"].get("__context_names") or []) if dim_meta else set()
                # A dim with context_names is applicable only when it overlaps the metric.
                if dc_names and not dc_names.intersection(mc_names):
                    continue
                dim_refs.append({"ref": dim_key})
            metric_node = _emit_metric_entry(metric_key, m_meta["entry"])
            if dim_refs:
                metric_node["attributes"] = dim_refs
            groups.append(metric_node)
            self._counters["metric_fields"] += 1

        model_doc: Dict[str, Any] = {
            "id": f"dsoa.metrics.{plugin_name}",
            "title": f"Snowflake {plugin_title} Metrics",
            "brief": f"Metrics collected by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
            "model_group_id": "dsoa.metrics",
            "data_object": "metric",
            "interfaces": interfaces,
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = groups
        return {"model": model_doc}

    def _build_event_model_yaml(
        self, plugin_name: str, event_ts_entries: Dict[str, Any], dql_queries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Build a per-plugin event model YAML document.

        Args:
            plugin_name:      Plugin name.
            event_ts_entries: All event_timestamp entries across all plugins.
            dql_queries:      Optional list of DQL query dicts from instruments-def.yml.

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
        model_doc: Dict[str, Any] = {
            "id": f"dsoa.events.{plugin_name}",
            "title": f"Snowflake {plugin_title} Lifecycle Events",
            "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin via the OpenPipeline Events API.",
            "model_group_id": "dsoa.events",
            "data_object": "event",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = [
            {
                "id": f"dsoa.events.{plugin_name}.fields",
                "type": "attribute_group",
                "title": f"{plugin_title} event fields",
                "attributes": attrs,
            }
        ]
        return {"model": model_doc}

    ##endregion

    ##region Log / Span model builders

    def _collect_plugin_attribute_refs(
        self,
        plugin_name: str,
        all_entries: Dict[str, Any],
        context_name: Optional[str] = None,
        exclude_span_only: bool = False,
    ) -> List[Dict[str, str]]:
        """Collect all attribute field refs for a plugin (optionally for one context).

        Collects all entries from ``attributes`` section that belong to ``plugin_name``
        (either as the dedup winner or as a definition registered in ``all_entries``).
        Entries with ``__context_names`` are included only if ``context_name`` is None
        or if the context matches.

        ``ref``-classified entries are excluded (they belong in SD interfaces only).

        Note: ``__context_names`` is a general per-field annotation also used (by many
        other plugins) to scope a field to a specific source SQL view/context — e.g.
        ``task_history`` vs. ``task_versions`` — not specifically log-vs-span. Passing a
        ``context_name`` here only has an effect on fields that opt in via their own
        ``__context_names`` list; callers must not assume it differentiates log/span
        models on its own. Log/span differentiation instead uses
        the dedicated ``exclude_span_only`` flag, driven by the ``__span_only``
        annotation, to avoid colliding with the pre-existing SQL-view-scoping use of
        ``__context_names``.

        Args:
            plugin_name:       Plugin name.
            all_entries:       All parsed entries (dedup-resolved).
            context_name:      If provided, only include fields applicable to this context.
            exclude_span_only: If True, skip fields annotated with ``__span_only: true``
                                (fields reported only on span records, e.g. span-event
                                payloads) — used to build the plugin's log model.

        Returns:
            Sorted list of ``{"ref": key}`` dicts.
        """
        refs = []
        for key, meta in all_entries.items():
            if meta["section"] != "attributes":
                continue
            if meta["plugin"] != plugin_name:
                continue
            if meta["semdict"] == "ref":
                continue
            if exclude_span_only and meta["entry"].get("__span_only"):
                continue
            # Filter by context if requested
            if context_name is not None:
                ctx_names = set(meta["entry"].get("__context_names") or [])
                if ctx_names and context_name not in ctx_names:
                    continue
            refs.append(key)
        return [{"ref": k} for k in sorted(refs)]

    def _build_log_model_yaml(
        self, plugin_name: str, all_entries: Dict[str, Any], dql_queries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Build a per-plugin log record model YAML document.

        Creates a log model that references all attribute fields for the plugin via
        a ``ref:`` list in a dedicated model group, resolving signal-field orphans.

        Fields annotated with ``__span_only: true`` are excluded here even though they
        are still collected for the span model, e.g., span-event
        payload fields (``snowflake.query.step.*``) that only apply to the span
        representation of a plugin's records.

        Args:
            plugin_name:  Plugin name.
            all_entries:  All parsed entries (dedup-resolved).
            dql_queries:  Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_title = _restore_acronyms(plugin_name.replace("_", " ").title())
        attr_refs = self._collect_plugin_attribute_refs(plugin_name, all_entries, exclude_span_only=True)
        model_doc: Dict[str, Any] = {
            "id": f"dsoa.logs.{plugin_name}",
            "title": f"DSOA {plugin_title} Log Records",
            "brief": f"Log records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "dsoa.logs",
            "data_object": "log",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = [
            {
                "id": f"dsoa.logs.{plugin_name}.fields",
                "type": "attribute_group",
                "title": f"{plugin_title} log record fields",
                "brief": f"Attribute fields for {_make_display_name(plugin_name)} log records.",
                "attributes": attr_refs,
            }
        ]
        return {"model": model_doc}

    def _build_span_model_yaml(
        self, plugin_name: str, all_entries: Dict[str, Any], dql_queries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Build a per-plugin span model YAML document.

        Only generated for plugins in ``SPAN_PLUGINS``. Unlike the log model, no
        ``__span_only`` filtering is applied here — span-only fields
        are ordinary attributes from the span model's perspective and are included
        alongside every other field the plugin defines.

        Args:
            plugin_name:  Plugin name (must be in SPAN_PLUGINS).
            all_entries:  All parsed entries (dedup-resolved).
            dql_queries:  Optional list of DQL query dicts from instruments-def.yml.

        Returns:
            Semconv-compliant YAML document dict with ``model:`` envelope.
        """
        plugin_title = _restore_acronyms(plugin_name.replace("_", " ").title())
        attr_refs = self._collect_plugin_attribute_refs(plugin_name, all_entries)
        model_doc: Dict[str, Any] = {
            "id": f"dsoa.spans.{plugin_name}",
            "title": f"DSOA {plugin_title} Spans",
            "brief": f"Span records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "dsoa.spans",
            "data_object": "span",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = [
            {
                "id": f"dsoa.spans.{plugin_name}.fields",
                "type": "attribute_group",
                "title": f"{plugin_title} span fields",
                "brief": f"Attribute fields for {_make_display_name(plugin_name)} spans.",
                "attributes": attr_refs,
            }
        ]
        return {"model": model_doc}

    ##endregion

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """Load and patch semconv JSON schema if available.

        The raw ``semconv.schema.json`` is written for a custom build-tool validator
        (not standard ``jsonschema``).  The ``Attribute`` and ``SemanticConventionBase``
        definitions use ``additionalProperties: false`` at the top level while declaring
        their allowed properties *inside* ``allOf`` sub-schemas.  In JSON Schema draft-07,
        ``additionalProperties: false`` only considers ``properties`` at the **same schema
        object level** — not properties nested inside ``allOf`` — which produces spurious
        "Additional properties not allowed" errors for all valid DSOA field definitions.

        This method patches the loaded schema before returning it:

        - Removes ``additionalProperties: false`` from all ``definitions`` entries that
          declare their properties via ``allOf`` (e.g. ``Attribute``,
          ``SemanticConventionBase``, smartscape edge types).  Removing it makes the
          ``additionalProperties`` check a no-op while preserving all ``required`` and
          type checks.
        - Removes the ``anyOf(attributes|extends)`` constraint from
          ``SemanticConventionBase``.  Metric groups that have no dimension attributes
          do not carry an ``attributes`` list and would otherwise fail this constraint.

        These patches silence false-positive errors without relaxing any meaningful
        structural validation.  Required fields (``id``, ``type``, ``metric_name``, etc.)
        are still enforced by the ``required`` constraints in each definition.

        Returns:
            Patched schema dict or None if the schema file is not found.
        """
        if not self.schema_path or not self.schema_path.exists():
            log.warning("semconv.schema.json not found at %s; skipping schema validation", self.schema_path)
            return None
        import copy  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        with open(self.schema_path, "r", encoding="utf-8") as fh:
            raw_schema = json.load(fh)

        schema = copy.deepcopy(raw_schema)
        for defn in schema.get("definitions", {}).values():
            # Strip additionalProperties:false — standard jsonschema draft-07 does not
            # look inside allOf sub-schemas when evaluating additionalProperties, so this
            # flag produces false-positive errors for every valid attribute node.
            if defn.get("additionalProperties") is False:
                defn.pop("additionalProperties")
        # Remove anyOf(attributes|extends) from SemanticConventionBase:
        # metric groups that carry no dimension attributes are otherwise rejected.
        scb = schema.get("definitions", {}).get("SemanticConventionBase", {})
        scb.pop("anyOf", None)
        return schema

    def _validate_against_schema(self, doc: Dict[str, Any], yaml_path: Path) -> bool:
        """Validate a generated YAML document against semconv.schema.json.

        Uses the patched schema loaded by :meth:`_load_schema` to avoid false-positive
        ``additionalProperties`` errors.  Only the short ``message`` from the first
        ``ValidationError`` is logged — the verbose ``On instance[...]`` JSON dump
        produced by the default ``str(exc)`` rendering is intentionally suppressed.

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
        except jsonschema.ValidationError as exc:  # pylint: disable=broad-except
            # Log only the short message to avoid the verbose "On instance[...]" dump.
            log.error("Schema validation FAIL: %s — %s", yaml_path, exc.message)
            return False
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Schema validation FAIL: %s — %s", yaml_path, exc)
            return False

    ##endregion

    ##region File writing

    def _write_yaml(self, doc: Dict[str, Any], rel_path: str) -> Path:
        """Write a YAML document to the output directory.

        Uses :class:`_IndentedDumper` to produce properly indented block sequences
        per Semantic Dictionary YAML conventions.

        Args:
            doc:      YAML-serialisable dict.
            rel_path: Relative path under output_dir.

        Returns:
            Absolute path to the written file.
        """
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            yaml.dump(doc, fh, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True, sort_keys=False, width=200)
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
        # Per-plugin dimension context names: {plugin_name: {dim_key: set(context_names)}}
        # This preserves each plugin's own context annotations independent of dedup winner.
        dim_context_by_plugin: Dict[str, Dict[str, Set[str]]] = {}
        # Per-plugin DQL query examples collected directly from the top-level dql_queries: key
        # in each instruments-def.yml file.  Keyed by plugin_name (or "_core").  Each entry's
        # ``context`` list routes it to the matching model type(s) via ``_dql_for_context``.
        plugin_dql_queries: Dict[str, List[Dict[str, Any]]] = {}
        for plugin_name, path in files:
            log.debug("Parsing %s (%s)", plugin_name, path)
            errors, entries = self._parse_file(plugin_name, path)
            all_errors.extend(errors)
            # Collect top-level dql_queries from the raw YAML (separate from field entries).
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw_data = yaml.safe_load(fh) or {}
                raw_queries = raw_data.get("dql_queries")
                if raw_queries and isinstance(raw_queries, list):
                    plugin_dql_queries[plugin_name] = raw_queries
                    log.debug("Collected %d dql_queries from %s", len(raw_queries), plugin_name)
            except Exception as exc:  # pylint: disable=broad-except
                log.warning("Could not re-read dql_queries from %s: %s", path, exc)
            for key, meta in entries.items():
                # Track all plugins that define each dimension key (for A3 ownership)
                if meta["section"] == "dimensions":
                    dim_plugins.setdefault(key, set()).add(plugin_name)
                    ctx = set(meta["entry"].get("__context_names") or [])
                    dim_context_by_plugin.setdefault(plugin_name, {}).setdefault(key, set()).update(ctx)
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
        p = self._write_yaml(self._build_interfaces_yaml(all_entries), "metrics/interfaces_dsoa.yaml")
        self._validate_against_schema(self._build_interfaces_yaml(all_entries), p)
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
            doc = self._build_metric_model_yaml(
                plugin_name,
                entries,
                all_entries,
                dim_plugins,
                dim_context_by_plugin,
                dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "metrics"),
            )
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
                        "brief": "Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace OpenPipeline Events API.",
                    }
                },
                "model/dsoa/model_group_dsoa_events.yaml",
            )
            for plugin_name in sorted(plugins_with_events):
                doc = self._build_event_model_yaml(
                    plugin_name,
                    event_ts_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "events"),
                )
                p = self._write_yaml(doc, f"model/dsoa/dsoa.events.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        # Step 10: per-plugin log models (resolves signal field orphans)
        plugins_with_attrs: Set[str] = {
            meta["plugin"] for meta in all_entries.values() if meta["section"] == "attributes" and meta["semdict"] != "ref"
        }
        plugins_with_attrs.discard("_core")  # _core attrs are resource-level; no log model needed
        if plugins_with_attrs:
            self._write_yaml(
                {
                    "model_group": {
                        "id": "dsoa.logs",
                        "title": "DSOA Snowflake Log Records",
                        "brief": "Log records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE and system views.",
                    }
                },
                "model/dsoa/model_group_dsoa_logs.yaml",
            )
            for plugin_name in sorted(plugins_with_attrs):
                doc = self._build_log_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "logs"),
                )
                p = self._write_yaml(doc, f"model/dsoa/dsoa.logs.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        # Step 11: per-plugin span models (only for SPAN_PLUGINS)
        span_model_plugins = plugins_with_attrs & SPAN_PLUGINS
        if span_model_plugins:
            self._write_yaml(
                {
                    "model_group": {
                        "id": "dsoa.spans",
                        "title": "DSOA Spans",
                        "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                    }
                },
                "model/dsoa/model_group_dsoa_spans.yaml",
            )
            for plugin_name in sorted(span_model_plugins):
                doc = self._build_span_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "spans"),
                )
                p = self._write_yaml(doc, f"model/dsoa/dsoa.spans.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        # Generate span model for event_log even if it has no attributes
        # (event_log emits spans from its SQL context; span fields are tracked as dimensions)
        if "event_log" in SPAN_PLUGINS and "event_log" not in span_model_plugins:
            if "dsoa.spans" not in str(list(span_model_plugins)):  # model_group not yet written
                self._write_yaml(
                    {
                        "model_group": {
                            "id": "dsoa.spans",
                            "title": "DSOA Spans",
                            "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                        }
                    },
                    "model/dsoa/model_group_dsoa_spans.yaml",
                )
            doc = self._build_span_model_yaml(
                "event_log",
                all_entries,
                dql_queries=_dql_for_context(plugin_dql_queries.get("event_log"), "spans"),
            )
            p = self._write_yaml(doc, "model/dsoa/dsoa.spans.event_log.yaml")
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
    parser.add_argument("--schema", default="scripts/tools/semconv.schema.json", help="Path to semconv.schema.json")
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

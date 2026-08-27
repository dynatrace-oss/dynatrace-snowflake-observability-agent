"""Constants and pure helper functions for classifying and emitting Semantic Dictionary fields.

Holds the SD submission metadata, namespace-grouping tables, and the stateless
functions that turn a single instruments-def.yml entry into title/display-name
strings, validation errors, or a semconv-compliant ``ref:``/``id:``/``metric``
node. These are used by :class:`build.semantic_exporter.discovery.EntryDiscoverer`
and :class:`build.semantic_exporter.document_builders.DocumentBuilder`.
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
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from build.semantic_exporter.yaml_helpers import _QuotedStr, _SingleQuotedStr

log = logging.getLogger("build.export_semantics")


def _load_dotenv(env_path: Path) -> None:
    """Load a .env file into os.environ (never fails — dotenv optional, raw parsing fallback).

    Runs at import time, before SD_PM/SD_MAINTAINER/SD_OWNERS below read os.environ —
    those constants must see .env values regardless of which module happens to import
    this one first.
    """
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import]  # pylint: disable=import-outside-toplevel

        load_dotenv(env_path, override=False)
    except ImportError:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(Path(__file__).resolve().parents[3] / ".env")

##region Constants

#: Plugins that emit OpenTelemetry spans (in addition to log records).
#: Only these plugins get ``snowflake.spans.<plugin_name>.yaml`` model files.
SPAN_PLUGINS: frozenset = frozenset({"query_history", "event_log"})

#: Fields that already exist in the Dynatrace Semantic Dictionary (emit as ref: only).
KNOWN_REFS = {
    "authentication.type",
    "client.ip",
    "db.collection.name",
    "db.namespace",
    "db.operation.name",
    "db.query.text",
    "db.system",
    "event.category",
    "event.description",
    "event.id",
    "event.kind",
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

# --- Semantic Dictionary submission metadata ---
# Update these constants when team membership or SD category naming changes.

#: SD global_field_categories.json key for all DSOA + Snowflake groups.
SD_FIELD_CATEGORY = "data_observability"

#: Human-readable label for the SD field category.
SD_FIELD_CATEGORY_DISPLAY_NAME = "Data Observability"

#: SD field category description.
SD_FIELD_CATEGORY_DESCRIPTION = "Snowflake observability fields (DSOA)"

#: Responsible PM listed in doc/model/snowflake/*/readme.md stubs.
#: Set via SD_PM env var (or .env file — see .env.example).
SD_PM: str = os.environ.get("SD_PM", "")

#: Maintainer listed in doc/model/snowflake/*/readme.md stubs.
#: Set via SD_MAINTAINER env var (or .env file — see .env.example).
SD_MAINTAINER: str = os.environ.get("SD_MAINTAINER", "")

#: Team name listed in doc/model/snowflake/*/readme.md stubs.
SD_TEAM = "DSOA"

#: OWNERS file identifiers for the DSOA team.
#: Set via SD_OWNERS env var as a space-separated list (or .env file — see .env.example).
SD_OWNERS: List[str] = os.environ.get("SD_OWNERS", "").split() or []

#: Group ID prefixes that DSOA owns exclusively in the Semantic Dictionary.
#: Used to decide which signal_fields files and doc/fields/*.md entries go
#: into the OWNERS section (shared fields like db, client, authentication are excluded).
SD_OWNED_GROUP_PREFIXES: frozenset = frozenset({"snowflake", "dsoa", "anomaly", "observed_timestamp"})

#: Acronyms that must stay ALL-CAPS in display_name (longer tokens first).
DISPLAY_NAME_ACRONYMS = ("DSOA", "OTel", "DDL", "DML", "RSS", "URL", "API", "ID", "DB", "QA", "SQL")

#: Multi-word proper nouns / product names that must retain their capitalisation
#: in SD group ``title:`` and ``brief:`` fields (sentence-case context only).
#: Each entry is the correctly-cased phrase; matching is case-insensitive.
TITLE_PROPER_NOUNS = (
    "Trust Center",
    "Resource Monitor",
    "Snowflake",
    "Dynatrace",
    "Data Observability",
    "Dynatrace Observability",
    "Snowpipe",
    "Snowpipes",
)

#: Word-level substitutions applied in _make_title, _make_display_name, and _plugin_label.
_WORD_SUBS: Dict[str, str] = {"org": "organization"}

#: Override map for doc/fields/ stub ## h2 headings (the hand-authored top-of-file
#: heading in the doc stub, "line 1" per PR #1964 review feedback) keyed by group_id
#: (ns_key after stripping any .resource suffix). Used when _make_title produces an
#: inadequate heading — e.g. the top-level "dsoa" group needs the full product name.
#: Per reviewer feedback (Schoenberger, PR #1964): "write in line 1 as it is [full
#: name] and in the group then just [abbreviated] ### DSOA debug signal fields" — so
#: this ## h2 override intentionally stays the FULL product name; only the YAML
#: title: (rendered as the ### h3 inside the semconv block, see
#: _GROUP_TITLE_OVERRIDES below) is abbreviated.
_FIELD_STUB_H2_OVERRIDES: Dict[str, str] = {
    "dsoa": "Dynatrace Snowflake Observability Agent (DSOA)",
    "dsoa.debug": "Dynatrace Snowflake Observability Agent (DSOA) debug",
    "dsoa.plugins": "Dynatrace Snowflake Observability Agent (DSOA) plugins",
}

#: Override map for a group's YAML title: field (rendered by the SD generator as the
#: ### h3 heading inside the semconv block — distinct from the ## h2 doc-stub heading
#: above, which intentionally keeps the full product name per PR #1964 review
#: feedback). Keyed by group_id the same way as _FIELD_STUB_H2_OVERRIDES.
_GROUP_TITLE_OVERRIDES: Dict[str, str] = {
    "dsoa": "DSOA",
    "dsoa.debug": "DSOA debug",
    "dsoa.plugins": "DSOA plugins",
}

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
    parts = [_WORD_SUBS.get(p, p) for p in parts]
    sentence = " ".join(p.lower() for p in parts)
    sentence = sentence[0].upper() + sentence[1:] if sentence else sentence
    return _restore_acronyms(sentence)


def _make_title(key: str) -> str:
    """Convert dot-notation key to sentence-case title for SD group ``title:`` fields.

    Sentence case means only the first word is capitalised; subsequent words are
    lowercase unless they are acronyms restored by :func:`_restore_acronyms` or
    multi-word proper nouns listed in :data:`TITLE_PROPER_NOUNS`.
    This matches the SD convention documented in
    ``juno_docs/define-data-in-grail/definition/yaml/common/title.md``.

    Args:
        key: Dot-notation field key (e.g. ``snowflake.warehouse``).

    Returns:
        Sentence-case title with acronyms and proper nouns preserved
        (e.g. ``"Snowflake warehouse"``, ``"Snowflake Trust Center"``).
    """
    parts = key.replace("_", " ").replace("-", " ").replace(".", " ").split()
    if not parts:
        return ""
    parts = [_WORD_SUBS.get(p, p) for p in parts]
    titled = [parts[0].capitalize()] + [p.lower() for p in parts[1:]]
    result = _restore_acronyms(" ".join(titled))
    for noun in TITLE_PROPER_NOUNS:
        result = result.replace(noun.lower(), noun)
    return result


def _plugin_label(plugin_name: str, *, cap_first: bool = False) -> str:
    """Convert a plugin identifier to a human-readable label with proper-noun capitalisation.

    Unlike :func:`_make_title`, this function does not call :func:`_restore_acronyms` or
    split on dots — it only processes underscore-joined plugin identifiers (e.g.
    ``"trust_center"``, ``"org_costs"``, ``"snowpipes"``).

    Args:
        plugin_name: Underscore-separated plugin identifier.
        cap_first:   If True, capitalise the first character only (without lowercasing
                     the rest, which ``.capitalize()`` would do and which would break
                     proper nouns like "Trust Center").

    Returns:
        Human-readable label (e.g. ``"Trust Center"``, ``"organization costs"``,
        ``"Snowpipes"``).
    """
    parts = [_WORD_SUBS.get(w, w) for w in plugin_name.split("_")]
    label = " ".join(parts)
    for noun in TITLE_PROPER_NOUNS:
        label = label.replace(noun.lower(), noun)
    if cap_first and label:
        label = label[0].upper() + label[1:]
    return label


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


def _resolve_model_group_dql(
    raw: Dict[str, Any],
    plugin_dql_queries: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Resolve the ``model_group_dql`` block from scripts/tools/model-group-dql.yml into SD-ready DQL lists.

    Each entry in the raw block is either a literal ``DqlQuery`` dict or a
    ``use_plugin_dql`` reference ``{plugin: <name>, context: <ctx>}``.  References are
    expanded by pulling matching queries from ``plugin_dql_queries`` via
    ``_dql_for_context``; the ``context`` routing key is stripped in both cases so the
    result is a clean list of ``DqlQuery`` objects suitable for direct embedding in
    model_group YAML.

    Args:
        raw:                Raw ``model_group_dql`` dict from scripts/tools/model-group-dql.yml.
        plugin_dql_queries: Per-plugin query lists already collected during export (keyed
                            by plugin name).

    Returns:
        Dict mapping model group ID → resolved list of SD ``DqlQuery`` dicts.  Groups
        with no resolvable queries are omitted.
    """
    resolved: Dict[str, List[Dict[str, Any]]] = {}
    for group_id, entries in (raw or {}).items():
        queries: List[Dict[str, Any]] = []
        for entry in entries or []:
            ref = entry.get("use_plugin_dql")
            if ref:
                plugin = ref.get("plugin", "")
                context = ref.get("context", "")
                expanded = _dql_for_context(plugin_dql_queries.get(plugin), context)
                if not expanded:
                    log.warning("model_group_dql[%s]: use_plugin_dql plugin=%s context=%s yielded no queries", group_id, plugin, context)
                queries.extend(expanded)
            else:
                # Literal DqlQuery — strip context key if present (routing directive, not SD shape)
                queries.append({k: v for k, v in entry.items() if k != "context"})
        if queries:
            resolved[group_id] = queries
        else:
            log.warning("model_group_dql[%s]: resolved to empty list; dql_queries will be omitted", group_id)
    return resolved


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


def _build_type_node(entry: Dict[str, Any], no_display_name: bool = False) -> Any:
    """Build the ``type:`` value — enum dict when __enum present, else type string.

    Args:
        entry:           instruments-def entry dict.
        no_display_name: When ``True``, omit ``display_name`` from enum member nodes.

    Returns:
        Type string or enum dict.
    """
    enum_def = entry.get("__enum")
    if enum_def:
        members = []
        for m in enum_def.get("members", []):
            member: Dict[str, Any] = {
                "id": m["id"],  # plain — SD: no quotes on member id
                "value": _QuotedStr(m["value"]),  # double-quoted — SD convention
                "brief": m["brief"],
            }
            if "display_name" in m and not no_display_name:
                member["display_name"] = _SingleQuotedStr(m["display_name"])  # single-quoted
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
            return [[_SingleQuotedStr(item) for item in inner] for inner in example_raw]
        # Flat list — wrap in outer list
        log.debug("string[] field '%s': wrapping flat list example in outer list", key)
        return [[_SingleQuotedStr(item) for item in example_raw]]

    # Scalar — try JSON parse first
    as_str = str(example_raw).strip()
    if as_str.startswith("["):
        try:
            parsed = json.loads(as_str)
            if isinstance(parsed, list):
                log.debug("string[] field '%s': parsed JSON array scalar example", key)
                return [[_SingleQuotedStr(item) for item in parsed]]
        except (json.JSONDecodeError, ValueError):
            log.debug("string[] field '%s': JSON parse failed on scalar; wrapping as single string", key)

    return [[_SingleQuotedStr(as_str)]]


def _emit_id_entry(key: str, entry: Dict[str, Any], semdict_flag: str, no_display_name: bool = False) -> Dict[str, Any]:
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
        key:             Field key.
        entry:           instruments-def entry dict.
        semdict_flag:    ``new``, ``deprecated-alias``, or ``otel-only``.
        no_display_name: When ``True``, omit the ``display_name`` property from
                         the emitted node.

    Returns:
        Dict with all required semconv attribute fields.
    """
    attr_type = _build_type_node(entry, no_display_name=no_display_name)
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
            **({} if no_display_name else {"display_name": _SingleQuotedStr(str(entry["__display_name"]).strip() if entry.get("__display_name") else _make_display_name(key))}),
            "type": attr_type,
            "deprecated": deprecated_msg,
            "brief": description,
            "examples": examples,
        }
    else:
        node = {
            "id": key,
            **({} if no_display_name else {"display_name": _SingleQuotedStr(str(entry["__display_name"]).strip() if entry.get("__display_name") else _make_display_name(key))}),
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


def _coerce_attribute_example(value: Any, field_type: str = "") -> Any:  # pylint: disable=too-many-return-statements
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
        return _SingleQuotedStr("true" if value else "false")
    return _SingleQuotedStr(str(value).strip())


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
        "brief": description,
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


def _requote_scalars(doc: Dict[str, Any]) -> None:
    """Re-wrap string scalars that require explicit quoting after a YAML round-trip.

    yaml.safe_load strips subclass type info (_SingleQuotedStr, _QuotedStr), turning
    them back into plain str. This restores the correct quote style per SD convention:
    - attribute display_name: single-quoted
    - examples: single-quoted
    - member id: plain (no re-wrapping needed)
    - member value: double-quoted
    - member display_name: single-quoted
    """
    for group in doc.get("groups", []):
        for attr in group.get("attributes", []):
            if isinstance(attr.get("display_name"), str):
                attr["display_name"] = _SingleQuotedStr(attr["display_name"])
            if "examples" in attr:
                attr["examples"] = [_SingleQuotedStr(v) if isinstance(v, str) else v for v in attr["examples"]]
            attr_type = attr.get("type")
            if isinstance(attr_type, dict):
                for member in attr_type.get("members", []):
                    if isinstance(member.get("value"), str):
                        member["value"] = _QuotedStr(member["value"])
                    if isinstance(member.get("display_name"), str):
                        member["display_name"] = _SingleQuotedStr(member["display_name"])

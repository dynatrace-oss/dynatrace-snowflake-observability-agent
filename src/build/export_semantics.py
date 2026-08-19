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
import json
import logging
import os
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

import yaml
from ruamel.yaml import YAML as RuamelYAML

# Load .env file if present (never fails — python-dotenv optional, raw parsing fallback).
def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import]
        load_dotenv(env_path, override=False)
    except ImportError:
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_dotenv(Path(__file__).resolve().parents[2] / ".env")

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

#: Override map for doc/fields/ stub h2 headings keyed by group_id (ns_key after
#: stripping any .resource suffix).  Used when _make_title produces an inadequate
#: heading — e.g. the top-level "dsoa" group needs the full product name.
_FIELD_STUB_H2_OVERRIDES: Dict[str, str] = {
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

log = logging.getLogger(__name__)


##region YAML output helpers

_FLOW_SEQ_RE = re.compile(r"^(\s+\S+:\s*)\[([^\]]+)\]$", re.MULTILINE)


def _add_flow_seq_spaces(content: str) -> str:
    """Add spaces inside YAML flow-sequence brackets to match SD convention.

    Transforms ``['A']`` → ``[ 'A' ]``.  Only matches ``key: [...]`` patterns on
    their own line, so markdown links inside block scalars are unaffected.
    """
    return _FLOW_SEQ_RE.sub(r"\1[ \2 ]", content)


def _make_ruamel_yaml() -> RuamelYAML:
    """Return a ruamel.yaml instance configured for round-trip YAML processing.

    ``preserve_quotes=True`` keeps single/double/block-scalar styles intact.
    ``indent(mapping=2, sequence=4, offset=2)`` matches the SD 2-space list style
    so existing files are re-emitted byte-for-byte (including inline comments)
    except for appended DSOA additions.
    """
    ry = RuamelYAML()
    ry.preserve_quotes = True
    ry.width = 4096
    ry.indent(mapping=2, sequence=4, offset=2)
    return ry


def _merge_into_ruamel(existing, new) -> None:
    """Merge DSOA groups from *new* CommentedMap into *existing* CommentedMap in-place.

    Preserves all existing content (including inline comments) unchanged.
    Appends new group IDs or new attribute IDs not already present.
    For attributes that already exist, updates mutable scalar fields (``brief``,
    ``stability``, ``deprecated``, ``type``, ``examples``) so that description
    and metadata changes in instruments-def are reflected on re-export without
    requiring ``--clean``.  Inline comments on unchanged keys are preserved.
    Blank-line spacing from the last SD-native attribute is mirrored on each
    appended DSOA attribute so the output matches SD style.

    Also handles ``model_group`` and ``model`` top-level envelope keys: updates
    ``dql_queries`` (and other scalar/list keys like ``brief``, ``title``, and — for
    ``model`` — ``data_object``) from *new* when the value is non-empty, so
    model-group DQL query lists and per-plugin model scalar-field fixes propagate
    on re-export without ``--clean``. ``groups``/``attributes`` merging is applied
    relative to whichever envelope (``model``, or the document root for
    envelope-less files like resource/signal field docs) actually holds them.

    Also updates an already-existing *group's own* ``title``/``brief`` scalars (not
    just its attributes) from *new* when present — without this, a group-level
    text fix (e.g. the observed_timestamp brief casing correction, or the DSOA
    subtitle abbreviation) computed in memory would never reach an already-committed
    group of the same id, since only attribute-level scalars were previously updated.
    This is scoped to DSOA-owned groups only (``SD_OWNED_GROUP_PREFIXES``): many groups
    DSOA merely contributes attributes into (``authentication``, ``client``, ``db``,
    ``event``) are owned by the SD team with their own title/brief text, and DSOA's
    in-memory ``new_group`` for those is only a generic computed placeholder, never
    meant to be authoritative.
    """
    # Scalar fields on an existing attribute that we always overwrite from new.
    _UPDATABLE_KEYS = frozenset({"brief", "stability", "deprecated", "type", "examples", "note"})
    # Scalar fields on an existing *group* (not its attributes) that we propagate from
    # new → existing when new has a non-empty value, for DSOA-owned groups only — e.g.
    # group-level title/brief text fixes (DSOA subtitle abbreviation, observed_timestamp
    # brief casing).
    _GROUP_UPDATABLE_KEYS = frozenset({"title", "brief"})
    # Top-level model_group keys we propagate from new → existing when new has a value.
    # parent_model_group_id is included so the sub-model-group hierarchy (e.g. wiring
    # snowflake.logs/.events/.spans under the parent "snowflake" model_group) is picked
    # up on re-export without --clean.
    _MG_UPDATABLE_KEYS = frozenset({"brief", "title", "dql_queries", "parent_model_group_id"})
    # Top-level model keys we propagate from new → existing when new has a value.
    # data_object is included so schema-convention fixes (e.g. singular → plural) on
    # already-committed model files are picked up on re-export without --clean.
    _MODEL_UPDATABLE_KEYS = frozenset({"brief", "title", "data_object", "dql_queries"})

    # Handle model_group top-level key (model group files use this instead of "groups").
    if "model_group" in existing and "model_group" in new:
        ex_mg = existing["model_group"]
        new_mg = new["model_group"]
        for key in _MG_UPDATABLE_KEYS:
            val = new_mg.get(key)
            if val:  # propagate only when new has a non-empty value
                ex_mg[key] = val
            elif key in ex_mg and val is not None:
                # new explicitly has the key but empty — remove from existing
                del ex_mg[key]

    # Handle model top-level key (per-plugin log/event/span/metric model files nest their
    # scalar fields — including data_object — and groups: under this envelope rather than
    # at the document root). Without this, scalar fixes like a data_object plurality
    # correction never propagate to already-committed files on re-export.
    existing_container, new_container = existing, new
    if "model" in existing and "model" in new:
        ex_m = existing["model"]
        new_m = new["model"]
        for key in _MODEL_UPDATABLE_KEYS:
            val = new_m.get(key)
            if val:
                ex_m[key] = val
            elif key in ex_m and val is not None:
                del ex_m[key]
        existing_container, new_container = ex_m, new_m

    if "groups" not in existing_container or "groups" not in new_container:
        return
    existing_by_id = {g["id"]: g for g in existing_container.get("groups", [])}
    for new_group in new_container.get("groups", []):
        gid = new_group["id"]
        if gid in existing_by_id:
            ex_g = existing_by_id[gid]
            # Propagate group-level scalar fixes (title/brief) — but ONLY for groups DSOA
            # actually owns (SD_OWNED_GROUP_PREFIXES). Many groups DSOA merely contributes
            # attributes into (authentication, client, db, event) are owned by the SD team
            # with their own carefully-written title/brief; DSOA's in-memory `new_group`
            # dict for those is only a generic computed placeholder used for its own
            # bookkeeping, never meant to be authoritative — propagating it here would
            # silently clobber genuine SD-team content on every DSOA re-export.
            if any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                for key in _GROUP_UPDATABLE_KEYS:
                    val = new_group.get(key)
                    if val:
                        ex_g[key] = val
            ex_attrs = ex_g.get("attributes", [])
            ex_ids = {a.get("id") or a.get("ref"): i for i, a in enumerate(ex_attrs)}
            # Capture the blank-line token used before the last SD-native attribute.
            blank_token = None
            if ex_attrs and hasattr(ex_attrs, "ca"):
                last_idx = len(ex_attrs) - 1
                ca_entry = ex_attrs.ca.items.get(last_idx)
                if ca_entry:
                    blank_token = ca_entry[0]
            for new_attr in new_group.get("attributes", []):
                attr_key = new_attr.get("id") or new_attr.get("ref")
                if attr_key not in ex_ids:
                    idx = len(ex_attrs)
                    ex_attrs.append(new_attr)
                    if blank_token is not None and hasattr(ex_attrs, "ca"):
                        ex_attrs.ca.items.setdefault(idx, [None, None, None, None])
                        ex_attrs.ca.items[idx][0] = blank_token
                else:
                    # Attribute already exists: update mutable scalar fields.
                    ex_attr = ex_attrs[ex_ids[attr_key]]
                    for key in _UPDATABLE_KEYS:
                        if key in new_attr:
                            ex_attr[key] = new_attr[key]
                        elif key in ex_attr:
                            del ex_attr[key]
        else:
            existing_container["groups"].append(new_group)


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

    # YAML 1.1 treats these bare words as booleans or nulls; double-quote them so the SD
    # generator (which uses a YAML 1.1-aware parser) reads them as strings.
    _YAML11_BOOL_SYNONYMS: ClassVar[frozenset] = frozenset({
        # Boolean synonyms
        "y", "Y", "yes", "Yes", "YES", "n", "N", "no", "No", "NO",
        "true", "True", "TRUE", "false", "False", "FALSE",
        "on", "On", "ON", "off", "Off", "OFF",
        # Null synonyms (YAML 1.1: none/null/~ all resolve to null)
        "~", "null", "Null", "NULL", "none", "None", "NONE",
    })

    def represent_str(self, data: str):
        """Represent strings as YAML scalars with appropriate quoting.

        - Multi-line strings use literal block style (``|``) for readability.
        - Strings that are YAML 1.1 boolean synonyms (off, TRUE, yes, …) use
          double-quote style so downstream parsers always read them as strings.
        - Everything else uses PyYAML's default (plain or single-quoted as needed).

        Args:
            data: String value to represent.

        Returns:
            YAML scalar node.
        """
        if "\n" in data:
            # Use folded (>) for single-line content with trailing newline; literal (|) for
            # true multi-line content (e.g. DQL queries) where newlines must be preserved.
            style = ">" if data.endswith("\n") and data.count("\n") == 1 else "|"
            return self.represent_scalar("tag:yaml.org,2002:str", data, style=style)
        if data in self._YAML11_BOOL_SYNONYMS:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style='"')
        return self.represent_scalar("tag:yaml.org,2002:str", data)

    def represent_sequence(self, tag, sequence, flow_style=None):
        """Use flow style for single-scalar sequences (e.g. ``examples: [ false ]``).

        The SD convention writes single-value example arrays inline.  Multi-element
        sequences keep block style via the ``increase_indent`` override.

        Args:
            tag:        YAML tag for the sequence.
            sequence:   The Python sequence to represent.
            flow_style: Explicit flow_style override; respected if provided.

        Returns:
            YAML sequence node.
        """
        if flow_style is None and sequence and not any(isinstance(v, (dict, list)) for v in sequence):
            flow_style = True
        return super().represent_sequence(tag, sequence, flow_style=flow_style)


_IndentedDumper.add_representer(str, _IndentedDumper.represent_str)


class _QuotedStr(str):
    """String that is always serialised with double-quote YAML style.

    Used for enum member ``id`` and ``value`` fields so that all member scalars
    have a consistent explicit string tag — avoiding the SD generator's type
    checker treating differently-styled scalars (e.g. ``"off"`` vs ``literals``)
    as different types.
    """


def _represent_quoted_str(dumper: _IndentedDumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


_IndentedDumper.add_representer(_QuotedStr, _represent_quoted_str)


class _SingleQuotedStr(str):
    """String that is always serialised with single-quote YAML style.

    Used for attribute example values so they match hand-authored SD YAML convention.
    """


def _represent_single_quoted_str(dumper: _IndentedDumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


_IndentedDumper.add_representer(_SingleQuotedStr, _represent_single_quoted_str)


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
    parts = [_WORD_SUBS.get(p, p) for p in parts]
    return _restore_acronyms(" ".join(p.title() for p in parts))


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
                "id": m["id"],                               # plain — SD: no quotes on member id
                "value": _QuotedStr(m["value"]),             # double-quoted — SD convention
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
            **({} if no_display_name else {"display_name": _SingleQuotedStr(_make_display_name(key))}),
            "type": attr_type,
            "deprecated": deprecated_msg,
            "brief": description,
            "examples": examples,
        }
    else:
        node = {
            "id": key,
            **({} if no_display_name else {"display_name": _SingleQuotedStr(_make_display_name(key))}),
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
                attr["examples"] = [
                    _SingleQuotedStr(v) if isinstance(v, str) else v
                    for v in attr["examples"]
                ]
            attr_type = attr.get("type")
            if isinstance(attr_type, dict):
                for member in attr_type.get("members", []):
                    if isinstance(member.get("value"), str):
                        member["value"] = _QuotedStr(member["value"])
                    if isinstance(member.get("display_name"), str):
                        member["display_name"] = _SingleQuotedStr(member["display_name"])


##region SemanticExporter


class SemanticExporter:
    """Reads instruments-def.yml files and emits Semantic Dictionary YAML.

    Attributes:
        repo_root:   Absolute path to the repository root.
        output_dir:  Directory where generated YAML files are written.
        schema_path: Optional path to ``semconv.schema.json`` for validation.
    """

    def __init__(self, repo_root: Path, output_dir: Path, schema_path: Optional[Path] = None, sd_metadata: bool = False, no_display_name: bool = False) -> None:
        """Initialise the exporter.

        Args:
            repo_root:        Repository root path.
            output_dir:       Output directory (created on demand).
            schema_path:      Optional semconv JSON schema for validation.
            sd_metadata:      When ``True``, write SD metadata files alongside the YAML source:
                              ``OWNERS``, ``definitions/mapping/global_field_categories.json``,
                              and ``doc/`` model/field stubs required by the SD generator.
                              Set this only when targeting the actual SD repo checkout —
                              **not** for the regular ``make semantic-dictionary`` export to
                              ``docs/semantic-dictionary/``.
            no_display_name:  When ``True``, suppress the ``display_name`` property on all
                              emitted attribute and enum member nodes.  Use when the target
                              SD PR should not include ``display_name`` fields (e.g. when the
                              SD committee has not yet approved them for a namespace).
        """
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.schema_path = schema_path
        self._sd_metadata = sd_metadata
        self._no_display_name = no_display_name
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
        node = _emit_id_entry(key, entry, semdict_flag, no_display_name=self._no_display_name)
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
                "title": _make_title(gid[: -len(".resource")] if gid.endswith(".resource") else gid) + " resource fields",
                "brief": f"Resource-level fields describing Snowflake {_make_title(gid)} entities.",
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

        # One file per group_id — snowflake_* groups are combined into a single snowflake.yaml
        docs: Dict[str, Dict[str, Any]] = {}
        for gid in sorted(groups_map):
            brief_subject = "observed timestamp" if gid == "observed_timestamp" else _make_title(gid)
            group_entry = {
                "id": gid,
                "type": groups_map[gid]["type"],
                "title": (_FIELD_STUB_H2_OVERRIDES.get(gid) or _make_title(gid)) + " signal fields",
                "brief": f"Signal-level fields for {brief_subject} telemetry.",
                "attributes": groups_map[gid]["attrs"],
            }
            if gid.startswith("snowflake"):
                rel_path = "fields/signal_fields/snowflake.yaml"
                if rel_path in docs:
                    docs[rel_path]["groups"].append(group_entry)
                else:
                    docs[rel_path] = {"groups": [group_entry]}
            else:
                filename = gid.replace(".", "_") + ".yaml"
                docs[f"fields/signal_fields/{filename}"] = {"groups": [group_entry]}
        return docs

    def _build_interfaces_yaml(self, all_entries: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Build interfaces_dsoa.yaml and interfaces_snowflake.yaml.

        Args:
            all_entries: All parsed field entries keyed by field key. When provided,
                         ``__interface_note`` values are read from each entry to annotate
                         ``ref:`` attributes in ``i.dsoa_resource`` with contextual notes.

        Returns:
            Tuple of (dsoa_doc, snowflake_doc) — semconv-compliant YAML doc dicts.
            dsoa_doc      → ``metrics/interfaces_dsoa.yaml``     (i.dsoa_resource)
            snowflake_doc → ``metrics/interfaces_snowflake.yaml`` (i.snowflake_warehouse, i.snowflake_database)
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

        dsoa_doc = {
            "groups": [
                {
                    "id": "i.dsoa_resource",
                    "type": "interface",
                    "title": "DSOA resource fields",
                    "brief": "Fields present on all DSOA telemetry records. Synced with config.py RESOURCE_ATTRIBUTES.",
                    "attributes": [_ref_entry(k) for k in sorted(RESOURCE_ATTRIBUTE_KEYS)],
                },
            ]
        }
        snowflake_doc = {
            "groups": [
                {
                    "id": "i.snowflake_warehouse",
                    "type": "interface",
                    "title": "Snowflake warehouse dimensions",
                    "brief": "Common warehouse dimensions for per-warehouse metrics.",
                    "attributes": [{"ref": "snowflake.warehouse.name"}, {"ref": "snowflake.warehouse.id"}],
                },
                {
                    "id": "i.snowflake_database",
                    "type": "interface",
                    "title": "Snowflake database dimensions",
                    "brief": "Common database/schema dimensions for per-database metrics.",
                    "attributes": [{"ref": "db.namespace"}, {"ref": "snowflake.schema.name"}],
                },
            ]
        }
        return dsoa_doc, snowflake_doc

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
            interfaces.append("i.snowflake_warehouse")
        if uses_database:
            interfaces.append("i.snowflake_database")
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
        interfaces = self._select_interfaces(metric_entries, all_entries, dim_plugins, dim_context_by_plugin)
        covered: Set[str] = set(RESOURCE_ATTRIBUTE_KEYS)
        if "i.snowflake_warehouse" in interfaces:
            covered |= INTERFACE_WAREHOUSE_KEYS
        if "i.snowflake_database" in interfaces:
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
            "id": f"snowflake.metrics.{plugin_name}",
            "title": f"Snowflake {_plugin_label(plugin_name)} metrics",
            "brief": f"Metrics collected by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
            "model_group_id": "snowflake.metrics",
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
        plugin_ts_keys = sorted(
            k for k, meta in event_ts_entries.items() if meta["plugin"] == plugin_name and k != "snowflake.event.trigger"
        )
        attrs = [{"ref": "snowflake.event.type"}] + [{"ref": k} for k in plugin_ts_keys]
        for _ in plugin_ts_keys:
            self._counters["event_timestamp_fields"] += 1
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.events.{plugin_name}",
            "title": f"Snowflake {_plugin_label(plugin_name)} lifecycle events",
            "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin via the OpenPipeline Events API.",
            "model_group_id": "snowflake.events",
            "data_object": "events",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        model_doc["groups"] = [
            {
                "id": f"snowflake.events.{plugin_name}.fields",
                "type": "attribute_group",
                "title": f"{_plugin_label(plugin_name, cap_first=True)} event fields",
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
        attr_refs = self._collect_plugin_attribute_refs(plugin_name, all_entries, exclude_span_only=True)
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.logs.{plugin_name}",
            "title": f"Snowflake {_plugin_label(plugin_name)} log records",
            "brief": f"Log records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "snowflake.logs",
            "data_object": "logs",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        if attr_refs:
            model_doc["groups"] = [
                {
                    "id": f"snowflake.logs.{plugin_name}.fields",
                    "type": "attribute_group",
                    "title": f"{_plugin_label(plugin_name, cap_first=True)} log record fields",
                    "brief": f"Attribute fields for {_make_display_name(plugin_name)} log records.",
                    "attributes": attr_refs,
                }
            ]
        else:
            model_doc["groups"] = []
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
        attr_refs = self._collect_plugin_attribute_refs(plugin_name, all_entries)
        model_doc: Dict[str, Any] = {
            "id": f"snowflake.spans.{plugin_name}",
            "title": f"Snowflake {_plugin_label(plugin_name)} spans",
            "brief": f"Span records emitted by the DSOA {plugin_name} plugin.",
            "model_group_id": "snowflake.spans",
            "data_object": "spans",
            "interfaces": ["i.dsoa_resource"],
        }
        if dql_queries:
            model_doc["dql_queries"] = dql_queries
        if attr_refs:
            model_doc["groups"] = [
                {
                    "id": f"snowflake.spans.{plugin_name}.fields",
                    "type": "attribute_group",
                    "title": f"{_plugin_label(plugin_name, cap_first=True)} span fields",
                    "brief": f"Attribute fields for {_make_display_name(plugin_name)} spans.",
                    "attributes": attr_refs,
                }
            ]
        else:
            model_doc["groups"] = []
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

        When the target file already exists, DSOA groups are merged into it rather
        than replacing the file wholesale — preserving SD-maintained content in
        groups that DSOA does not own.

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
        _requote_scalars(doc)
        dsoa_text = yaml.dump(doc, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True, sort_keys=False, width=4096)
        dsoa_text = _add_flow_seq_spaces(dsoa_text)
        if not out_path.exists():
            out_path.write_text(dsoa_text, encoding="utf-8")
        else:
            # Use ruamel.yaml round-trip merge so inline comments in the existing file
            # (e.g. stability: experimental # traces-in-grail) are preserved.
            ry = _make_ruamel_yaml()
            dsoa_cm = ry.load(dsoa_text)
            with open(out_path, "r", encoding="utf-8") as fh:
                existing_cm = ry.load(fh)
            _merge_into_ruamel(existing_cm, dsoa_cm)
            buf = StringIO()
            ry.dump(existing_cm, buf)
            out_path.write_text(_add_flow_seq_spaces(buf.getvalue()), encoding="utf-8")
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    @property
    def _sd_root(self) -> Path:
        """Return the SD repo root directory for SD-metadata files (OWNERS, doc/, definitions/).

        When ``output_dir`` ends in ``source`` the SD root is ``output_dir.parent``
        (standard SD layout: ``<repo-root>/source/``).  Otherwise (e.g. when
        ``--output docs/semantic-dictionary`` is passed without a ``source/`` tier)
        the SD root is ``output_dir`` itself.
        """
        return self.output_dir.parent if self.output_dir.name == "source" else self.output_dir

    def _write_text(self, content: str, rel_path: str) -> Path:
        """Write a plain-text or Markdown file to the output directory."""
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    def _write_sd_root_text(self, content: str, rel_path: str) -> Path:
        """Write a plain-text file relative to the SD repo root (see :attr:`_sd_root`)."""
        out_path = self._sd_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    def _write_json(self, data: Any, rel_path: str) -> Path:
        """Write a JSON file to the output directory."""
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        log.debug("Wrote %s", out_path)
        self._counters["files"] += 1
        return out_path

    def _write_owners(self, content: str) -> Path:
        """Update the OWNERS file at the SD repo root with the DSOA section.

        The OWNERS file lives one level above source/ (i.e. output_dir.parent).
        An existing '## DSOA' block (from the start of that marker's own line
        through the next section header or EOF) is replaced; if none exists the
        section is appended.
        """
        owners_path = self._sd_root / "OWNERS"
        if owners_path.exists():
            existing = owners_path.read_text(encoding="utf-8")
            marker = "## DSOA"
            idx = existing.find(marker)
            if idx >= 0:
                # Back up to the start of the marker's own line so any leading
                # indentation on that line (OWNERS sections are indented, e.g.
                # "    ## DSOA") is removed together with the marker, rather than
                # left dangling as a stray whitespace-only line in `head` — that
                # stray indentation (never stripped by a plain .rstrip("\n"), which
                # only strips newlines, not spaces) is what caused a blank-ish
                # line to accumulate before "## DSOA" on every re-export.
                line_start = existing.rfind("\n", 0, idx) + 1
                head = existing[:line_start].rstrip()
                head = f"{head}\n\n" if head else ""
                # Find the next section header after the DSOA block, if any.
                # Indentation-aware ("\n[ \t]*## ") since OWNERS section headers
                # are indented — the previous "\n## " (no indentation allowed)
                # could never match, so a DSOA block followed by another section
                # would have silently deleted that section too (currently masked
                # only because DSOA happens to be the last section in the file).
                rest = existing[idx + len(marker):]
                next_match = re.search(r"\n[ \t]*## ", rest)
                tail = rest[next_match.start() + 1 :] if next_match else ""
            else:
                head = f"{existing.rstrip()}\n\n" if existing.strip() else ""
                tail = ""
        else:
            owners_path.parent.mkdir(parents=True, exist_ok=True)
            head, tail = "", ""
        new_text = head + content.rstrip("\n") + "\n"
        if tail:
            new_text += f"\n{tail}"
        owners_path.write_text(new_text, encoding="utf-8")
        log.debug("Wrote %s", owners_path)
        self._counters["files"] += 1
        return owners_path

    def _build_owners_entries(self, signal_group_ids: List[str], resource_group_ids: List[str], plugin_names: List[str]) -> str:
        """Generate the DSOA section of the Semantic Dictionary OWNERS file.

        Returns text suitable for pasting into OWNERS. The path list is derived
        from the groups actually generated in the current export run so it stays
        in sync with the YAML output automatically.

        Args:
            signal_group_ids:  Group IDs from the generated signal_fields docs.
            resource_group_ids: Group IDs from the generated resource_fields docs.
            plugin_names:      Sorted list of plugin names that have metrics.
        """
        paths: List[str] = []

        # Resource field source files
        sf_res_file = "source/fields/resource_fields/snowflake_resource.yaml"
        dsoa_res_file = "source/fields/resource_fields/dsoa.yaml"
        if any(gid.startswith("snowflake") or gid.startswith("db") for gid in resource_group_ids):
            paths.append(sf_res_file)
        if any(gid.startswith("dsoa") or gid.startswith("deployment") for gid in resource_group_ids):
            paths.append(dsoa_res_file)

        # Signal field source files — DSOA-owned groups and shared groups we co-contribute to
        # (authentication, client, db, event are SD-shared but we write into them; they must be
        # listed in OWNERS so the F027 sanity check does not fire)
        snowflake_added = False
        for gid in sorted(signal_group_ids):
            if not any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                continue
            if gid.startswith("snowflake"):
                if not snowflake_added:
                    paths.append("source/fields/signal_fields/snowflake.yaml")
                    snowflake_added = True
            else:
                filename = gid.replace(".", "_") + ".yaml"
                paths.append(f"source/fields/signal_fields/{filename}")

        # Shared signal field files we merge DSOA fields into (not DSOA-exclusive but co-owned)
        for shared_group in sorted({"authentication", "client", "db", "event"}):
            shared_path = f"source/fields/signal_fields/{shared_group}.yaml"
            if shared_path not in paths:
                paths.append(shared_path)

        # Metrics files
        paths.append("source/metrics/snowflake_metrics_**")
        paths.append("source/metrics/interfaces_dsoa.yaml")
        paths.append("source/metrics/interfaces_snowflake.yaml")

        # Model files
        paths.append("source/model/snowflake/**")

        # doc/fields files for DSOA-owned groups. snowflake.* groups (signal and resource)
        # are consolidated into a single doc/fields/snowflake.md — add it once.
        snowflake_doc_added = False
        for gid in sorted(signal_group_ids) + sorted(resource_group_ids):
            if not any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                continue
            if gid == "snowflake" or gid.startswith("snowflake."):
                if not snowflake_doc_added:
                    paths.append("doc/fields/snowflake.md")
                    snowflake_doc_added = True
            else:
                md_name = gid.replace(".", "_") + ".md"
                doc_path = f"doc/fields/{md_name}"
                if doc_path not in paths:
                    paths.append(doc_path)

        # doc/model
        paths.append("doc/model/snowflake/**")

        # Format as OWNERS syntax
        lines = ["    ## DSOA - Dynatrace Snowflake Observability Agent"]
        indent = "        "
        lines.append("    path " + (", \\\n" + indent).join(paths))
        for owner in SD_OWNERS:
            lines.append(f"        {owner}")
        lines.append("")
        return "\n".join(lines)

    def _update_field_categories(self, signal_group_ids: List[str], resource_group_ids: List[str]) -> None:
        """Merge the DSOA entry into definitions/mapping/global_field_categories.json.

        Reads the existing SD file at the SD repo root (if present), otherwise falls back
        to the seed copy at ``scripts/tools/global_field_categories.json``.  Injects the
        DSOA category under ``SD_FIELD_CATEGORY`` and writes the result in-place to the
        SD repo root path so all other categories are preserved.
        """
        gfc_path = self._sd_root / "definitions" / "mapping" / "global_field_categories.json"
        seed_path = self.repo_root / "scripts" / "tools" / "global_field_categories.json"
        existing: Dict[str, Any] = {}
        if gfc_path.exists():
            with open(gfc_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        elif seed_path.exists():
            log.debug("global_field_categories.json not found at SD root; using seed from %s", seed_path)
            with open(seed_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        existing[SD_FIELD_CATEGORY] = {
            "display_name": SD_FIELD_CATEGORY_DISPLAY_NAME,
            "description": SD_FIELD_CATEGORY_DESCRIPTION,
            "signal_groups": sorted(signal_group_ids),
            "resource_groups": sorted(resource_group_ids),
        }
        gfc_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gfc_path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        log.debug("Wrote %s", gfc_path)
        self._counters["files"] += 1

    def _build_model_doc_stubs(self, sub_groups: Optional[Set[str]] = None) -> Dict[str, str]:
        """Generate doc/model/snowflake/{logs,events,spans}/readme.md stubs.

        These Markdown files are required by the SD generator (model_group tags).
        Also emits the parent doc/model/snowflake/readme.md stub (group id
        ``snowflake``) when at least one sub-group was written this run — its
        ``<!-- model_group snowflake -->`` block links to whichever of the
        logs/events/spans readmes actually exist.

        Args:
            sub_groups: Subset of ``{"logs", "events", "spans"}`` identifying which
                        sub-group model_groups were actually written this run. When
                        None (default), all three are assumed present (back-compat).

        Returns:
            Dict mapping relative output path → file content. Update
            SD_PM / SD_MAINTAINER / SD_TEAM constants at the top of this module
            to change the ownership table.
        """
        all_stubs = {
            "snowflake.logs": ("Snowflake log records", "Log records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE and system views."),
            "snowflake.events": ("Snowflake lifecycle events", "Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace OpenPipeline Events API."),
            "snowflake.spans": ("Snowflake spans", "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views."),
        }
        if sub_groups is None:
            sub_groups = {"logs", "events", "spans"}
        stubs = {gid: info for gid, info in all_stubs.items() if gid.split(".")[1] in sub_groups}
        result: Dict[str, str] = {}
        for group_id, (title, description) in stubs.items():
            subdir = group_id.split(".")[1]  # logs, events, spans
            content = (
                f"<!-- model_group {group_id} -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                f"## {title}\n"
                "\n"
                f"{description}\n"
                "\n"
                "<!-- end_model_group -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/model/snowflake/{subdir}/readme.md"] = content
        if sub_groups:
            content = (
                "<!-- model_group snowflake -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                "## Snowflake\n"
                "\n"
                "<!-- end_model_group -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result["doc/model/snowflake/readme.md"] = content
        return result

    def _build_per_model_doc_stubs(self, models: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate per-model doc/model/snowflake/<type>/<plugin>.md stub files.

        The SD generator reads these stubs and fills in the ``<!-- model <id> -->``
        sections with the generated attribute tables and DQL examples.  Without them
        the generator has nothing to populate and the F001 / F004 / F025 sanity
        checks fire for every undefined model.

        Each stub contains the ``<!-- model <id> --> … <!-- end_model -->`` block
        (populated by the generator with the model description and DQL examples) plus,
        when the model has an inner ``attribute_group``, a ``<!-- semconv <id>.fields -->``
        reference for it.  The inner-group reference is required — without it F025
        ("unused domain-specific groups") fires for every ``<model_id>.fields`` group,
        because the ``<!-- model -->`` tag documents the model itself but not its
        attribute groups.  This mirrors well-formed SD model docs (e.g. the Davis
        models, which reference each inner group with its own ``<!-- semconv -->`` tag).
        Models without an inner group (``has_fields`` False, e.g. the attribute-less
        ``event_log`` span model) omit the reference to avoid a dangling-group error.

        Args:
            models: List of dicts with keys ``id`` (model ID, e.g.
                    ``snowflake.logs.metering``), ``title``, ``brief``,
                    ``signal_type`` (``logs``, ``events``, ``spans``), and
                    ``has_fields`` (whether the model has an inner ``.fields`` group).

        Returns:
            Dict mapping relative output path (``doc/model/snowflake/…``) → content.
        """
        result: Dict[str, str] = {}
        for model in models:
            model_id = model["id"]
            title = model["title"]
            brief = model.get("brief", "")
            signal_type = model["signal_type"]  # logs | events | spans
            has_fields = model.get("has_fields", True)
            plugin = model_id.split(".")[-1]    # last segment is the plugin name
            # The model's inner attribute_group is always ``<model_id>.fields`` (see
            # _build_*_model_yaml). It must be referenced with its own semconv tag so
            # F025 does not flag it as an unused domain-specific group — but only when
            # the model actually declares that group.
            fields_ref = f"<!-- semconv {model_id}.fields -->\n<!-- end_semconv -->\n\n" if has_fields else ""
            content = (
                f"<!-- model {model_id} -->\n"
                "<!-- The content between the markdown start and end comments (tags) is generated. Please do not edit manually. -->\n"
                "\n"
                f"## {title}\n"
                "\n"
                f"{brief}\n"
                "\n"
                "<!-- end_model -->\n"
                "\n"
                f"{fields_ref}"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/model/snowflake/{signal_type}/{plugin}.md"] = content
        return result

    def _build_per_field_doc_stubs(self, field_groups: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate doc/fields/<group_id_normalized>.md stubs for DSOA-owned signal field groups.

        The SD generator reads these stubs and fills in the ``<!-- semconv <group_id> -->``
        sections with rendered attribute tables.  Without them, field groups have no
        documentation entry in the SD and the F001/F004/F025 sanity checks can fire for
        any signal_fields file that depends on them.

        Each stub is minimal — a heading and the semconv marker.  The generator replaces
        everything between ``<!-- semconv <id> -->`` and ``<!-- end_semconv -->`` with the
        rendered attribute table and description.

        The filename is the group ID with dots replaced by underscores, matching the SD
        convention (e.g. ``snowflake.account`` → ``doc/fields/snowflake_account.md``).

        Exception: any group whose id is ``snowflake`` or starts with ``snowflake.``
        (both signal-field groups and the snowflake resource-field groups) is routed
        into a single consolidated ``doc/fields/snowflake.md`` file instead — one
        shared ``## Snowflake`` h2 followed by one ``### <title>`` + semconv block per
        group, mirroring the multi-block-per-file pattern used by
        ``doc/fields/azure_resource.md`` in the SD repo. The ``dsoa`` resource-field
        group is a different domain and keeps its own separate file.

        The ``## h2`` heading uses the namespace name in sentence case — no ``fields``
        or ``resource`` suffix, matching the SD doc convention seen in
        ``doc/fields/host.md``, ``doc/fields/app.md`` (e.g. ``## Snowflake warehouse``).
        Groups with a ``.resource`` id suffix have that part stripped before titling.
        The YAML ``title:`` (with the "fields" suffix) is rendered as the ``### h3``
        heading inside the semconv block by the SD generator itself.

        Args:
            field_groups: List of dicts with keys ``group_id`` (e.g.
                          ``snowflake.account``), ``title`` (e.g.
                          ``Snowflake account signal fields``), and ``is_resource``
                          (``True`` for resource_fields-origin groups).

        Returns:
            Dict mapping relative output path (``doc/fields/…``) → stub content.
        """
        result: Dict[str, str] = {}
        snowflake_groups: List[Dict[str, Any]] = []
        for fg in field_groups:
            group_id = fg["group_id"]
            if group_id == "snowflake" or group_id.startswith("snowflake."):
                snowflake_groups.append(fg)
                continue
            # h2 heading: sentence-case namespace, no "fields" or "resource" suffix.
            # Strip any ".resource" id suffix so "snowflake.warehouse.resource" → "## Snowflake warehouse".
            ns_key = group_id[: -len(".resource")] if group_id.endswith(".resource") else group_id
            h2_title = _FIELD_STUB_H2_OVERRIDES.get(ns_key) or _make_title(ns_key)
            filename = group_id.replace(".", "_") + ".md"
            content = (
                f"## {h2_title}\n"
                "\n"
                f"<!-- semconv {group_id} -->\n"
                "<!-- end_semconv -->\n"
                "\n"
                "<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result[f"doc/fields/{filename}"] = content

        if snowflake_groups:
            # Consolidate all snowflake / snowflake.* groups into a single doc/fields/snowflake.md
            # file: one shared "## Snowflake" h2, then one semconv stub block per group (sorted
            # by group_id for determinism), and one shared ownership table at the end —
            # mirroring doc/fields/azure_resource.md's multi-block-per-file pattern. The SD
            # generator fills in each block's own "### <title>" heading from the YAML title —
            # no manual h3 is emitted here (matching the azure_resource.md stub shape exactly).
            blocks: List[str] = ["## Snowflake\n"]
            for fg in sorted(snowflake_groups, key=lambda x: x["group_id"]):
                group_id = fg["group_id"]
                blocks.append(f"\n<!-- semconv {group_id} -->\n<!-- end_semconv -->\n")
            content = "".join(blocks) + (
                "\n<!-- dynatrace_internal -->\n"
                "| Responsible PM | Maintainer | Team |\n"
                "|---|---|---|\n"
                f"| {SD_PM} | {SD_MAINTAINER} | {SD_TEAM} |\n"
                "<!-- end_dynatrace_internal -->\n"
            )
            result["doc/fields/snowflake.md"] = content
        return result

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

        # Resolve model_group_dql from its dedicated tooling file (expands use_plugin_dql references).
        _mg_dql_path = self.repo_root / "scripts" / "tools" / "model-group-dql.yml"
        _core_raw: Dict[str, Any] = {}
        if _mg_dql_path.exists():
            try:
                with open(_mg_dql_path, "r", encoding="utf-8") as fh:
                    _core_raw = yaml.safe_load(fh) or {}
            except Exception as exc:  # pylint: disable=broad-except
                log.warning("Could not read model_group_dql file from %s: %s", _mg_dql_path, exc)
        else:
            log.warning("model_group_dql file not found at %s", _mg_dql_path)
        resolved_mg_dql = _resolve_model_group_dql(_core_raw.get("model_group_dql"), plugin_dql_queries)
        log.info("Resolved model_group_dql for %d group(s): %s", len(resolved_mg_dql), sorted(resolved_mg_dql))

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
        dsoa_iface_doc, sf_iface_doc = self._build_interfaces_yaml(all_entries)
        p = self._write_yaml(dsoa_iface_doc, "metrics/interfaces_dsoa.yaml")
        self._validate_against_schema(dsoa_iface_doc, p)
        p = self._write_yaml(sf_iface_doc, "metrics/interfaces_snowflake.yaml")
        self._validate_against_schema(sf_iface_doc, p)
        self._write_yaml(
            {
                "model_group": {
                    "id": "snowflake.metrics",
                    "title": "Snowflake metrics",
                    "brief": "Metrics collected by the DSOA from Snowflake ACCOUNT_USAGE views.",
                    **({} if not resolved_mg_dql.get("snowflake.metrics") else {"dql_queries": resolved_mg_dql["snowflake.metrics"]}),
                }
            },
            "metrics/snowflake_metrics_model_group.yaml",
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
            p = self._write_yaml(doc, f"metrics/snowflake_metrics_{plugin_name}.yaml")
            self._validate_against_schema(doc, p)

        # Step 9: per-plugin event models
        plugins_with_events: Set[str] = {meta["plugin"] for k, meta in event_ts_entries.items() if k != "snowflake.event.trigger"}
        if plugins_with_events:
            self._write_yaml(
                {
                    "model_group": {
                        "id": "snowflake.events",
                        "title": "Snowflake lifecycle events",
                        "brief": "Timestamp-based state-change events emitted by DSOA plugins via the Dynatrace OpenPipeline Events API.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.events") else {"dql_queries": resolved_mg_dql["snowflake.events"]}),
                    }
                },
                "model/snowflake/events/model_group_snowflake_events.yaml",
            )
            for plugin_name in sorted(plugins_with_events):
                doc = self._build_event_model_yaml(
                    plugin_name,
                    event_ts_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "events"),
                )
                p = self._write_yaml(doc, f"model/snowflake/events/snowflake.events.{plugin_name}.yaml")
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
                        "id": "snowflake.logs",
                        "title": "Snowflake log records",
                        "brief": "Log records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE and system views.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.logs") else {"dql_queries": resolved_mg_dql["snowflake.logs"]}),
                    }
                },
                "model/snowflake/logs/model_group_snowflake_logs.yaml",
            )
            for plugin_name in sorted(plugins_with_attrs):
                doc = self._build_log_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "logs"),
                )
                p = self._write_yaml(doc, f"model/snowflake/logs/snowflake.logs.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        # Step 11: per-plugin span models (only for SPAN_PLUGINS)
        span_model_plugins = plugins_with_attrs & SPAN_PLUGINS
        if span_model_plugins:
            self._write_yaml(
                {
                    "model_group": {
                        "id": "snowflake.spans",
                        "title": "Snowflake spans",
                        "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                        "parent_model_group_id": "snowflake",
                        **({} if not resolved_mg_dql.get("snowflake.spans") else {"dql_queries": resolved_mg_dql["snowflake.spans"]}),
                    }
                },
                "model/snowflake/spans/model_group_snowflake_spans.yaml",
            )
            for plugin_name in sorted(span_model_plugins):
                doc = self._build_span_model_yaml(
                    plugin_name,
                    all_entries,
                    dql_queries=_dql_for_context(plugin_dql_queries.get(plugin_name), "spans"),
                )
                p = self._write_yaml(doc, f"model/snowflake/spans/snowflake.spans.{plugin_name}.yaml")
                self._validate_against_schema(doc, p)

        # Generate span model for event_log even if it has no attributes
        # (event_log emits spans from its SQL context; span fields are tracked as dimensions)
        if "event_log" in SPAN_PLUGINS and "event_log" not in span_model_plugins:
            if not span_model_plugins:  # model_group not yet written
                self._write_yaml(
                    {
                        "model_group": {
                            "id": "snowflake.spans",
                            "title": "Snowflake spans",
                            "brief": "Span records emitted by DSOA plugins from Snowflake ACCOUNT_USAGE views.",
                            "parent_model_group_id": "snowflake",
                            **({} if not resolved_mg_dql.get("snowflake.spans") else {"dql_queries": resolved_mg_dql["snowflake.spans"]}),
                        }
                    },
                    "model/snowflake/spans/model_group_snowflake_spans.yaml",
                )
            doc = self._build_span_model_yaml(
                "event_log",
                all_entries,
                dql_queries=_dql_for_context(plugin_dql_queries.get("event_log"), "spans"),
            )
            p = self._write_yaml(doc, "model/snowflake/spans/snowflake.spans.event_log.yaml")
            self._validate_against_schema(doc, p)

        # Step 11b: parent "snowflake" model_group — only when at least one of the
        # events/logs/spans sub-groups was actually written this run. The bullet list
        # only references subfolders that exist.
        written_sub_groups: Set[str] = set()
        if plugins_with_events:
            written_sub_groups.add("events")
        if plugins_with_attrs:
            written_sub_groups.add("logs")
        if span_model_plugins or ("event_log" in SPAN_PLUGINS and "event_log" not in span_model_plugins):
            written_sub_groups.add("spans")
        if written_sub_groups:
            bullet_labels = {
                "events": "[Lifecycle events](./events/readme.md)",
                "logs": "[Log records](./logs/readme.md)",
                "spans": "[Spans](./spans/readme.md)",
            }
            bullets = "\n".join(f"* {bullet_labels[sg]}" for sg in ("events", "logs", "spans") if sg in written_sub_groups)
            self._write_yaml(
                {
                    "model_group": {
                        "id": "snowflake",
                        "title": "Snowflake",
                        "brief": ("DSOA (Dynatrace Snowflake Observability Agent) telemetry models, organized by signal type:\n\n" + bullets),
                    }
                },
                "model/snowflake/model_group_snowflake.yaml",
            )

        # Step 12: SD metadata — OWNERS, field categories, and doc stubs.
        # Only written when targeting the actual SD repo (--sd-metadata flag).
        # Never written for the regular 'make semantic-dictionary' export to docs/.
        if self._sd_metadata:
            signal_group_ids = [g["id"] for doc in sig_docs.values() for g in doc.get("groups", [])]
            resource_group_ids = [g["id"] for g in sf_res_doc.get("groups", [])] + [g["id"] for g in dsoa_res_doc.get("groups", [])]
            plugin_names_sorted = sorted(plugin_metric_entries.keys() - {"_core"})
            self._write_owners(self._build_owners_entries(signal_group_ids, resource_group_ids, plugin_names_sorted))
            self._update_field_categories(signal_group_ids, resource_group_ids)
            for rel_path, content in self._build_model_doc_stubs(sub_groups=written_sub_groups).items():
                self._write_sd_root_text(content, rel_path)

            # Per-model doc stubs (logs, events, spans) — required by the SD generator to
            # populate the ``<!-- model <id> -->`` sections (F001/F004/F025 root cause A).
            per_model_stubs: List[Dict[str, Any]] = []
            for plugin_name in sorted(plugins_with_attrs):
                per_model_stubs.append({
                    "id": f"snowflake.logs.{plugin_name}",
                    "title": f"Snowflake {_plugin_label(plugin_name)} log records",
                    "brief": f"Log records emitted by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE and system views.",
                    "signal_type": "logs",
                    "has_fields": True,
                })
            for plugin_name in sorted(plugins_with_events):
                per_model_stubs.append({
                    "id": f"snowflake.events.{plugin_name}",
                    "title": f"Snowflake {_plugin_label(plugin_name)} lifecycle events",
                    "brief": f"Timestamp-based state-change events emitted by the DSOA {plugin_name} plugin via the OpenPipeline Events API.",
                    "signal_type": "events",
                    "has_fields": True,
                })
            all_span_plugins = span_model_plugins | ({"event_log"} if "event_log" in SPAN_PLUGINS else set())
            for plugin_name in sorted(all_span_plugins):
                per_model_stubs.append({
                    "id": f"snowflake.spans.{plugin_name}",
                    "title": f"Snowflake {_plugin_label(plugin_name)} spans",
                    "brief": f"Span records emitted by the DSOA {plugin_name} plugin from Snowflake ACCOUNT_USAGE views.",
                    "signal_type": "spans",
                    # A span model has an inner <plugin>.fields attribute_group only when it
                    # has attribute refs (span_model_plugins). event_log is added even without
                    # attributes and therefore has empty groups — no inner semconv reference.
                    "has_fields": plugin_name in span_model_plugins,
                })
            for rel_path, content in self._build_per_model_doc_stubs(per_model_stubs).items():
                self._write_sd_root_text(content, rel_path)

            # Per-field-group doc stubs — required by the SD generator to populate the
            # ``<!-- semconv <group_id> -->`` sections in doc/fields/ (point 3 of review).
            # Titles are derived from sig_docs (Option A) to avoid re-reading YAML.
            sig_group_titles: Dict[str, str] = {
                g["id"]: g.get("title", "")
                for doc in sig_docs.values()
                for g in doc.get("groups", [])
            }
            field_stubs = [
                {"group_id": gid, "title": sig_group_titles.get(gid, ""), "is_resource": False}
                for gid in sorted(sig_group_titles)
                if any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES)
            ]
            # Also include resource_fields groups (dsoa, snowflake.resource_monitor.resource,
            # snowflake.warehouse.resource) — they are global groups and require a doc stub
            # so the SD generator can find them (otherwise F003 fires).  These originate from
            # the resource_fields docs, so their h2 heading carries a " resource" qualifier.
            res_group_titles: Dict[str, str] = {
                g["id"]: g.get("title", "")
                for res_doc in (sf_res_doc, dsoa_res_doc)
                for g in res_doc.get("groups", [])
            }
            for gid, title in sorted(res_group_titles.items()):
                if any(gid == p or gid.startswith(p + ".") for p in SD_OWNED_GROUP_PREFIXES):
                    field_stubs.append({"group_id": gid, "title": title, "is_resource": True})
            for rel_path, content in self._build_per_field_doc_stubs(field_stubs).items():
                self._write_sd_root_text(content, rel_path)

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
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output) if Path(args.output).is_absolute() else repo_root / args.output
    schema_path = Path(args.schema) if Path(args.schema).is_absolute() else repo_root / args.schema
    log.info("Repo root : %s", repo_root)
    log.info("Output dir: %s", output_dir)
    exporter = SemanticExporter(repo_root=repo_root, output_dir=output_dir, schema_path=schema_path, sd_metadata=args.sd_metadata, no_display_name=args.no_display_name)
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

"""YAML serialization helpers for the Semantic Dictionary export.

Provides the custom PyYAML dumper (indentation + quoting conventions required
by the Dynatrace Semantic Dictionary), the ruamel.yaml round-trip merge used
to preserve hand-authored content on re-export, and the ``ExportError``
raised on fatal validation failures.
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

import re
from typing import ClassVar

import yaml
from ruamel.yaml import YAML as RuamelYAML

from build.semantic_exporter.constants import SD_OWNED_GROUP_PREFIXES

##region Data structures


class ExportError(Exception):
    """Raised when export encounters a fatal validation error."""


##endregion


##region YAML output helpers

_FLOW_SEQ_RE = re.compile(r"^(\s+\S+:\s*)\[([^\]]+)\]$", re.MULTILINE)


def add_flow_seq_spaces(content: str) -> str:
    """Add spaces inside YAML flow-sequence brackets to match SD convention.

    Transforms ``['A']`` → ``[ 'A' ]``.  Only matches ``key: [...]`` patterns on
    their own line, so markdown links inside block scalars are unaffected.
    """
    return _FLOW_SEQ_RE.sub(r"\1[ \2 ]", content)


def make_ruamel_yaml() -> RuamelYAML:
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


def merge_into_ruamel(existing, new) -> None:
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
    _UPDATABLE_KEYS = frozenset({"brief", "stability", "deprecated", "type", "examples", "note", "display_name"})
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


class IndentedDumper(yaml.Dumper):  # pylint: disable=too-many-ancestors
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

    Example — IndentedDumper (correct for SD)::

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
    _YAML11_BOOL_SYNONYMS: ClassVar[frozenset] = frozenset(
        {
            # Boolean synonyms
            "y",
            "Y",
            "yes",
            "Yes",
            "YES",
            "n",
            "N",
            "no",
            "No",
            "NO",
            "true",
            "True",
            "TRUE",
            "false",
            "False",
            "FALSE",
            "on",
            "On",
            "ON",
            "off",
            "Off",
            "OFF",
            # Null synonyms (YAML 1.1: none/null/~ all resolve to null)
            "~",
            "null",
            "Null",
            "NULL",
            "none",
            "None",
            "NONE",
        }
    )

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


IndentedDumper.add_representer(str, IndentedDumper.represent_str)


class QuotedStr(str):
    """String that is always serialised with double-quote YAML style.

    Used for enum member ``id`` and ``value`` fields so that all member scalars
    have a consistent explicit string tag — avoiding the SD generator's type
    checker treating differently-styled scalars (e.g. ``"off"`` vs ``literals``)
    as different types.
    """


def _represent_quoted_str(dumper: IndentedDumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


IndentedDumper.add_representer(QuotedStr, _represent_quoted_str)


class SingleQuotedStr(str):
    """String that is always serialised with single-quote YAML style.

    Used for attribute example values so they match hand-authored SD YAML convention.
    """


def _represent_single_quoted_str(dumper: IndentedDumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


IndentedDumper.add_representer(SingleQuotedStr, _represent_single_quoted_str)


##endregion

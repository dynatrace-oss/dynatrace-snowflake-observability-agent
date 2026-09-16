"""Tests validating that src/build/semantic_exporter/ faithfully converts instruments-def to SD YAML.

These tests verify the fidelity of the export pipeline: every field, enum, brief,
and example in ``instruments-def.yml`` must appear correctly in the generated output.
Tests run the actual ``SemanticExporter`` against real instruments-def files.

Note:
    All tests use ``@pytest.mark.integration`` because they invoke the full
    export pipeline and read real source files.
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

from typing import Any, Dict, List, Set

import pytest

from build.semantic_exporter import KNOWN_REFS
from test.core._semdict_test_utils import load_all_generated_yaml, load_all_instruments_defs

##region Fixtures


def _load_all_instruments_defs() -> Dict[str, Dict[str, Any]]:
    """Thin wrapper around shared utility.

    Returns:
        Dict mapping plugin name to parsed YAML data.
    """
    return load_all_instruments_defs()


def _load_generated_yaml_files() -> Dict[str, Dict[str, Any]]:
    """Thin wrapper around shared utility.

    Returns:
        Dict mapping relative path to parsed YAML content.
    """
    return load_all_generated_yaml()


def _collect_all_output_attr_nodes(generated_docs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build a flat map of field_key → attribute_node from all generated files.

    Collects both ``id:`` (full definition) and ``ref:`` (reference) entries
    from all groups across all files.

    Args:
        generated_docs: All parsed generated YAML docs.

    Returns:
        Dict mapping field key to the attribute node dict.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    for doc in generated_docs.values():
        for group in doc.get("groups", []):
            for attr in group.get("attributes", []):
                key = attr.get("id") or attr.get("ref")
                if key and key not in nodes:
                    nodes[key] = attr
        model = doc.get("model", {})
        for group in model.get("groups", []):
            for attr in group.get("attributes", []):
                key = attr.get("id") or attr.get("ref")
                if key and key not in nodes:
                    nodes[key] = attr
    return nodes


def _collect_enum_fields(all_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Collect all fields with __enum definitions across all instruments-def files.

    Returns the first (winning) definition per key — mirrors export dedup.

    Args:
        all_defs: Parsed instruments-def data keyed by plugin name.

    Returns:
        Dict mapping field key to entry dict (with __enum).
    """
    enum_fields: Dict[str, Dict[str, Any]] = {}
    for plugin_name, data in all_defs.items():
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, entry in (data.get(section) or {}).items():
                if key not in enum_fields and (entry or {}).get("__enum"):
                    enum_fields[key] = {"entry": entry, "plugin": plugin_name, "section": section}
    return enum_fields


##endregion


##region Tests


@pytest.mark.integration
class TestEnumPreservation:
    """Every __enum in instruments-def must produce an enum type in generated output."""

    def test_all_enums_preserved_in_output(self):
        """Every field with __enum in any instruments-def.yml must have dict type in output.

        A plain ``type: string`` in output for a field that has ``__enum`` in source
        indicates the enum loss bug (Concern 5 / C5). The cross-plugin dedup logic
        must prefer the enum-rich definition.

        Specifically catches: snowflake.query.execution_status, db.operation.name,
        snowflake.warehouse.type, snowflake.object.type, snowflake.object.ddl.operation.
        """
        all_defs = _load_all_instruments_defs()
        generated = _load_generated_yaml_files()

        enum_fields = _collect_enum_fields(all_defs)
        output_nodes = _collect_all_output_attr_nodes(generated)

        violations = []
        for key, meta in enum_fields.items():
            node = output_nodes.get(key)
            if node is None:
                violations.append(f"{key} (plugin={meta['plugin']}): field with __enum not found in output")
                continue
            type_val = node.get("type")
            if not isinstance(type_val, dict):
                violations.append(
                    f"{key} (plugin={meta['plugin']}): has __enum in source but " f"output type is {type_val!r} (should be a dict/enum)"
                )
        assert not violations, "Enum definitions lost in export:\n" + "\n".join(violations)

    def test_enum_member_values_preserved(self):
        """Every enum member value from instruments-def must appear in output.

        Validates that enum union (when both definitions have __enum) does not
        drop any member values.
        """
        all_defs = _load_all_instruments_defs()
        generated = _load_generated_yaml_files()

        output_nodes = _collect_all_output_attr_nodes(generated)

        # Build expected values per field (union across all plugins)
        expected_by_field: Dict[str, Set[str]] = {}
        for _plugin, data in all_defs.items():
            for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
                for key, entry in (data.get(section) or {}).items():
                    enum_def = (entry or {}).get("__enum", {})
                    if enum_def:
                        expected_by_field.setdefault(key, set())
                        for m in enum_def.get("members", []):
                            if m.get("value"):
                                expected_by_field[key].add(str(m["value"]))

        violations = []
        for key, expected_values in expected_by_field.items():
            node = output_nodes.get(key)
            if node is None or not isinstance(node.get("type"), dict):
                continue  # handled by test_all_enums_preserved_in_output
            output_type = node["type"]
            output_values = {str(m["value"]) for m in output_type.get("members", []) if m.get("value")}
            missing = expected_values - output_values
            if missing:
                violations.append(f"{key}: missing enum members {sorted(missing)}")
        assert not violations, "Missing enum member values in output:\n" + "\n".join(violations)


@pytest.mark.integration
class TestFieldCompleteness:
    """Every field in instruments-def must appear in the generated output."""

    def test_all_fields_present_in_output(self):
        """No field key should be silently dropped during export.

        Tests that every key from every instruments-def.yml (attributes,
        dimensions, event_timestamps sections) is present in the generated output.
        Metrics are checked separately.

        Excluded:
        - __semdict: ref fields (they appear as ref: not id:, which is correct).
        - snowflake.event.trigger: intentionally excluded from signal fields (special event key).
        - _core plugin metrics: intentionally skipped by the exporter (DSOA self-monitoring).
        """
        # Fields intentionally excluded from the generated output by the export pipeline.
        INTENTIONALLY_EXCLUDED: frozenset = frozenset(
            {
                "snowflake.event.trigger",  # special event field; excluded from signal_fields by design
            }
        )
        all_defs = _load_all_instruments_defs()
        generated = _load_generated_yaml_files()

        output_nodes = _collect_all_output_attr_nodes(generated)
        # Also collect metric keys from metric model files
        output_metric_keys: Set[str] = set()
        for doc in generated.values():
            model = doc.get("model", {})
            for group in model.get("groups", []):
                if group.get("type") == "metric" or "instrument" in group:
                    metric_id = group.get("id") or group.get("metric_name")
                    if metric_id:
                        output_metric_keys.add(metric_id)

        # Collect source keys (dedup: first wins per key across all plugins)
        source_keys: Dict[str, str] = {}  # key → plugin
        for plugin_name, data in all_defs.items():
            for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
                for key, entry in (data.get(section) or {}).items():
                    if key not in source_keys:
                        source_keys[key] = plugin_name

        violations = []
        for key, plugin_name in source_keys.items():
            # Skip intentionally excluded fields
            if key in INTENTIONALLY_EXCLUDED:
                continue
            # Skip KNOWN_REFS — always emitted as ref: in interfaces, never as id: in field files
            if key in KNOWN_REFS:
                continue
            # Skip _core metrics — intentionally not exported (DSOA self-monitoring)
            if plugin_name == "_core":
                # Check if it's a metric section field from _core
                core_data = all_defs.get("_core", {})
                if key in (core_data.get("metrics") or {}):
                    continue

            # Skip keys that are __semdict: ref in ALL definitions
            is_always_ref = True
            for data in all_defs.values():
                for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
                    entry = (data.get(section) or {}).get(key)
                    if entry and (entry.get("__semdict") or "new") != "ref":
                        is_always_ref = False
                        break
                if not is_always_ref:
                    break
            if is_always_ref:
                continue  # ref-only fields are emitted as ref: (no id:) — correct

            # Check if in output (as id: or in metric models)
            if key not in output_nodes and key not in output_metric_keys:
                violations.append(f"{key} (first in plugin={plugin_name}): not found in generated output")

        assert not violations, "Fields missing from export output:\n" + "\n".join(violations)


@pytest.mark.integration
class TestBriefPreservation:
    """Every __description in instruments-def must appear as brief in output."""

    def test_brief_not_empty(self):
        """Every id: attribute node in generated output must have a non-empty brief.

        A missing or empty brief indicates a __description was lost during export.
        """
        generated = _load_generated_yaml_files()

        violations: List[str] = []
        for rel_path, doc in generated.items():
            for group in doc.get("groups", []):
                for attr in group.get("attributes", []):
                    if "id" not in attr:
                        continue  # ref: entry; no brief required
                    brief = attr.get("brief", "")
                    if not brief or not str(brief).strip():
                        violations.append(f"{rel_path}: id={attr['id']} has empty brief")
            # Also check metric model groups
            model = doc.get("model", {})
            for group in model.get("groups", []):
                brief = group.get("brief", "")
                if group.get("instrument") or group.get("type") == "metric":
                    if not brief or not str(brief).strip():
                        violations.append(f"{rel_path}[model]: metric {group.get('id', '?')} has empty brief")
        assert not violations, "Attribute nodes with empty brief:\n" + "\n".join(violations)


@pytest.mark.integration
class TestExamplePreservation:
    """Every output id: attribute must have at least one example."""

    def test_examples_not_empty(self):
        """Every id: attribute node in generated output must have a non-empty examples list.

        Checks that examples are not dropped during export. This test validates the
        export pipeline does not silently produce empty examples lists, without checking
        the exact value (since dedup may promote a richer definition whose example differs
        from the first-seen plugin's example).
        """
        generated = _load_generated_yaml_files()

        output_nodes = _collect_all_output_attr_nodes(generated)

        violations: List[str] = []
        for key, node in output_nodes.items():
            if "id" not in node:
                continue  # ref: entry; no examples required
            out_examples = node.get("examples", [])
            if not out_examples:
                violations.append(f"{key}: examples list is empty in output")

        assert not violations, "Attribute nodes with empty examples:\n" + "\n".join(violations)


##endregion

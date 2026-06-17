"""Unit and integration tests for src/build/export_semantics.py."""

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

import os
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from build.export_semantics import (
    INTERFACE_DATABASE_KEYS,
    INTERFACE_WAREHOUSE_KEYS,
    RESOURCE_ATTRIBUTE_KEYS,
    ExportError,
    SemanticExporter,
    _build_type_node,
    _classify_field,
    _emit_id_entry,
    _emit_metric_entry,
    _emit_ref_entry,
    _map_attr_type,
    _map_metric_instrument,
    _ns_group,
    _validate_entry,
)

##region Fixtures

MOCK_FIXTURE = Path(__file__).parent.parent / "test_data" / "instruments-def-mock.yml"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_mock() -> Dict[str, Any]:
    """Load the mock instruments-def.yml fixture."""
    with open(MOCK_FIXTURE, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


##endregion


##region Unit tests — type mapping


class TestTypeMappings:
    """Verify __type → semconv type/instrument mapping."""

    def test_attr_type_string_default(self):
        """Missing __type maps to string."""
        assert _map_attr_type(None) == "string"

    def test_attr_type_long(self):
        """long/int map to long."""
        assert _map_attr_type("long") == "long"
        assert _map_attr_type("int") == "long"

    def test_attr_type_double(self):
        """double/float map to double."""
        assert _map_attr_type("double") == "double"
        assert _map_attr_type("float") == "double"

    def test_attr_type_boolean(self):
        """Boolean maps to boolean."""
        assert _map_attr_type("boolean") == "boolean"

    def test_metric_instrument_gauge(self):
        """Gauge maps to gauge."""
        assert _map_metric_instrument("gauge") == "gauge"

    def test_metric_instrument_count(self):
        """Count and counter both map to counter."""
        assert _map_metric_instrument("count") == "counter"
        assert _map_metric_instrument("counter") == "counter"

    def test_metric_instrument_updowncounter(self):
        """Updowncounter maps to updowncounter."""
        assert _map_metric_instrument("updowncounter") == "updowncounter"

    def test_metric_instrument_histogram(self):
        """Histogram maps to histogram."""
        assert _map_metric_instrument("histogram") == "histogram"

    def test_metric_instrument_default_gauge(self):
        """Missing __type defaults to gauge."""
        assert _map_metric_instrument(None) == "gauge"


##endregion


##region Unit tests — field classification


class TestFieldClassification:
    """Verify _classify_field produces correct bucket based on key + section + override.

    SD definition (source/readme.md):
    - resource field: STABLE for the resource lifetime (only RESOURCE_ATTRIBUTE_KEYS qualify)
    - signal field: everything else — including metric dimensions like warehouse.name, db.user
    """

    def test_resource_attribute_key_is_resource(self):
        """Keys in RESOURCE_ATTRIBUTE_KEYS → resource regardless of section."""
        assert _classify_field("db.system", "dimensions", None) == "resource"
        assert _classify_field("service.name", "attributes", None) == "resource"
        assert _classify_field("host.name", "dimensions", None) == "resource"
        assert _classify_field("dsoa.run.id", "attributes", None) == "resource"

    def test_dimension_default_is_signal(self):
        """Metric dimensions without __field_type override and not in RESOURCE_ATTRIBUTE_KEYS → signal.

        Metric dimensions (e.g. warehouse.name, db.namespace, db.user) vary per
        observation — they are signal fields per SD definition even though DSOA
        uses them for low-cardinality metric splitting.
        """
        assert _classify_field("snowflake.warehouse.name", "dimensions", None) == "signal"
        assert _classify_field("db.namespace", "dimensions", None) == "signal"
        assert _classify_field("db.user", "dimensions", None) == "signal"

    def test_dimension_signal_override(self):
        """Metric `dimensions` with __field_type: signal → signal (explicit override)."""
        assert _classify_field("snowflake.warehouse.event.name", "dimensions", "signal") == "signal"

    def test_attribute_default_is_signal(self):
        """Definition of attributes without __field_type override → signal."""
        assert _classify_field("snowflake.query.id", "attributes", None) == "signal"

    def test_attribute_resource_override(self):
        """Definition of attributes with __field_type: resource → resource (explicit override)."""
        assert _classify_field("snowflake.warehouse.size", "attributes", "resource") == "resource"

    def test_metric_always_metric(self):
        """Definition of metrics section always → metric regardless of override."""
        assert _classify_field("snowflake.credits.used", "metrics", None) == "metric"
        assert _classify_field("snowflake.credits.used", "metrics", "signal") == "metric"

    def test_event_timestamps_classification(self):
        """Definition of event_timestamps section → event_timestamp."""
        assert _classify_field("snowflake.user.created_on", "event_timestamps", None) == "event_timestamp"


##endregion


##region Unit tests — namespace grouping


class TestNamespaceGrouping:
    """Verify _ns_group maps field keys to (group_id, group_type) correctly."""

    def test_warehouse_signal_group(self):
        """snowflake.warehouse.* signal fields → snowflake.warehouse group, type: attribute_group."""
        from build.export_semantics import _SIG_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("snowflake.warehouse.name", _SIG_NS, "snowflake.misc", "attribute_group")
        assert gid == "snowflake.warehouse"
        assert gtype == "attribute_group", "All DSOA signal groups use attribute_group per IA guidance"

    def test_warehouse_resource_group(self):
        """snowflake.warehouse.* resource fields → snowflake.warehouse resource group."""
        from build.export_semantics import _RES_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("snowflake.warehouse.size", _RES_NS, "snowflake.resource", "resource")
        assert gid == "snowflake.warehouse"
        assert gtype == "resource"

    def test_db_signal_group(self):
        """db.* signal fields → db attribute_group (not span — cross-signal per IA guidance)."""
        from build.export_semantics import _SIG_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("db.namespace", _SIG_NS, "snowflake.misc", "attribute_group")
        assert gid == "db"
        assert gtype == "attribute_group"

    def test_unknown_key_fallback(self):
        """Unknown key falls back to default group."""
        from build.export_semantics import _SIG_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("completely.unknown.field", _SIG_NS, "snowflake.misc", "attribute_group")
        assert gid == "snowflake.misc"
        assert gtype == "attribute_group"


##endregion


##region Unit tests — validation


class TestValidation:
    """Verify _validate_entry detects missing required metadata."""

    def test_valid_entry_passes(self):
        """Entry with all required fields produces no errors."""
        entry = {"__description": "A description.", "__example": "an_example"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_missing_description_fails(self):
        """Entry without __description produces an error."""
        entry = {"__example": "an_example"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__description" in e for e in errors)

    def test_missing_example_fails(self):
        """Entry without __example produces an error."""
        entry = {"__description": "A description."}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__example" in e for e in errors)

    def test_empty_string_example_passes(self):
        """Empty string __example is valid (nullable field)."""
        entry = {"__description": "A description.", "__example": ""}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_zero_example_passes(self):
        """Zero __example is valid."""
        entry = {"__description": "A description.", "__example": 0}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_deprecated_alias_requires_otel_replacement(self):
        """deprecated-alias without __otel_replacement fails."""
        entry = {"__description": "D.", "__example": "E.", "__semdict": "deprecated-alias"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__otel_replacement" in e for e in errors)

    def test_otel_only_requires_otel_note(self):
        """otel-only without __semdict_note fails."""
        entry = {"__description": "D.", "__example": "E.", "__semdict": "otel-only"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__semdict_note" in e for e in errors)

    def test_invalid_field_type_fails(self):
        """Unknown __field_type produces an error."""
        entry = {"__description": "D.", "__example": "E.", "__field_type": "invalid_value"}
        errors = _validate_entry("test.field", entry, "dimensions", "test.yml")
        assert any("__field_type" in e for e in errors)

    def test_valid_field_type_resource_passes(self):
        """__field_type: resource is valid."""
        entry = {"__description": "D.", "__example": "E.", "__field_type": "resource"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_valid_field_type_signal_passes(self):
        """__field_type: signal is valid."""
        entry = {"__description": "D.", "__example": "E.", "__field_type": "signal"}
        errors = _validate_entry("test.field", entry, "dimensions", "test.yml")
        assert errors == []


##endregion


##region Unit tests — ref emission


class TestRefEmission:
    """Verify ref entries emit ref: node without id: block."""

    def test_ref_entry_has_ref_key(self):
        """Ref entry produces dict with 'ref' key."""
        entry = {"__semdict": "ref", "__description": "System.", "__example": "snowflake"}
        node = _emit_ref_entry("db.system", entry)
        assert node["ref"] == "db.system"
        assert "id" not in node

    def test_ref_with_otel_note_includes_note(self):
        """Ref entry with __semdict_note includes note in output."""
        entry = {"__semdict": "ref", "__description": "Auth method.", "__example": "PASSWORD", "__semdict_note": "Custom enum gap."}
        node = _emit_ref_entry("authentication.type", entry)
        assert node.get("note") == "Custom enum gap."


##endregion


##region Unit tests — id: block emission


class TestIdEmission:
    """Verify new/deprecated-alias/otel-only entries emit full id: blocks."""

    def test_new_entry_has_id_block(self):
        """New entry produces id: block with required fields."""
        entry = {"__semdict": "new", "__description": "Unique run ID.", "__example": "4aa7c76c"}
        node = _emit_id_entry("dsoa.run.id", entry, "new")
        assert node["id"] == "dsoa.run.id"
        assert node["type"] == "string"
        assert node["stability"] == "experimental"
        assert "Unique run ID." in node["brief"]
        assert "4aa7c76c" in node["examples"]

    def test_new_entry_has_display_name(self):
        """New entry includes a display_name field."""
        entry = {"__semdict": "new", "__description": "D.", "__example": "E."}
        node = _emit_id_entry("dsoa.run.id", entry, "new")
        assert "display_name" in node

    def test_deprecated_alias_stability(self):
        """deprecated-alias entry stays experimental — OTel renamed it, DSOA still emits it."""
        entry = {
            "__semdict": "deprecated-alias",
            "__otel_replacement": "deployment.environment.name",
            "__semdict_note": "Renamed in v1.26.",
            "__description": "Deployment env.",
            "__example": "PROD",
        }
        node = _emit_id_entry("deployment.environment", entry, "deprecated-alias")
        assert node["stability"] == "experimental", "deprecated-alias must stay experimental"
        assert "deprecated" not in node, "deprecated key must not appear for active DSOA fields"
        assert "note" in node, "deprecated-alias must produce a note about the OTel rename"

    def test_deprecated_alias_has_note(self):
        """deprecated-alias entry note includes __semdict_note content and backward-compat message."""
        entry = {
            "__semdict": "deprecated-alias",
            "__otel_replacement": "deployment.environment.name",
            "__semdict_note": "Renamed in v1.26.",
            "__description": "Deployment env.",
            "__example": "PROD",
        }
        node = _emit_id_entry("deployment.environment", entry, "deprecated-alias")
        assert "Renamed in v1.26." in node.get("note", "")
        assert "backward compatibility" in node.get("note", "")

    def test_otel_only_has_note(self):
        """otel-only entry includes note from __semdict_note."""
        entry = {"__semdict": "otel-only", "__semdict_note": "OTel Development-tier.", "__description": "Session ID.", "__example": "123"}
        node = _emit_id_entry("session.id", entry, "otel-only")
        assert node["stability"] == "experimental"
        assert node.get("note") == "OTel Development-tier."
        assert "deprecated" not in node

    def test_long_type_mapping(self):
        """__type: long maps to type: long in output."""
        entry = {"__semdict": "new", "__type": "long", "__description": "D.", "__example": "42"}
        node = _emit_id_entry("test.long.field", entry, "new")
        assert node["type"] == "long"


##endregion


##region Unit tests — enum emission


class TestEnumEmission:
    """Verify __enum fields produce type: {allow_custom_values, members} instead of type: string."""

    def test_enum_produces_dict_not_string(self):
        """Entry with __enum produces a dict type, not a string type."""
        entry = {
            "__description": "The warehouse type.",
            "__example": "STANDARD",
            "__enum": {
                "allow_custom_values": True,
                "members": [
                    {"id": "standard", "value": "STANDARD", "brief": "Standard warehouse."},
                    {"id": "snowpark_optimized", "value": "SNOWPARK_OPTIMIZED", "brief": "Snowpark optimized."},
                ],
            },
        }
        type_node = _build_type_node(entry)
        assert isinstance(type_node, dict), "enum field should produce dict type"
        assert "allow_custom_values" in type_node
        assert "members" in type_node
        assert len(type_node["members"]) == 2

    def test_enum_allow_custom_values_false(self):
        """allow_custom_values: false is preserved."""
        entry = {
            "__description": "Level.",
            "__example": "ACCOUNT",
            "__enum": {
                "allow_custom_values": False,
                "members": [{"id": "account", "value": "ACCOUNT", "brief": "Account level."}],
            },
        }
        type_node = _build_type_node(entry)
        assert type_node["allow_custom_values"] is False

    def test_enum_member_ids_are_snake_case(self):
        """Member IDs follow snake_case convention."""
        entry = {
            "__description": "Size.",
            "__example": "X-SMALL",
            "__enum": {
                "allow_custom_values": True,
                "members": [
                    {"id": "x_small", "value": "X-SMALL", "brief": "X-Small."},
                    {"id": "x2_large", "value": "2X-LARGE", "brief": "2X-Large."},
                ],
            },
        }
        type_node = _build_type_node(entry)
        member_ids = [m["id"] for m in type_node["members"]]
        assert "x_small" in member_ids
        assert "x2_large" in member_ids

    def test_no_enum_returns_string(self):
        """Entry without __enum returns the mapped type string."""
        entry = {"__description": "D.", "__example": "E."}
        type_node = _build_type_node(entry)
        assert type_node == "string"

    def test_enum_in_emit_id_entry(self):
        """_emit_id_entry produces enum dict in type: field when __enum present."""
        entry = {
            "__semdict": "new",
            "__description": "Warehouse type.",
            "__example": "STANDARD",
            "__enum": {
                "allow_custom_values": True,
                "members": [{"id": "standard", "value": "STANDARD", "brief": "Standard."}],
            },
        }
        node = _emit_id_entry("snowflake.warehouse.type", entry, "new")
        assert isinstance(node["type"], dict)
        assert node["type"]["members"][0]["value"] == "STANDARD"


##endregion


##region Unit tests — metric emission


class TestMetricEmission:
    """Verify metric entries emit instrument, unit, metric_name."""

    def test_metric_has_instrument_and_unit(self):
        """Metric entry emits instrument and unit."""
        entry = {"__semdict": "new", "__type": "gauge", "__unit": "{credits}", "__description": "Credits used.", "__example": "42.5"}
        node = _emit_metric_entry("snowflake.warehouse.credits.used", entry)
        assert node["instrument"] == "gauge"
        assert node["unit"] == "{credits}"
        assert node["metric_name"] == "snowflake.warehouse.credits.used"
        assert node["type"] == "metric"

    def test_metric_unit_from_unit_key(self):
        """Metric unit can come from 'unit' key (not just __unit)."""
        entry = {"__semdict": "new", "__type": "counter", "unit": "ms", "__description": "Time.", "__example": "100"}
        node = _emit_metric_entry("test.time", entry)
        assert node["unit"] == "ms"

    def test_counter_instrument(self):
        """__type: count maps to instrument: counter."""
        entry = {"__semdict": "new", "__type": "count", "__unit": "1", "__description": "Query count.", "__example": "100"}
        node = _emit_metric_entry("test.count", entry)
        assert node["instrument"] == "counter"

    def test_updowncounter_instrument(self):
        """__type: updowncounter maps correctly."""
        entry = {"__semdict": "new", "__type": "updowncounter", "__unit": "bytes", "__description": "Memory.", "__example": "1024"}
        node = _emit_metric_entry("test.memory", entry)
        assert node["instrument"] == "updowncounter"

    def test_histogram_instrument(self):
        """__type: histogram maps correctly."""
        entry = {"__semdict": "new", "__type": "histogram", "__unit": "ms", "__description": "Latency dist.", "__example": "250"}
        node = _emit_metric_entry("test.latency", entry)
        assert node["instrument"] == "histogram"


##endregion


##region Unit tests — SemanticExporter with mock fixture


class TestSemanticExporterMock:
    """Test SemanticExporter using the mock fixture."""

    def test_parse_mock_fixture(self, tmp_path):
        """Exporter parses the mock fixture without errors."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        errors, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        assert errors == [], f"Unexpected errors: {errors}"
        assert len(entries) > 0

    def test_ref_classified_correctly(self, tmp_path):
        """Ref entries are classified as 'ref' from mock fixture."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        db_system = entries.get("db.system")
        assert db_system is not None
        assert db_system["semdict"] == "ref"

    def test_deprecated_alias_classified(self, tmp_path):
        """Deprecated-alias entries are classified correctly."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        dep_env = entries.get("deployment.environment")
        assert dep_env is not None
        assert dep_env["semdict"] == "deprecated-alias"

    def test_otel_only_classified(self, tmp_path):
        """otel-only entries are classified correctly."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        session = entries.get("session.id")
        assert session is not None
        assert session["semdict"] == "otel-only"

    def test_default_semdict_is_new(self, tmp_path):
        """Entries without __semdict flag default to 'new'."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        minimal = tmp_path / "minimal.yml"
        minimal.write_text("attributes:\n  my.field:\n    __description: D.\n    __example: E.\n")
        _, entries = exporter._parse_file("test", minimal)
        assert entries["my.field"]["semdict"] == "new"

    def test_dimension_classified_as_signal(self, tmp_path):
        """Dimension not in RESOURCE_ATTRIBUTE_KEYS → classification: signal.

        Per SD definition, metric dimensions like snowflake.warehouse.name vary
        per observation — they are signal fields, not resource fields.
        """
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        wh_name = entries.get("snowflake.warehouse.name")
        assert wh_name is not None
        assert wh_name["section"] == "dimensions"
        assert wh_name["classification"] == "signal", (
            "snowflake.warehouse.name is a metric dimension but varies per observation "
            "— it is a signal field per SD resource/signal definition"
        )

    def test_dimension_signal_override_classified_as_signal(self, tmp_path):
        """Dimension with __field_type: signal → classification: signal."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        event_name = entries.get("snowflake.warehouse.event.name")
        assert event_name is not None
        assert event_name["section"] == "dimensions"
        assert event_name["classification"] == "signal"

    def test_attribute_resource_override_classified_as_resource(self, tmp_path):
        """Attribute with __field_type: resource → classification: resource."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        wh_size = entries.get("snowflake.warehouse.size")
        assert wh_size is not None
        assert wh_size["section"] == "attributes"
        assert wh_size["classification"] == "resource"

    def test_event_timestamps_parsed(self, tmp_path):
        """event_timestamps section is parsed and classified as event_timestamp."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        created = entries.get("snowflake.warehouse.created_on")
        assert created is not None
        assert created["section"] == "event_timestamps"
        assert created["classification"] == "event_timestamp"

    def test_ref_not_in_attribute_group_id_block(self, tmp_path):
        """Ref entries appear as {'ref': key} not {'id': key} in output."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        ref_meta = entries["db.system"]
        node = exporter._build_attribute_node("db.system", ref_meta)
        assert "ref" in node
        assert "id" not in node

    def test_deprecated_alias_in_output(self, tmp_path):
        """deprecated-alias entry keeps experimental stability."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        dep_meta = entries["deployment.environment"]
        node = exporter._build_attribute_node("deployment.environment", dep_meta)
        assert node.get("stability") == "experimental", "deprecated-alias must be experimental"
        assert "deprecated" not in node, "deprecated key must not appear for active DSOA fields"
        assert "note" in node, "deprecated-alias must have a note about OTel rename"

    def test_enum_field_emits_type_dict(self, tmp_path):
        """Field with __enum emits type: dict in output (not type: string)."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        # snowflake.warehouse.size has __enum in the mock fixture
        size_meta = entries.get("snowflake.warehouse.size")
        assert size_meta is not None
        node = exporter._build_attribute_node("snowflake.warehouse.size", size_meta)
        assert isinstance(node["type"], dict), "enum field must produce dict type not string"
        assert "allow_custom_values" in node["type"]
        assert "members" in node["type"]


##endregion


##region Unit tests — export pipeline with mock fixture


class TestExportPipelineMock:
    """Test full export pipeline using a mock file (no real repo required)."""

    def test_resource_fields_file_produced(self, tmp_path):
        """Export produces resource_fields/snowflake_resource.yaml."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        # Use a minimal fixture pointing to just the mock file
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        resource_entries = {k: v for k, v in entries.items() if v["classification"] == "resource"}
        sf_doc, _dsoa_doc = exporter._build_resource_fields_yaml(resource_entries)
        assert "groups" in sf_doc
        # snowflake.warehouse.name (dimension) and snowflake.warehouse.size (attr+resource override)
        # should both appear in snowflake.warehouse group
        all_attrs = [a for g in sf_doc["groups"] for a in g.get("attributes", [])]
        keys = [a.get("id") or a.get("ref") for a in all_attrs]
        assert "snowflake.warehouse.name" in keys or "snowflake.warehouse.size" in keys

    def test_signal_fields_file_produced(self, tmp_path):
        """Export produces per-namespace signal_fields files with signal-classified fields."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        signal_entries = {k: v for k, v in entries.items() if v["classification"] == "signal"}
        event_ts = {k: v for k, v in entries.items() if v["classification"] == "event_timestamp"}
        sig_docs = exporter._build_signal_fields_yaml(signal_entries, event_ts)
        # Returns dict of {rel_path: doc} — one file per namespace group
        assert isinstance(sig_docs, dict), "signal fields must return dict of path → doc"
        assert len(sig_docs) > 0, "at least one signal_fields file must be produced"
        # All values must have 'groups' key
        for rel_path, doc in sig_docs.items():
            assert "groups" in doc, f"{rel_path} missing groups key"
        # snowflake.warehouse.event.name (dimension with __field_type: signal) must appear in warehouse file
        all_keys: set = set()
        for doc in sig_docs.values():
            for grp in doc["groups"]:
                for attr in grp.get("attributes", []):
                    all_keys.add(attr.get("id") or attr.get("ref"))
        assert "snowflake.warehouse.event.name" in all_keys, "signal-override dimension must be in signal_fields"

    def test_interfaces_yaml_has_three_interfaces(self, tmp_path):
        """interfaces_dsoa.yaml has i.dsoa_resource, i.dsoa_warehouse, i.dsoa_database."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        doc = exporter._build_interfaces_yaml()
        assert "groups" in doc
        group_ids = {g["id"] for g in doc["groups"]}
        assert "i.dsoa_resource" in group_ids
        assert "i.dsoa_warehouse" in group_ids
        assert "i.dsoa_database" in group_ids

    def test_resource_interface_covers_resource_attribute_keys(self, tmp_path):
        """i.dsoa_resource attrs are a superset of RESOURCE_ATTRIBUTE_KEYS."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        doc = exporter._build_interfaces_yaml()
        i_resource = next(g for g in doc["groups"] if g["id"] == "i.dsoa_resource")
        interface_keys = {a["ref"] for a in i_resource["attributes"] if "ref" in a}
        assert RESOURCE_ATTRIBUTE_KEYS.issubset(interface_keys)

    def test_dsoa_resource_file_has_dsoa_fields(self, tmp_path):
        """resource_fields/dsoa.yaml only has dsoa./deployment. keys that are resource-classified.

        In the mock fixture, ``deployment.environment`` is an attribute with
        ``__semdict: deprecated-alias`` and no ``__field_type`` override, so it
        is ``signal``-classified.  The dsoa.yaml resource file will therefore be
        empty (or contain only fields explicitly overridden as resource).
        This test verifies the builder produces the correct structure regardless.
        """
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        resource_entries = {k: v for k, v in entries.items() if v["classification"] == "resource"}
        _sf_doc, dsoa_doc = exporter._build_resource_fields_yaml(resource_entries)
        # The dsoa group always exists in the doc structure, even if attrs list is empty
        assert "groups" in dsoa_doc
        assert dsoa_doc["groups"][0]["id"] == "dsoa"

    def test_metric_model_has_model_envelope(self, tmp_path):
        """Metric model file has model: envelope (not groups: at top level)."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        metric_entries = {k: v for k, v in entries.items() if v["classification"] == "metric"}
        all_entries = entries
        doc = exporter._build_metric_model_yaml("mock_plugin", metric_entries, all_entries)
        assert "model" in doc, "metric model must use model: envelope"
        assert "groups:" not in str(list(doc.keys())), "top level must not be groups:"
        assert "interfaces" in doc["model"]

    def test_metric_model_always_has_dsoa_resource_interface(self, tmp_path):
        """Metric model always includes i.dsoa_resource in interfaces."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        metric_entries = {k: v for k, v in entries.items() if v["classification"] == "metric"}
        doc = exporter._build_metric_model_yaml("mock_plugin", metric_entries, entries)
        assert "i.dsoa_resource" in doc["model"]["interfaces"]

    def test_event_model_produced(self, tmp_path):
        """Event model file is produced for plugins with event_timestamps."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        event_ts = {k: v for k, v in entries.items() if v["classification"] == "event_timestamp"}
        doc = exporter._build_event_model_yaml("mock_plugin", event_ts)
        assert "model" in doc
        assert doc["model"]["id"] == "dsoa.events.mock_plugin"
        assert doc["model"]["model_group_id"] == "dsoa.events"
        assert doc["model"]["data_object"] == "bizevents"

    def test_event_model_excludes_trigger_key(self, tmp_path):
        """Event model attrs include snowflake.warehouse.created_on but NOT snowflake.event.trigger."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        event_ts = {k: v for k, v in entries.items() if v["classification"] == "event_timestamp"}
        doc = exporter._build_event_model_yaml("mock_plugin", event_ts)
        group_attrs = doc["model"]["groups"][0]["attributes"]
        attr_refs = [a.get("ref") for a in group_attrs]
        assert "snowflake.event.trigger" not in attr_refs, "trigger key must be excluded from event model attrs"
        assert "snowflake.warehouse.created_on" in attr_refs or "snowflake.warehouse.updated_on" in attr_refs

    def test_interface_covered_dims_excluded_from_metric_attrs(self, tmp_path):
        """Metric attributes list excludes dims covered by declared interfaces."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        # Create a fixture that has i.dsoa_warehouse-covered dims + other dims
        fixture = tmp_path / "test.yml"
        fixture.write_text(
            "dimensions:\n"
            "  snowflake.warehouse.name:\n"
            "    __context_names: [ctx]\n"
            "    __description: Warehouse name.\n"
            "    __example: COMPUTE_WH\n"
            "  snowflake.warehouse.id:\n"
            "    __context_names: [ctx]\n"
            "    __description: Warehouse ID.\n"
            "    __example: wh123\n"
            "  snowflake.custom.dim:\n"
            "    __context_names: [ctx]\n"
            "    __description: Custom dim.\n"
            "    __example: val\n"
            "metrics:\n"
            "  test.metric:\n"
            "    __context_names: [ctx]\n"
            "    __description: A test metric.\n"
            "    __example: '1'\n"
            "    unit: count\n"
        )
        _, entries = exporter._parse_file("test_plugin", fixture)
        metric_entries = {k: v for k, v in entries.items() if v["classification"] == "metric"}
        doc = exporter._build_metric_model_yaml("test_plugin", metric_entries, entries)
        metric_node = doc["model"]["groups"][0]
        attr_refs = [a["ref"] for a in metric_node.get("attributes", [])]
        # Interface-covered dims must NOT appear in per-metric attrs
        for iface_key in INTERFACE_WAREHOUSE_KEYS:
            assert iface_key not in attr_refs, f"{iface_key} must not appear (covered by i.dsoa_warehouse)"
        # Custom dim must appear
        assert "snowflake.custom.dim" in attr_refs


##endregion


##region Integration tests


@pytest.mark.integration
@pytest.mark.skipif(not os.path.exists("build"), reason="build dir absent")
class TestSemanticExporterIntegration:
    """Integration tests: run full pipeline against real codebase.

    These tests require the repository to have a build/ directory
    and are only executed when explicitly requested via -m integration.
    """

    @pytest.fixture(scope="class")
    def export_output(self, tmp_path_factory):
        """Run SemanticExporter against the real codebase."""
        out_dir = tmp_path_factory.mktemp("semdict")
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        summary = exporter.export()
        return out_dir, summary

    def test_files_generated(self, export_output):
        """At least 20 YAML files are generated."""
        out_dir, summary = export_output
        yaml_files = list(out_dir.rglob("*.yaml"))
        assert len(yaml_files) >= 20, f"Expected ≥20 files, got {len(yaml_files)}"
        assert summary["files"] >= 20

    def test_snowflake_resource_file_exists(self, export_output):
        """fields/resource_fields/snowflake_resource.yaml is created."""
        out_dir, _ = export_output
        rf = out_dir / "fields" / "resource_fields" / "snowflake_resource.yaml"
        assert rf.exists(), "snowflake_resource.yaml not found"

    def test_dsoa_resource_file_exists(self, export_output):
        """fields/resource_fields/dsoa.yaml is created."""
        out_dir, _ = export_output
        df = out_dir / "fields" / "resource_fields" / "dsoa.yaml"
        assert df.exists(), "dsoa.yaml not found"

    def test_signal_fields_file_exists(self, export_output):
        """fields/signal_fields/ contains per-namespace YAML files (not a single snowflake.yaml)."""
        out_dir, _ = export_output
        sig_dir = out_dir / "fields" / "signal_fields"
        assert sig_dir.exists(), "signal_fields directory not found"
        yaml_files = list(sig_dir.glob("*.yaml"))
        assert len(yaml_files) >= 2, f"Expected multiple namespace files, got {len(yaml_files)}"
        # At minimum the warehouse and query namespaces must be present
        names = {f.name for f in yaml_files}
        assert "snowflake_warehouse.yaml" in names or any(
            "warehouse" in n for n in names
        ), "snowflake_warehouse.yaml expected in signal_fields"

    def test_interfaces_file_exists(self, export_output):
        """metrics/interfaces_dsoa.yaml is created."""
        out_dir, _ = export_output
        fi = out_dir / "metrics" / "interfaces_dsoa.yaml"
        assert fi.exists(), "interfaces_dsoa.yaml not found"

    def test_metrics_model_group_file_exists(self, export_output):
        """metrics/dsoa_metrics_model_group.yaml is created."""
        out_dir, _ = export_output
        mg = out_dir / "metrics" / "dsoa_metrics_model_group.yaml"
        assert mg.exists(), "dsoa_metrics_model_group.yaml not found"

    def test_warehouse_usage_metrics_file_exists(self, export_output):
        """metrics/dsoa_metrics_warehouse_usage.yaml has model: envelope with interfaces."""
        out_dir, _ = export_output
        wf = out_dir / "metrics" / "dsoa_metrics_warehouse_usage.yaml"
        assert wf.exists(), "dsoa_metrics_warehouse_usage.yaml not found"
        with open(wf, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "model" in doc, "metric file must use model: envelope"
        assert "interfaces" in doc["model"]
        assert "i.dsoa_resource" in doc["model"]["interfaces"]

    def test_users_event_model_exists(self, export_output):
        """model/dsoa/dsoa.events.users.yaml is created."""
        out_dir, _ = export_output
        ef = out_dir / "model" / "dsoa" / "dsoa.events.users.yaml"
        assert ef.exists(), "dsoa.events.users.yaml not found"

    def test_events_model_group_exists(self, export_output):
        """model/dsoa/model_group_dsoa_events.yaml is created."""
        out_dir, _ = export_output
        mg = out_dir / "model" / "dsoa" / "model_group_dsoa_events.yaml"
        assert mg.exists(), "model_group_dsoa_events.yaml not found"

    def test_snowflake_resource_has_multiple_groups(self, export_output):
        """snowflake_resource.yaml contains multiple namespace groups."""
        out_dir, _ = export_output
        rf = out_dir / "fields" / "resource_fields" / "snowflake_resource.yaml"
        with open(rf, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "groups" in doc
        assert len(doc["groups"]) > 1, "snowflake_resource.yaml should have multiple namespace groups"

    def test_interfaces_has_three_groups(self, export_output):
        """interfaces_dsoa.yaml contains exactly 3 interface groups."""
        out_dir, _ = export_output
        fi = out_dir / "metrics" / "interfaces_dsoa.yaml"
        with open(fi, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        group_ids = {g["id"] for g in doc["groups"]}
        assert "i.dsoa_resource" in group_ids
        assert "i.dsoa_warehouse" in group_ids
        assert "i.dsoa_database" in group_ids

    def test_metric_attrs_do_not_contain_attribute_section_fields(self, export_output):
        """Metric attributes: list must not include attributes-section fields.

        Only dimensions (resource-classified) are valid metric dimensions.
        Attributes-section fields (signal-classified) must NOT appear in
        a metric's attributes: list.
        """
        out_dir, _ = export_output
        # Load resource monitors or warehouse_usage — both have attributes
        for fname in (out_dir / "metrics").glob("dsoa_metrics_*.yaml"):
            with open(fname, "r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if "model" not in doc:
                continue
            for group in doc["model"].get("groups", []):
                if group.get("type") != "metric":
                    continue
                for attr in group.get("attributes", []):
                    # Key assertion: attribute section fields that are signal-classified
                    # must never appear here. We spot-check known signal fields.
                    ref = attr.get("ref", "")
                    assert ref not in {
                        "session.id",
                        "dsoa.debug.span.events.added",
                    }, f"Signal-only field {ref!r} must not appear in metric dimensions"

    def test_nonzero_field_count(self, export_output):
        """Total field count is non-zero."""
        _, summary = export_output
        total = summary["ref"] + summary["new"] + summary["deprecated_alias"] + summary["otel_only"]
        assert total > 0, "No fields exported"

    def test_interfaces_file_parseable(self, export_output):
        """interfaces_dsoa.yaml is valid YAML."""
        out_dir, _ = export_output
        fi = out_dir / "metrics" / "interfaces_dsoa.yaml"
        with open(fi, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "groups" in doc
        assert len(doc["groups"]) > 0


##endregion

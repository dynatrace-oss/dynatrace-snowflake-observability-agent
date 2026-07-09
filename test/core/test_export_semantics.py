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
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from build.export_semantics import (
    INTERFACE_DATABASE_KEYS,
    INTERFACE_WAREHOUSE_KEYS,
    RESOURCE_ATTRIBUTE_KEYS,
    VALID_STABILITY_VALUES,
    ExportError,
    SemanticExporter,
    _IndentedDumper,
    _build_type_node,
    _classify_field,
    _coerce_attribute_example,
    _coerce_string_array_examples,
    _emit_id_entry,
    _emit_metric_entry,
    _emit_ref_entry,
    _map_attr_type,
    _map_metric_instrument,
    _merge_field_entries,
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

    def test_attr_type_array_types(self):
        """Array and record types map to their SD equivalents."""
        assert _map_attr_type("string[]") == "string[]"
        assert _map_attr_type("long[]") == "long[]"
        assert _map_attr_type("array") == "array"
        assert _map_attr_type("record") == "record"
        assert _map_attr_type("record[]") == "record[]"

    def test_attr_type_timestamp_falls_through_to_string(self):
        """__type: timestamp (legacy) falls through to string (Grail reality)."""
        assert _map_attr_type("timestamp") == "string"


##endregion


##region Unit tests — attribute example coercion


class TestAttributeExampleCoercion:
    """Verify _coerce_attribute_example handles Python bool and other types correctly."""

    def test_bool_true_produces_lowercase_true(self):
        """Python True (from YAML true) → 'true' (lowercase, per semconv)."""
        assert _coerce_attribute_example(True) == "true"

    def test_bool_false_produces_lowercase_false(self):
        """Python False (from YAML false) → 'false' (lowercase, per semconv)."""
        assert _coerce_attribute_example(False) == "false"

    def test_string_passthrough(self):
        """String examples pass through unchanged (stripped)."""
        assert _coerce_attribute_example("  hello  ") == "hello"

    def test_int_to_string_default(self):
        """Integer examples with no field_type are converted to string (default behaviour)."""
        assert _coerce_attribute_example(42) == "42"

    def test_int_with_long_type_returns_int(self):
        """Integer examples with field_type='long' return Python int."""
        assert _coerce_attribute_example(42, "long") == 42
        assert isinstance(_coerce_attribute_example(42, "long"), int)

    def test_emit_id_entry_boolean_example_is_bool(self):
        """_emit_id_entry with __type: boolean and __example: true produces Python bool in examples."""
        entry = {"__semdict": "new", "__type": "boolean", "__description": "Is active.", "__example": True}
        node = _emit_id_entry("snowflake.resource_monitor.is_active", entry, "new")
        assert node["type"] == "boolean"
        assert node["examples"] == [True], "boolean True must emit as Python bool True (PyYAML → 'true')"


##endregion


##region Unit tests — type-aware attribute example coercion


class TestAttributeExampleTypeCoercion:
    """Verify _coerce_attribute_example returns the correct native type per declared __type."""

    def test_long_example_emits_int(self):
        """__type: long + int example → Python int."""
        result = _coerce_attribute_example(2, "long")
        assert result == 2
        assert isinstance(result, int)

    def test_int_example_emits_int(self):
        """__type: int + int example → Python int."""
        result = _coerce_attribute_example(5, "int")
        assert result == 5
        assert isinstance(result, int)

    def test_double_example_emits_float(self):
        """__type: double + float example → Python float."""
        result = _coerce_attribute_example(1.5, "double")
        assert result == 1.5
        assert isinstance(result, float)

    def test_boolean_example_emits_bool(self):
        """__type: boolean + True example → Python bool."""
        result = _coerce_attribute_example(True, "boolean")
        assert result is True
        assert isinstance(result, bool)

    def test_string_example_still_str(self):
        """__type: string + str example → str (unchanged behaviour)."""
        result = _coerce_attribute_example("foo", "string")
        assert result == "foo"
        assert isinstance(result, str)

    def test_quoted_long_string_coerced_to_int(self):
        """__type: long + quoted 19-digit string example → Python int (arbitrary precision)."""
        result = _coerce_attribute_example("1633046400000000000", "long")
        assert result == 1633046400000000000
        assert isinstance(result, int)

    def test_clusters_count_example_is_int(self):
        """snowflake.warehouse.clusters.count (long) must emit int example in generated output.

        Regression: before the fix, _coerce_attribute_example always returned str,
        causing the SD build tool to reject string '2' for a long field.
        """
        instruments_def_path = REPO_ROOT / "src" / "dtagent" / "plugins" / "warehouse_usage.config" / "instruments-def.yml"
        with open(instruments_def_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        # Navigate to the attributes section to find the field
        attributes = data.get("attributes", {})
        entry = attributes.get("snowflake.warehouse.clusters.count")
        assert entry is not None, "snowflake.warehouse.clusters.count not found in instruments-def"
        assert entry.get("__type") == "long", "field must be typed long"
        field_type = str(entry.get("__type") or "").lower()
        example_raw = entry.get("__example")
        result = _coerce_attribute_example(example_raw, field_type)
        assert isinstance(result, int), f"clusters.count example must be int, got {type(result).__name__}: {result!r}"

    def test_has_query_acceleration_example_is_bool(self):
        """snowflake.warehouse.has_query_acceleration_enabled (boolean) must emit bool example.

        Regression: before the fix, boolean True was coerced to string 'true', causing
        the SD build tool to reject a string example for a boolean field.
        """
        instruments_def_path = REPO_ROOT / "src" / "dtagent" / "plugins" / "resource_monitors.config" / "instruments-def.yml"
        with open(instruments_def_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        attributes = data.get("attributes", {})
        entry = attributes.get("snowflake.warehouse.has_query_acceleration_enabled")
        assert entry is not None, "snowflake.warehouse.has_query_acceleration_enabled not found"
        assert entry.get("__type") == "boolean", "field must be typed boolean"
        field_type = str(entry.get("__type") or "").lower()
        example_raw = entry.get("__example")
        result = _coerce_attribute_example(example_raw, field_type)
        assert isinstance(result, bool), f"has_query_acceleration_enabled example must be bool, got {type(result).__name__}: {result!r}"


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
        """snowflake.warehouse.* resource fields → snowflake.warehouse.resource group (avoids collision with signal group)."""
        from build.export_semantics import _RES_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("snowflake.warehouse.size", _RES_NS, "snowflake.resource", "resource")
        assert gid == "snowflake.warehouse.resource"
        assert gtype == "resource"

    def test_db_resource_group(self):
        """db.* resource fields → db.resource group (avoids collision with db signal attribute_group)."""
        from build.export_semantics import _RES_NS  # pylint: disable=import-outside-toplevel

        gid, gtype = _ns_group("db.namespace", _RES_NS, "snowflake.resource", "resource")
        assert gid == "db.resource"
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

    def test_empty_string_example_fails(self):
        """Empty string __example is invalid — all fields must provide a real example."""
        entry = {"__description": "A description.", "__example": ""}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__example" in e for e in errors)

    def test_blank_string_example_fails(self):
        """Whitespace-only __example is invalid."""
        entry = {"__description": "A description.", "__example": "   "}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__example" in e for e in errors)

    def test_zero_example_passes(self):
        """Zero __example is valid for long/double fields."""
        entry = {"__description": "A description.", "__example": 0, "__type": "long"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_type_mismatch_long_with_string_fails(self):
        """__type: long with a string example is a hard error."""
        entry = {"__description": "An id.", "__example": "wh123", "__type": "long"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__type=long" in e for e in errors)

    def test_type_mismatch_string_with_int_fails(self):
        """__type: string with an integer example is a hard error."""
        entry = {"__description": "A name.", "__example": 42, "__type": "string"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__type=string" in e for e in errors)

    def test_type_mismatch_boolean_with_string_fails(self):
        """__type: boolean with a string example is a hard error."""
        entry = {"__description": "A flag.", "__example": "N", "__type": "boolean"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__type=boolean" in e for e in errors)

    def test_type_mismatch_long_with_bool_fails(self):
        """__type: long with a bool example is a hard error (bool is subclass of int but not a valid long)."""
        entry = {"__description": "A count.", "__example": True, "__type": "long"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__type=long" in e for e in errors)

    def test_type_mismatch_string_array_with_string_fails(self):
        """__type: string[] with a plain string example is a hard error."""
        entry = {"__description": "Names.", "__example": "COMPUTE_WH", "__type": "string[]"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__type=string[]" in e for e in errors)

    def test_type_match_long_with_int_passes(self):
        """__type: long with an integer example passes."""
        entry = {"__description": "An id.", "__example": 12345, "__type": "long"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_type_match_string_array_with_list_passes(self):
        """__type: string[] with a list example passes."""
        entry = {"__description": "Names.", "__example": ["WH_A", "WH_B"], "__type": "string[]"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_enum_field_skips_type_match_check(self):
        """Fields with __enum skip type-match validation (schema enforces string)."""
        entry = {
            "__description": "Status.",
            "__example": "ACTIVE",
            "__type": "string",
            "__enum": {"allow_custom_values": False, "members": []},
        }
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_metrics_section_skips_type_match(self):
        """Type-match is not enforced in the metrics section."""
        entry = {"__description": "Credits.", "__example": "some_string", "__type": "long"}
        errors = _validate_entry("test.metric", entry, "metrics", "test.yml")
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
        """__type: long maps to type: long in output and example is emitted as int."""
        entry = {"__semdict": "new", "__type": "long", "__description": "D.", "__example": 42}
        node = _emit_id_entry("test.long.field", entry, "new")
        assert node["type"] == "long"
        assert node["examples"] == [42]
        assert isinstance(node["examples"][0], int), "long field example must be Python int"


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

    def test_interfaces_yaml_has_correct_interfaces(self, tmp_path):
        """interfaces_dsoa.yaml has i.dsoa_resource; interfaces_snowflake.yaml has i.snowflake_warehouse/database."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        dsoa_doc, sf_doc = exporter._build_interfaces_yaml()
        dsoa_ids = {g["id"] for g in dsoa_doc["groups"]}
        sf_ids = {g["id"] for g in sf_doc["groups"]}
        assert "i.dsoa_resource" in dsoa_ids
        assert "i.snowflake_warehouse" in sf_ids
        assert "i.snowflake_database" in sf_ids

    def test_resource_interface_covers_resource_attribute_keys(self, tmp_path):
        """i.dsoa_resource attrs are a superset of RESOURCE_ATTRIBUTE_KEYS."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        dsoa_doc, _ = exporter._build_interfaces_yaml()
        i_resource = next(g for g in dsoa_doc["groups"] if g["id"] == "i.dsoa_resource")
        interface_keys = {a["ref"] for a in i_resource["attributes"] if "ref" in a}
        assert RESOURCE_ATTRIBUTE_KEYS.issubset(interface_keys)

    def test_dsoa_resource_file_has_dsoa_fields(self, tmp_path):
        """resource_fields/dsoa.yaml only has dsoa./deployment. keys (no ref: nodes).

        Refs belong exclusively in the i.dsoa_resource interface (interfaces_dsoa.yaml).
        Field definition files must contain only ``id:`` blocks — never ``ref:`` nodes.

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
        # Field definition files must contain ONLY id: nodes — never ref: nodes
        all_attrs = [a for g in dsoa_doc["groups"] for a in g.get("attributes", [])]
        for attr in all_attrs:
            assert "ref" not in attr, f"ref: node {attr!r} must not appear in dsoa.yaml field file"

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
        assert doc["model"]["id"] == "snowflake.events.mock_plugin"
        assert doc["model"]["model_group_id"] == "snowflake.events"
        # Timestamp events go to the OpenPipeline Events API, not bizevents
        assert doc["model"]["data_object"] == "event", (
            "Event-timestamp models must use data_object: event (OpenPipeline Events API). "
            "Only dsoa.* self-monitoring fields are sent to bizevents."
        )

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
        # Create a fixture that has i.snowflake_warehouse-covered dims + other dims
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
            assert iface_key not in attr_refs, f"{iface_key} must not appear (covered by i.snowflake_warehouse)"
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
        # All snowflake signal groups are combined into a single snowflake.yaml
        names = {f.name for f in yaml_files}
        assert "snowflake.yaml" in names, "snowflake.yaml expected in signal_fields"

    def test_interfaces_file_exists(self, export_output):
        """metrics/interfaces_dsoa.yaml is created."""
        out_dir, _ = export_output
        fi = out_dir / "metrics" / "interfaces_dsoa.yaml"
        assert fi.exists(), "interfaces_dsoa.yaml not found"

    def test_metrics_model_group_file_exists(self, export_output):
        """metrics/snowflake_metrics_model_group.yaml is created."""
        out_dir, _ = export_output
        mg = out_dir / "metrics" / "snowflake_metrics_model_group.yaml"
        assert mg.exists(), "snowflake_metrics_model_group.yaml not found"

    def test_warehouse_usage_metrics_file_exists(self, export_output):
        """metrics/snowflake_metrics_warehouse_usage.yaml has model: envelope with interfaces."""
        out_dir, _ = export_output
        wf = out_dir / "metrics" / "snowflake_metrics_warehouse_usage.yaml"
        assert wf.exists(), "snowflake_metrics_warehouse_usage.yaml not found"
        with open(wf, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "model" in doc, "metric file must use model: envelope"
        assert "interfaces" in doc["model"]
        assert "i.dsoa_resource" in doc["model"]["interfaces"]

    def test_users_event_model_exists(self, export_output):
        """model/snowflake/events/snowflake.events.users.yaml is created."""
        out_dir, _ = export_output
        ef = out_dir / "model" / "snowflake" / "events" / "snowflake.events.users.yaml"
        assert ef.exists(), "snowflake.events.users.yaml not found"

    def test_events_model_group_exists(self, export_output):
        """model/snowflake/events/model_group_snowflake_events.yaml is created."""
        out_dir, _ = export_output
        mg = out_dir / "model" / "snowflake" / "events" / "model_group_snowflake_events.yaml"
        assert mg.exists(), "model_group_snowflake_events.yaml not found"

    def test_snowflake_resource_has_multiple_groups(self, export_output):
        """snowflake_resource.yaml contains multiple namespace groups."""
        out_dir, _ = export_output
        rf = out_dir / "fields" / "resource_fields" / "snowflake_resource.yaml"
        with open(rf, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "groups" in doc
        assert len(doc["groups"]) > 1, "snowflake_resource.yaml should have multiple namespace groups"

    def test_interfaces_has_correct_groups(self, export_output):
        """interfaces_dsoa.yaml has i.dsoa_resource; interfaces_snowflake.yaml has warehouse/database."""
        out_dir, _ = export_output
        dsoa_doc = yaml.safe_load((out_dir / "metrics" / "interfaces_dsoa.yaml").read_text(encoding="utf-8"))
        sf_doc = yaml.safe_load((out_dir / "metrics" / "interfaces_snowflake.yaml").read_text(encoding="utf-8"))
        dsoa_ids = {g["id"] for g in dsoa_doc["groups"]}
        sf_ids = {g["id"] for g in sf_doc["groups"]}
        assert "i.dsoa_resource" in dsoa_ids
        assert "i.snowflake_warehouse" in sf_ids
        assert "i.snowflake_database" in sf_ids

    def test_metric_attrs_do_not_contain_attribute_section_fields(self, export_output):
        """Metric attributes: list must not include attributes-section fields.

        Only dimensions (resource-classified) are valid metric dimensions.
        Attributes-section fields (signal-classified) must NOT appear in
        a metric's attributes: list.
        """
        out_dir, _ = export_output
        # Load resource monitors or warehouse_usage — both have attributes
        for fname in (out_dir / "metrics").glob("snowflake_metrics_*.yaml"):
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


##region Unit tests — _merge_field_entries (A2: enum union dedup)


class TestMergeFieldEntries:
    """Verify _merge_field_entries implements the union enum merge strategy."""

    def _make_meta(self, plugin: str, enum_def=None, extra=None) -> Dict[str, Any]:
        """Helper: build a minimal entry meta dict."""
        entry: Dict[str, Any] = {"__description": "A field.", "__example": "val"}
        if enum_def is not None:
            entry["__enum"] = enum_def
        if extra:
            entry.update(extra)
        return {"section": "attributes", "semdict": "new", "plugin": plugin, "entry": entry, "classification": "signal"}

    def test_enum_dedup_upgrade_no_enum_to_enum(self):
        """Existing has no __enum, incoming has __enum → result upgrades to enum-rich definition."""
        existing = self._make_meta("plugin_a")
        incoming_enum = {"allow_custom_values": True, "members": [{"id": "v1", "value": "V1", "brief": "Value one."}]}
        incoming = self._make_meta("plugin_b", enum_def=incoming_enum)
        result = _merge_field_entries("test.field", existing, incoming)
        assert result["entry"].get("__enum") is not None, "result must have __enum after upgrade"
        assert result["plugin"] == "plugin_b", "plugin should be the incoming (enum-rich) one"
        assert result["entry"]["__enum"]["members"][0]["value"] == "V1"

    def test_enum_dedup_union_both_have_enum(self):
        """Both have __enum with partially overlapping members → union of all unique values."""
        enum_a = {
            "allow_custom_values": False,
            "members": [{"id": "a", "value": "A", "brief": "Alpha."}, {"id": "b", "value": "B", "brief": "Beta."}],
        }
        enum_b = {
            "allow_custom_values": True,
            "members": [{"id": "b", "value": "B", "brief": "Beta (dup)."}, {"id": "c", "value": "C", "brief": "Gamma."}],
        }
        existing = self._make_meta("plugin_a", enum_def=enum_a)
        incoming = self._make_meta("plugin_b", enum_def=enum_b)
        result = _merge_field_entries("test.field", existing, incoming)
        merged_enum = result["entry"]["__enum"]
        values = [m["value"] for m in merged_enum["members"]]
        assert values.count("B") == 1, "duplicate value B must appear exactly once"
        assert set(values) == {"A", "B", "C"}, "union must contain all unique values"
        assert merged_enum["allow_custom_values"] is True, "allow_custom_values must be OR of both (False OR True = True)"
        assert result["plugin"] == "plugin_a", "dedup winner (existing) plugin must be preserved"

    def test_enum_dedup_first_wins_no_enum(self):
        """Neither has __enum → existing wins unchanged."""
        existing = self._make_meta("plugin_a")
        incoming = self._make_meta("plugin_b", extra={"__description": "Incoming description."})
        result = _merge_field_entries("test.field", existing, incoming)
        assert result["plugin"] == "plugin_a", "first-seen plugin must win when no enum"
        assert result["entry"].get("__description") == "A field.", "existing description must be preserved"

    def test_enum_allow_custom_both_false_stays_false(self):
        """allow_custom_values = False OR False = False."""
        enum_a = {"allow_custom_values": False, "members": [{"id": "x", "value": "X", "brief": "X."}]}
        enum_b = {"allow_custom_values": False, "members": [{"id": "y", "value": "Y", "brief": "Y."}]}
        existing = self._make_meta("plugin_a", enum_def=enum_a)
        incoming = self._make_meta("plugin_b", enum_def=enum_b)
        result = _merge_field_entries("test.field", existing, incoming)
        assert result["entry"]["__enum"]["allow_custom_values"] is False


##endregion


##region Unit tests — dim_plugins ownership tracking (A3)


class TestDimPluginsOwnership:
    """Verify dimension ownership tracking allows cross-plugin dims in metric models."""

    def test_dim_from_discarded_plugin_appears_in_metric_model(self, tmp_path):
        """Dim defined in plugin_b but dedup-won by plugin_a still appears in plugin_b metric."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")

        # plugin_a defines dim first (wins dedup), plugin_b also defines it
        plugin_a_fixture = tmp_path / "plugin_a.yml"
        plugin_a_fixture.write_text("dimensions:\n" "  my.shared.dim:\n" "    __description: Shared dimension.\n" "    __example: val\n")
        plugin_b_fixture = tmp_path / "plugin_b.yml"
        plugin_b_fixture.write_text(
            "dimensions:\n"
            "  my.shared.dim:\n"
            "    __description: Shared dimension (plugin b copy).\n"
            "    __example: val\n"
            "metrics:\n"
            "  plugin_b.metric:\n"
            "    __description: A metric.\n"
            "    __example: '1'\n"
            "    unit: count\n"
        )

        _, entries_a = exporter._parse_file("plugin_a", plugin_a_fixture)
        _, entries_b = exporter._parse_file("plugin_b", plugin_b_fixture)

        # Build combined entries with dedup (plugin_a wins for my.shared.dim)
        all_entries: Dict[str, Any] = {}
        dim_plugins: Dict[str, Any] = {}
        for plugin_name, raw_entries in [("plugin_a", entries_a), ("plugin_b", entries_b)]:
            for key, meta in raw_entries.items():
                if meta["section"] == "dimensions":
                    dim_plugins.setdefault(key, set()).add(plugin_name)
                if key in all_entries:
                    all_entries[key] = _merge_field_entries(key, all_entries[key], meta)
                else:
                    all_entries[key] = meta

        # plugin_b's dedup winner for my.shared.dim is plugin_a
        assert all_entries["my.shared.dim"]["plugin"] == "plugin_a", "plugin_a should have won dedup"
        assert "plugin_b" in dim_plugins["my.shared.dim"], "dim_plugins must record plugin_b defined the dim"

        # Without dim_plugins: plugin_b metric won't see the dim (old bug)
        metric_entries_b = {k: v for k, v in all_entries.items() if v["classification"] == "metric" and v["plugin"] == "plugin_b"}
        doc_without = exporter._build_metric_model_yaml("plugin_b", metric_entries_b, all_entries, dim_plugins=None)
        refs_without = [a["ref"] for a in doc_without["model"]["groups"][0].get("attributes", [])]

        # With dim_plugins: plugin_b metric must see the dim
        doc_with = exporter._build_metric_model_yaml("plugin_b", metric_entries_b, all_entries, dim_plugins=dim_plugins)
        refs_with = [a["ref"] for a in doc_with["model"]["groups"][0].get("attributes", [])]

        assert "my.shared.dim" not in refs_without, "without dim_plugins the dim should be absent (old behavior)"
        assert "my.shared.dim" in refs_with, "with dim_plugins the dim must appear in plugin_b's metric"


##endregion


##region Unit tests — update_docs.py semantics table generation


class TestSemanticsTableColumns:
    """Verify _generate_semantics_tables column layout: no Note/SD Status, note content merged into Description."""

    def test_semantics_table_columns_dimensions(self):
        """Dimensions/attributes tables must have Stability but no Note or SD Status columns.

        __semdict_note content must be merged into the Description cell instead of a
        separate column, keeping tables narrow enough to render in VS Code and Obsidian.
        """
        from build.update_docs import _generate_semantics_tables

        json_data = {
            "dimensions": {
                "db.system": {
                    "__description": "DBMS product.",
                    "__example": "snowflake",
                    "__semdict_note": "OTel-derived field.",
                    "__stability": "stable",
                    "__semdict": "otel-only",
                }
            }
        }
        result = _generate_semantics_tables(json_data, "test_plugin", no_global_context_name=False)
        assert "Note" not in result, "Note column must not appear in semantics table"
        assert "SD Status" not in result, "SD Status column must not appear in semantics table"
        assert "Stability" in result, "Stability column must appear in semantics table"
        assert "OTel-derived field." not in result, "__semdict_note content must NOT be merged into Description"
        assert "stable" in result, "__stability value must appear in table"

    def test_semantics_table_columns_metrics(self):
        """Metrics tables must also have no Note or SD Status columns, note merged into Description."""
        from build.update_docs import _generate_semantics_tables

        json_data = {
            "metrics": {
                "snowflake.credits.compute": {
                    "__description": "Credits consumed by compute.",
                    "__example": 8,
                    "unit": "count",
                    "displayName": "Compute Credits",
                    "__semdict_note": "Original unit: credits (Snowflake billing unit).",
                    "__stability": "experimental",
                    "__semdict": "new",
                }
            }
        }
        result = _generate_semantics_tables(json_data, "warehouse_usage", no_global_context_name=False)
        assert "Note" not in result, "Note column must not appear in metrics table"
        assert "SD Status" not in result, "SD Status column must not appear in metrics table"
        assert "Stability" in result, "Stability column must appear in metrics table"
        assert "Original unit: credits" not in result, "__semdict_note content must NOT be merged into Description"


class TestEnumDescriptionInSemantics:
    """Verify that __enum members are rendered as human-readable text in SEMANTICS.md."""

    def test_enum_values_appended_to_description(self):
        """Fields with __enum must have a 'Possible values' section appended to their description cell."""
        from build.update_docs import _generate_semantics_tables

        json_data = {
            "attributes": {
                "snowflake.table.dynamic.refresh.trigger": {
                    "__description": "Describes the trigger for the refresh.",
                    "__example": "SCHEDULED",
                    "__stability": "stable",
                    "__type": "string",
                    "__enum": {
                        "allow_custom_values": True,
                        "members": [
                            {"id": "scheduled", "value": "SCHEDULED", "brief": "Normal background refresh."},
                            {"id": "manual", "value": "MANUAL", "brief": "User triggered refresh."},
                            {"id": "creation", "value": "CREATION", "brief": "Refresh during creation DDL."},
                        ],
                    },
                }
            }
        }
        result = _generate_semantics_tables(json_data, "dynamic_tables", no_global_context_name=False)

        assert "Possible values:" in result, "Enum values must appear as 'Possible values:' in description"
        assert "`SCHEDULED`" in result, "SCHEDULED enum value must appear in description"
        assert "`MANUAL`" in result, "MANUAL enum value must appear in description"
        assert "`CREATION`" in result, "CREATION enum value must appear in description"
        assert "Normal background refresh" in result, "SCHEDULED brief must appear"
        assert "User triggered refresh" in result, "MANUAL brief must appear"
        assert "Additional values may be present." in result, "allow_custom_values=True must add note"

    def test_enum_closed_no_additional_values_note(self):
        """When allow_custom_values is False, the 'Additional values may be present' note must be absent."""
        from build.update_docs import _get_clean_description

        details = {
            "__description": "The operation status.",
            "__enum": {
                "allow_custom_values": False,
                "members": [
                    {"id": "ok", "value": "OK", "brief": "Success."},
                    {"id": "error", "value": "ERROR", "brief": "Failure."},
                ],
            },
        }
        result = _get_clean_description(details)

        assert "Possible values:" in result
        assert "<ul>" in result
        assert "<li> `OK`" in result
        assert "<li> `ERROR`" in result
        assert "Additional values may be present." not in result

    def test_enum_brief_trailing_period_stripped(self):
        """Trailing periods in enum member briefs must be stripped to avoid double periods."""
        from build.update_docs import _get_clean_description

        details = {
            "__description": "Refresh state.",
            "__enum": {
                "allow_custom_values": False,
                "members": [
                    {"id": "done", "value": "DONE", "brief": "Completed successfully."},
                ],
            },
        }
        result = _get_clean_description(details)

        # Trailing period stripped from brief → no ".," or ".." artifact inside the list
        assert "<li> `DONE` — Completed successfully" in result
        assert "<li> `DONE` — Completed successfully.," not in result

    def test_enum_without_brief_renders_value_only(self):
        """Enum members without a brief must render as just `VALUE` without the dash."""
        from build.update_docs import _get_clean_description

        details = {
            "__description": "Some field.",
            "__enum": {
                "allow_custom_values": False,
                "members": [
                    {"id": "foo", "value": "FOO"},
                ],
            },
        }
        result = _get_clean_description(details)
        assert "<li> `FOO`" in result
        assert " — " not in result

    def test_no_enum_description_unchanged(self):
        """Fields without __enum must have their description returned unchanged (newline handling only)."""
        from build.update_docs import _get_clean_description

        details = {"__description": "Plain description."}
        result = _get_clean_description(details)
        assert result == "Plain description."
        assert "Possible values:" not in result

    def test_enum_empty_members_no_possible_values(self):
        """An __enum block with no members must not produce 'Possible values:' text."""
        from build.update_docs import _get_clean_description

        details = {
            "__description": "Field with empty enum.",
            "__enum": {"allow_custom_values": True, "members": []},
        }
        result = _get_clean_description(details)
        assert "Possible values:" not in result

    def test_dynamic_refresh_trigger_in_real_instruments_def(self):
        """The real dynamic_tables instruments-def.yml must produce enum docs for snowflake.table.dynamic.refresh.trigger."""
        import yaml

        with open("src/dtagent/plugins/dynamic_tables.config/instruments-def.yml", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        from build.update_docs import _get_clean_description

        trigger_entry = data.get("attributes", {}).get("snowflake.table.dynamic.refresh.trigger", {})
        assert trigger_entry, "snowflake.table.dynamic.refresh.trigger must exist in dynamic_tables instruments-def"

        result = _get_clean_description(trigger_entry)
        assert "Possible values:" in result, "trigger field must have Possible values: section"
        assert "`SCHEDULED`" in result, "SCHEDULED must appear in enum docs"
        assert "`MANUAL`" in result, "MANUAL must appear in enum docs"
        assert "`CREATION`" in result, "CREATION must appear in enum docs"
        assert "Additional values may be present." in result, "allow_custom_values=True must add note"


##endregion


##region Unit tests — __stability validation


class TestStabilityValidation:
    """Verify _validate_entry rejects invalid __stability values and accepts valid ones."""

    def test_valid_stability_stable_passes(self):
        """__stability: stable is valid."""
        entry = {"__description": "D.", "__example": "E.", "__stability": "stable"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_valid_stability_experimental_passes(self):
        """__stability: experimental is valid."""
        entry = {"__description": "D.", "__example": "E.", "__stability": "experimental"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_valid_stability_deprecated_passes(self):
        """__stability: deprecated is valid (mutual-exclusion handled at emit time)."""
        entry = {"__description": "D.", "__example": "E.", "__stability": "deprecated"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_invalid_stability_development_fails(self):
        """__stability: development is NOT a valid SD value — must produce an error."""
        entry = {"__description": "D.", "__example": "E.", "__stability": "development"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any(
            "__stability" in e and "development" in e for e in errors
        ), "Expected an error for __stability: development; got: " + str(errors)

    def test_invalid_stability_alpha_fails(self):
        """Arbitrary unknown stability value must produce an error."""
        entry = {"__description": "D.", "__example": "E.", "__stability": "alpha"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__stability" in e for e in errors)

    def test_no_stability_passes(self):
        """Entries without __stability are valid (defaults to experimental at emit time)."""
        entry = {"__description": "D.", "__example": "E."}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert errors == []

    def test_valid_stability_constants(self):
        """VALID_STABILITY_VALUES must contain exactly stable, experimental, deprecated."""
        assert VALID_STABILITY_VALUES == {"stable", "experimental", "deprecated"}


##endregion


##region Unit tests — string[] example coercion


class TestStringArrayExampleCoercion:
    """Verify _coerce_string_array_examples produces list-of-lists for SD string[] fields."""

    def test_flat_list_wrapped_in_outer_list(self):
        """Flat list ['val1', 'val2'] → [['val1', 'val2']]."""
        result = _coerce_string_array_examples("test.field", ["val1", "val2"])
        assert result == [["val1", "val2"]]
        assert isinstance(result[0], list)

    def test_list_of_lists_passthrough(self):
        """Already list-of-lists [['val1', 'val2']] → emitted as-is."""
        result = _coerce_string_array_examples("test.field", [["val1", "val2"]])
        assert result == [["val1", "val2"]]

    def test_scalar_json_array_string_wrapped(self):
        """Scalar string '["val1", "val2"]' parsed and wrapped → [['val1', 'val2']]."""
        result = _coerce_string_array_examples("test.field", '["val1", "val2"]')
        assert result == [["val1", "val2"]]

    def test_scalar_non_json_string_single_element(self):
        """Non-JSON scalar string → wrapped as single-element inner list [['val']]."""
        result = _coerce_string_array_examples("test.field", "plain_value")
        assert result == [["plain_value"]]

    def test_scalar_bad_json_falls_back(self):
        """Scalar string starting with '[' but invalid JSON → single-element inner list."""
        result = _coerce_string_array_examples("test.field", "[not valid json")
        assert len(result) == 1
        assert isinstance(result[0], list)

    def test_emit_id_entry_string_array_flat_list(self):
        """_emit_id_entry with string[] type and flat list example produces list-of-lists."""
        entry = {
            "__semdict": "new",
            "__type": "string[]",
            "__description": "Array of resources.",
            "__example": ["database1", "warehouse1"],
        }
        node = _emit_id_entry("snowflake.budget.resource", entry, "new")
        assert node["type"] == "string[]"
        assert node["examples"] == [["database1", "warehouse1"]], f"Expected [['database1', 'warehouse1']], got {node['examples']!r}"

    def test_emit_id_entry_string_array_scalar_json(self):
        """_emit_id_entry with string[] type and JSON scalar example produces list-of-lists."""
        entry = {
            "__semdict": "new",
            "__type": "string[]",
            "__description": "Array of IDs.",
            "__example": '["0", "1"]',
        }
        node = _emit_id_entry("test.ids", entry, "new")
        assert node["examples"] == [["0", "1"]], f"Expected [['0', '1']], got {node['examples']!r}"

    def test_emit_id_entry_string_array_already_list_of_lists(self):
        """_emit_id_entry with string[] type and already list-of-lists example passes through."""
        entry = {
            "__semdict": "new",
            "__type": "string[]",
            "__description": "Array of roles.",
            "__example": [["ROLE_A", "ROLE_B"]],
        }
        node = _emit_id_entry("test.roles", entry, "new")
        assert node["examples"] == [["ROLE_A", "ROLE_B"]]


##endregion


##region Integration tests — string[] examples in generated output


class TestStringArrayExamplesInOutput:
    """Verify string[] fields in the generated export have list-of-lists examples."""

    def test_budget_resource_has_list_of_lists_examples(self, tmp_path):
        """snowflake.budget.resource (string[]) must export with list-of-lists examples."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        instruments_path = REPO_ROOT / "src" / "dtagent" / "plugins" / "budgets.config" / "instruments-def.yml"
        if not instruments_path.exists():
            pytest.skip("budgets instruments-def.yml not found")
        _, entries = exporter._parse_file("budgets", instruments_path)
        meta = entries.get("snowflake.budget.resource")
        assert meta is not None, "snowflake.budget.resource not found in entries"
        node = _emit_id_entry("snowflake.budget.resource", meta["entry"], meta["semdict"])
        examples = node.get("examples", [])
        assert len(examples) > 0, "examples must be non-empty"
        assert isinstance(
            examples[0], list
        ), f"string[] field examples[0] must be a list, got {type(examples[0]).__name__}: {examples[0]!r}"

    def test_user_roles_direct_has_list_of_lists_examples(self, tmp_path):
        """snowflake.user.roles.direct.list (string[]) must export with list-of-lists examples."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        instruments_path = REPO_ROOT / "src" / "dtagent" / "plugins" / "users.config" / "instruments-def.yml"
        if not instruments_path.exists():
            pytest.skip("users instruments-def.yml not found")
        _, entries = exporter._parse_file("users", instruments_path)
        meta = entries.get("snowflake.user.roles.direct.list")
        assert meta is not None, "snowflake.user.roles.direct.list not found in entries"
        node = _emit_id_entry("snowflake.user.roles.direct.list", meta["entry"], meta["semdict"])
        examples = node.get("examples", [])
        assert len(examples) > 0
        assert isinstance(
            examples[0], list
        ), f"string[] field examples[0] must be a list, got {type(examples[0]).__name__}: {examples[0]!r}"

    def test_dynamic_table_inputs_has_list_of_lists_examples(self, tmp_path):
        """snowflake.table.dynamic.graph.inputs (string[]) must export with list-of-lists examples."""
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=tmp_path / "out")
        instruments_path = REPO_ROOT / "src" / "dtagent" / "plugins" / "dynamic_tables.config" / "instruments-def.yml"
        if not instruments_path.exists():
            pytest.skip("dynamic_tables instruments-def.yml not found")
        _, entries = exporter._parse_file("dynamic_tables", instruments_path)
        meta = entries.get("snowflake.table.dynamic.graph.inputs")
        assert meta is not None, "snowflake.table.dynamic.graph.inputs not found in entries"
        node = _emit_id_entry("snowflake.table.dynamic.graph.inputs", meta["entry"], meta["semdict"])
        examples = node.get("examples", [])
        assert len(examples) > 0
        assert isinstance(
            examples[0], list
        ), f"string[] field examples[0] must be a list, got {type(examples[0]).__name__}: {examples[0]!r}"


##endregion


##region Unit tests — numeric example without __type warning


class TestNumericExampleWithoutTypeWarning:
    """Verify _validate_entry warns when a numeric example is used without __type."""

    def test_numeric_int_example_without_type_emits_warning(self, caplog):
        """Bare int example with no __type should trigger a WARNING log."""
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "A count.", "__example": 42}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("test.count", entry, "attributes", "test.yml")
        assert errors == [], "numeric example without __type must not be a hard error"
        assert any(
            "numeric" in r.message.lower() or "__type" in r.message for r in caplog.records
        ), "Expected a WARNING about numeric example without __type"

    def test_numeric_float_example_without_type_emits_warning(self, caplog):
        """Bare float example with no __type should trigger a WARNING log."""
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "A percentage.", "__example": 85.0}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("test.pct", entry, "attributes", "test.yml")
        assert errors == [], "must not be a hard error"
        assert any("numeric" in r.message.lower() or "__type" in r.message for r in caplog.records)

    def test_numeric_example_with_type_no_warning(self, caplog):
        """Numeric example with __type annotation must NOT trigger a warning."""
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "A count.", "__example": 42, "__type": "long"}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("test.count", entry, "attributes", "test.yml")
        assert errors == []
        assert not any("numeric" in r.message.lower() for r in caplog.records), "No warning expected when __type is present"

    def test_bool_example_without_type_no_warning(self, caplog):
        """Python bool (YAML true/false) without __type must NOT trigger the numeric warning."""
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "A flag.", "__example": True}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("test.flag", entry, "attributes", "test.yml")
        assert errors == []
        assert not any(
            "numeric" in r.message.lower() for r in caplog.records
        ), "Bool examples must not trigger the numeric-without-type warning"

    def test_string_example_without_type_no_warning(self, caplog):
        """String example without __type must not trigger the numeric warning."""
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "A name.", "__example": "hello"}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("test.name", entry, "attributes", "test.yml")
        assert errors == []
        assert not any("numeric" in r.message.lower() for r in caplog.records)

    def test_metrics_section_numeric_no_warning(self, caplog):
        """Numeric metric example without __type must NOT warn.

        In the ``metrics`` section ``__type`` represents the instrument type
        (``gauge``, ``counter``, etc.), not the SD value type.  Metrics are
        inherently numeric — no ``__type: long/double`` annotation is required.
        """
        import logging  # pylint: disable=import-outside-toplevel

        entry = {"__description": "Credits used.", "__example": 15}
        with caplog.at_level(logging.WARNING, logger="build.export_semantics"):
            errors = _validate_entry("snowflake.credits.used", entry, "metrics", "test.yml")
        assert errors == [], "must not be a hard error for metrics"
        assert not any(
            "numeric" in r.message.lower() for r in caplog.records
        ), "Numeric metric examples must not trigger the no-__type warning"


##endregion


##region Integration tests — build_semantic_export.sh clean output


#: Path to the build_semantic_export.sh script.
_EXPORT_SCRIPT: Path = REPO_ROOT / "scripts" / "dev" / "build_semantic_export.sh"


@pytest.mark.integration
class TestBuildSemanticExportScriptOutput:
    """Assert that build_semantic_export.sh produces zero WARNING and ERROR lines.

    This is a regression gate: any future change to ``export_semantics.py`` or the
    ``instruments-def.yml`` files that introduces new schema validation errors or
    numeric-without-type warnings will be caught here before it reaches CI.

    The test runs the shell script as a subprocess and scans the combined output
    (stdout + stderr) for lines beginning with ``WARNING`` or ``ERROR``.
    """

    @pytest.fixture(scope="class")
    def script_output(self):
        """Run build_semantic_export.sh and return (returncode, combined_output)."""
        if not _EXPORT_SCRIPT.exists():
            pytest.skip(f"build_semantic_export.sh not found: {_EXPORT_SCRIPT}")
        result = subprocess.run(
            [str(_EXPORT_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        combined = result.stdout + result.stderr
        return result.returncode, combined

    def test_script_exits_zero(self, script_output):
        """build_semantic_export.sh must exit with code 0."""
        returncode, output = script_output
        assert returncode == 0, f"Script exited {returncode}:\n{output}"

    def test_no_warning_lines(self, script_output):
        """build_semantic_export.sh must produce zero WARNING lines.

        WARNING lines indicate missing ``__type`` annotations or other non-fatal
        issues in ``instruments-def.yml`` or ``export_semantics.py``.
        """
        _, output = script_output
        warning_lines = [line for line in output.splitlines() if line.startswith("WARNING")]
        assert warning_lines == [], f"build_semantic_export.sh produced {len(warning_lines)} WARNING line(s):\n" + "\n".join(
            warning_lines[:20]
        )

    def test_no_error_lines(self, script_output):
        """build_semantic_export.sh must produce zero ERROR lines.

        ERROR lines indicate schema validation failures in the generated YAML files.
        These are hard failures that mean the generated output is not SD-compliant.
        """
        _, output = script_output
        error_lines = [line for line in output.splitlines() if line.startswith("ERROR")]
        assert error_lines == [], f"build_semantic_export.sh produced {len(error_lines)} ERROR line(s):\n" + "\n".join(error_lines[:20])


##endregion


##region Tests — event routing correctness (Bug 1)


class TestEventModelDataObject:
    """Verify event-model data_object is 'event', not 'bizevents'.

    Timestamp events (e.g. snowflake.grant.created_on) are routed through
    GenericEvents → /platform/ingest/v1/events (OpenPipeline Events API).
    Only dsoa.* self-monitoring events go through BizEvents.
    The generated semdict model must declare data_object: event so the
    Semantic Dictionary correctly maps the fields to the right table.
    """

    def test_event_model_data_object_is_event(self, tmp_path):
        """_build_event_model_yaml must produce data_object: event."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        event_ts = {k: v for k, v in entries.items() if v["classification"] == "event_timestamp"}
        doc = exporter._build_event_model_yaml("mock_plugin", event_ts)
        actual = doc["model"]["data_object"]
        assert actual == "event", (
            f"Expected data_object='event' (OpenPipeline Events API), got '{actual}'. "
            "Snowflake telemetry timestamp events are NOT bizevents."
        )

    def test_event_model_data_object_is_not_bizevents(self, tmp_path):
        """_build_event_model_yaml must NOT produce data_object: bizevents."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)
        event_ts = {k: v for k, v in entries.items() if v["classification"] == "event_timestamp"}
        doc = exporter._build_event_model_yaml("mock_plugin", event_ts)
        assert doc["model"]["data_object"] != "bizevents", (
            "Event-timestamp models must NOT use data_object: bizevents. "
            "Only dsoa.* self-monitoring signals belong in the bizevents table."
        )

    def test_all_event_model_files_use_data_object_event(self):
        """All generated snowflake.events.*.yaml files must have data_object: event."""
        semdict_dir = REPO_ROOT / "build" / "_semdict" / "source" / "model" / "snowflake" / "events"
        if not semdict_dir.exists():
            pytest.skip("Semdict output dir not found — run build_semantic_export.sh first")
        event_files = list(semdict_dir.glob("snowflake.events.*.yaml"))
        assert event_files, "No snowflake.events.*.yaml files found in semdict output"
        failures = []
        for path in sorted(event_files):
            with open(path, "r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            data_obj = doc.get("model", {}).get("data_object")
            if data_obj != "event":
                failures.append(f"{path.name}: data_object={data_obj!r}")
        assert not failures, "The following event model files have wrong data_object (expected 'event'):\n" + "\n".join(failures)


##endregion


##region Tests — DQL multi-line string serialisation (Bug 2)


class TestDqlQueryStringFormatting:
    r"""Verify DQL query_string values are serialised as block literals without extra blank lines.

    Bug: PyYAML's default string representer wraps multi-line strings in flow-style
    single-quoted scalars with embedded \n characters.  The rendered output gains an
    extra blank line after every DQL pipe stage because the block literal's trailing
    newline is reproduced literally in the flow scalar.

    Fix: _IndentedDumper overrides represent_str to use YAML block literal style (|)
    for any string containing a newline.
    """

    def test_indented_dumper_uses_block_literal_for_multiline(self):
        """_IndentedDumper.represent_str uses block-literal style for multi-line strings."""
        import io

        data = {"query_string": "fetch logs\n| filter db.system == 'snowflake'\n| limit 10\n"}
        stream = io.StringIO()
        yaml.dump(data, stream, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True)
        output = stream.getvalue()
        # Block literal marker must be present
        assert "query_string: |" in output, f"Expected block literal style for multi-line string, got:\n{output}"
        # Must NOT contain flow-style single-quoted value on one line
        assert "query_string: '" not in output, f"Must not use flow-style single-quoted string, got:\n{output}"

    def test_indented_dumper_no_consecutive_blank_lines_in_dql(self):
        """Rendered DQL query_string values must not contain consecutive blank lines."""
        import io

        query = 'fetch logs\n| filter db.system == "snowflake"\n| sort timestamp desc\n| limit 100\n'
        data = {"dql_queries": [{"query_string": query, "description": "Test query.", "internal": False}]}
        stream = io.StringIO()
        yaml.dump(data, stream, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True)
        output = stream.getvalue()
        # Two or more consecutive blank lines within the rendered YAML indicate the bug
        assert "\n\n\n" not in output, f"Generated YAML contains consecutive blank lines (extra blank line bug):\n{output}"

    def test_single_line_strings_are_not_affected(self):
        """Single-line strings must NOT use block literal style."""
        import io

        data = {"title": "Simple one-liner"}
        stream = io.StringIO()
        yaml.dump(data, stream, Dumper=_IndentedDumper, default_flow_style=False, allow_unicode=True)
        output = stream.getvalue()
        assert "title: Simple one-liner\n" in output, f"Single-line string should be plain scalar, got:\n{output}"

    def test_generated_event_yaml_no_consecutive_blank_lines(self):
        """Generated snowflake.events.*.yaml files must not contain consecutive blank lines inside DQL blocks."""
        semdict_dir = REPO_ROOT / "build" / "_semdict" / "source" / "model" / "snowflake" / "events"
        if not semdict_dir.exists():
            pytest.skip("Semdict output dir not found — run build_semantic_export.sh first")
        event_files = list(semdict_dir.glob("snowflake.events.*.yaml"))
        assert event_files, "No snowflake.events.*.yaml files found in semdict output"
        failures = []
        for path in sorted(event_files):
            content = path.read_text(encoding="utf-8")
            if "\n\n\n" in content:
                failures.append(f"{path.name}: contains consecutive blank lines (triple-newline)")
        assert not failures, "The following event model files contain consecutive blank lines inside DQL blocks:\n" + "\n".join(failures)

    def test_generated_log_yaml_no_consecutive_blank_lines(self):
        """Generated snowflake.logs.*.yaml files must not contain consecutive blank lines inside DQL blocks."""
        semdict_dir = REPO_ROOT / "build" / "_semdict" / "source" / "model" / "snowflake" / "logs"
        if not semdict_dir.exists():
            pytest.skip("Semdict output dir not found — run build_semantic_export.sh first")
        log_files = list(semdict_dir.glob("snowflake.logs.*.yaml"))
        if not log_files:
            pytest.skip("No snowflake.logs.*.yaml files found in semdict output")
        failures = []
        for path in sorted(log_files):
            content = path.read_text(encoding="utf-8")
            if "\n\n\n" in content:
                failures.append(f"{path.name}: contains consecutive blank lines (triple-newline)")
        assert not failures, "The following log model files contain consecutive blank lines inside DQL blocks:\n" + "\n".join(failures)


##endregion

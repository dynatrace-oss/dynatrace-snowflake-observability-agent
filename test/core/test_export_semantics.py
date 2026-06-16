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
    ExportError,
    SemanticExporter,
    _emit_id_entry,
    _emit_metric_entry,
    _emit_ref_entry,
    _map_attr_type,
    _map_metric_instrument,
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
        """otel-only without __otel_note fails."""
        entry = {"__description": "D.", "__example": "E.", "__semdict": "otel-only"}
        errors = _validate_entry("test.field", entry, "attributes", "test.yml")
        assert any("__otel_note" in e for e in errors)


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
        """Ref entry with __otel_note includes note in output."""
        entry = {
            "__semdict": "ref",
            "__description": "Auth method.",
            "__example": "PASSWORD",
            "__otel_note": "Custom enum gap.",
        }
        node = _emit_ref_entry("authentication.type", entry)
        assert node.get("note") == "Custom enum gap."


##endregion


##region Unit tests — id: block emission


class TestIdEmission:
    """Verify new/deprecated-alias/otel-only entries emit full id: blocks."""

    def test_new_entry_has_id_block(self):
        """New entry produces id: block with required fields."""
        entry = {
            "__semdict": "new",
            "__description": "Unique run ID.",
            "__example": "4aa7c76c",
        }
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
        """deprecated-alias entry has stability: deprecated."""
        entry = {
            "__semdict": "deprecated-alias",
            "__otel_replacement": "deployment.environment.name",
            "__otel_note": "Renamed in v1.26.",
            "__description": "Deployment env.",
            "__example": "PROD",
        }
        node = _emit_id_entry("deployment.environment", entry, "deprecated-alias")
        assert node["stability"] == "deprecated"
        assert "deprecated" in node
        assert "deployment.environment.name" in node["deprecated"]

    def test_deprecated_alias_has_note(self):
        """deprecated-alias entry includes note from __otel_note."""
        entry = {
            "__semdict": "deprecated-alias",
            "__otel_replacement": "deployment.environment.name",
            "__otel_note": "Renamed in v1.26.",
            "__description": "Deployment env.",
            "__example": "PROD",
        }
        node = _emit_id_entry("deployment.environment", entry, "deprecated-alias")
        assert node.get("note") == "Renamed in v1.26."

    def test_otel_only_has_note(self):
        """otel-only entry includes note from __otel_note."""
        entry = {
            "__semdict": "otel-only",
            "__otel_note": "OTel Development-tier.",
            "__description": "Session ID.",
            "__example": "123",
        }
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


##region Unit tests — metric emission


class TestMetricEmission:
    """Verify metric entries emit instrument, unit, metric_name."""

    def test_metric_has_instrument_and_unit(self):
        """Metric entry emits instrument and unit."""
        entry = {
            "__semdict": "new",
            "__type": "gauge",
            "__unit": "{credits}",
            "__description": "Credits used.",
            "__example": "42.5",
        }
        node = _emit_metric_entry("snowflake.warehouse.credits.used", entry)
        assert node["instrument"] == "gauge"
        assert node["unit"] == "{credits}"
        assert node["metric_name"] == "snowflake.warehouse.credits.used"
        assert node["type"] == "metric"

    def test_metric_unit_from_unit_key(self):
        """Metric unit can come from 'unit' key (not just __unit)."""
        entry = {
            "__semdict": "new",
            "__type": "counter",
            "unit": "ms",
            "__description": "Time.",
            "__example": "100",
        }
        node = _emit_metric_entry("test.time", entry)
        assert node["unit"] == "ms"

    def test_counter_instrument(self):
        """__type: count maps to instrument: counter."""
        entry = {
            "__semdict": "new",
            "__type": "count",
            "__unit": "1",
            "__description": "Query count.",
            "__example": "100",
        }
        node = _emit_metric_entry("test.count", entry)
        assert node["instrument"] == "counter"

    def test_updowncounter_instrument(self):
        """__type: updowncounter maps correctly."""
        entry = {
            "__semdict": "new",
            "__type": "updowncounter",
            "__unit": "bytes",
            "__description": "Memory.",
            "__example": "1024",
        }
        node = _emit_metric_entry("test.memory", entry)
        assert node["instrument"] == "updowncounter"

    def test_histogram_instrument(self):
        """__type: histogram maps correctly."""
        entry = {
            "__semdict": "new",
            "__type": "histogram",
            "__unit": "ms",
            "__description": "Latency dist.",
            "__example": "250",
        }
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
        # Create a minimal fixture with no __semdict flag
        minimal = tmp_path / "minimal.yml"
        minimal.write_text("attributes:\n  my.field:\n    __description: D.\n    __example: E.\n")
        _, entries = exporter._parse_file("test", minimal)
        assert entries["my.field"]["semdict"] == "new"

    def test_generated_yaml_has_groups(self, tmp_path):
        """Exporter emits valid YAML with 'groups' key."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)

        # Build a plugin yaml from the entries
        plugin_entries = {k: v for k, v in entries.items() if v["semdict"] != "ref"}
        doc = exporter._build_plugin_yaml("mock_plugin", plugin_entries)

        assert "groups" in doc
        assert len(doc["groups"]) > 0

    def test_ref_not_in_attribute_group_id_block(self, tmp_path):
        """Ref entries appear as {'ref': key} not {'id': key} in output."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)

        ref_meta = entries["db.system"]
        node = exporter._build_attribute_node("db.system", ref_meta)
        assert "ref" in node
        assert "id" not in node

    def test_deprecated_alias_in_output(self, tmp_path):
        """deprecated-alias entry in plugin output has stability: deprecated."""
        out_dir = tmp_path / "out"
        exporter = SemanticExporter(repo_root=REPO_ROOT, output_dir=out_dir)
        _, entries = exporter._parse_file("mock_plugin", MOCK_FIXTURE)

        dep_meta = entries["deployment.environment"]
        node = exporter._build_attribute_node("deployment.environment", dep_meta)
        assert node.get("stability") == "deprecated"
        assert "deprecated" in node


##endregion


##region Integration tests


@pytest.mark.integration
@pytest.mark.skipif(not os.path.exists("build"), reason="build dir absent")
class TestSemanticExporterIntegration:
    """Integration tests: run full pipeline against real codebase.

    These tests require the repository to have a build/ directory
    (created by running ./scripts/dev/build.sh) and are only executed
    when explicitly requested via -m integration.
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

    def test_global_file_exists(self, export_output):
        """snowflake_global.yaml is created."""
        out_dir, _ = export_output
        global_file = out_dir / "fields" / "snowflake" / "snowflake_global.yaml"
        assert global_file.exists(), "snowflake_global.yaml not found"

    def test_metrics_dir_exists(self, export_output):
        """metrics/ directory is created under model/smartscape/db/snowflake/."""
        out_dir, _ = export_output
        metrics_dir = out_dir / "model" / "smartscape" / "db" / "snowflake" / "metrics"
        assert metrics_dir.exists(), "metrics/ directory not found"

    def test_nonzero_field_count(self, export_output):
        """Total field count is non-zero."""
        _, summary = export_output
        total = summary["ref"] + summary["new"] + summary["deprecated_alias"] + summary["otel_only"]
        assert total > 0, "No fields exported"

    def test_global_yaml_parseable(self, export_output):
        """snowflake_global.yaml is valid YAML with groups key."""
        out_dir, _ = export_output
        global_file = out_dir / "fields" / "snowflake" / "snowflake_global.yaml"
        with open(global_file, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert "groups" in doc
        assert len(doc["groups"]) > 0


##endregion

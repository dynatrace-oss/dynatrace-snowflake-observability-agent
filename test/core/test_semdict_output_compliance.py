"""Tests that validate the generated build/_semdict/source/ YAML files for SD compliance.

These are integration tests that read the actual generated output files and check
for structural compliance: no ref: in field definition files, correct YAML indentation,
valid unit values, proper type annotations, model existence, and orphan field counts.

Note:
    All tests skip with ``pytest.skip()`` if ``build/_semdict/source/`` does not exist.
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
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
import yaml

from test.core._semdict_test_utils import (
    INVALID_SD_UNITS,
    SEMDICT_SOURCE,
    collect_model_referenced_fields,
    collect_signal_field_ids,
    load_all_generated_yaml,
    load_all_instruments_defs,
    require_semdict_source,
)

##region Fixtures

#: Plugins known to emit spans (in addition to logs).
SPAN_PLUGINS: frozenset = frozenset({"query_history", "event_log"})

#: Fields that are structural OTel/platform attributes — exempt from orphan check.
EXEMPT_ORPHAN_FIELDS: frozenset = frozenset({"observed_timestamp"})

#: Max allowed orphan signal fields. Target: 0. Currently 9 known orphans remain
#: (10 including observed_timestamp, but that one is in EXEMPT_ORPHAN_FIELDS).
#: These are dimension-only fields (not in any attributes: section) whose context names
#: don't match any surviving metric context in their plugin (either due to log-only contexts
#: or cross-plugin metric dedup removing the applicable metric from that plugin's model).
#: Known orphans: client.ip, client.type, event.name (login_history dims/log context only),
#: snowflake.grant.name, snowflake.share.name (shares dims), snowflake.task.is_internal,
#: snowflake.task.name (tasks dims; credits.used metric deduped to event_usage),
#: snowflake.warehouse.event.name, snowflake.warehouse.event.state (warehouse_usage dims).
MAX_ORPHAN_SIGNAL_FIELDS: int = 9

##endregion


##region Helpers


def _require_semdict_source() -> None:
    """Skip the test if build/_semdict/source/ does not exist.

    Raises:
        pytest.skip: If the output directory is missing.
    """
    require_semdict_source()


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a single YAML file.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed YAML content as dict.
    """
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_all_generated() -> Dict[str, Dict[str, Any]]:
    """Thin wrapper around shared utility.

    Returns:
        Dict mapping relative path to parsed YAML content.
    """
    return load_all_generated_yaml()


def _collect_signal_field_ids(generated: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Wrapper for shared signal field ID collection.

    Args:
        generated: All parsed generated YAML docs.

    Returns:
        Set of field id strings from signal_fields/ files.
    """
    return collect_signal_field_ids(generated)


def _collect_model_referenced_fields(generated: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Wrapper for shared model-referenced field collection.

    Args:
        generated: All parsed generated YAML docs.

    Returns:
        Set of field keys referenced by any model or interface.
    """
    return collect_model_referenced_fields(generated)


##endregion


##region Tests


@pytest.mark.integration
class TestGroupIdUniqueness:
    """Group IDs must be unique across all generated YAML files."""

    def test_no_group_id_collisions(self):
        """Every group id: must appear exactly once across all generated files.

        B1: 'db' must not appear as both resource and attribute_group.
        B2: 'snowflake.warehouse' must not appear as both resource and attribute_group.
        """
        generated = _load_all_generated()

        id_to_files: Dict[str, List[str]] = {}
        for rel_path, doc in generated.items():
            for group in doc.get("groups", []):
                gid = group.get("id")
                if gid:
                    id_to_files.setdefault(gid, []).append(rel_path)

        collisions = {gid: files for gid, files in id_to_files.items() if len(files) > 1}
        assert not collisions, "Group ID collisions detected:\n" + "\n".join(
            f"  {gid}: {files}" for gid, files in sorted(collisions.items())
        )


@pytest.mark.integration
class TestUnitValidity:
    """Generated metric files must not contain invalid unit values."""

    def test_all_unit_values_valid_in_metric_files(self):
        """All unit: values in generated metric model files must not be raw invalid strings.

        After UNIT_MAP translation, units like 'bytes', 'percent', 'rows' must not
        appear in the output — they must have been translated to 'By', '%', 'count', etc.
        """
        generated = _load_all_generated()

        violations: List[str] = []
        for rel_path, doc in generated.items():
            if "dsoa_metrics_" not in rel_path and "metrics/" not in rel_path:
                continue
            model = doc.get("model", {})
            for group in model.get("groups", []):
                unit = group.get("unit")
                if unit and unit in INVALID_SD_UNITS:
                    violations.append(f"{rel_path}: {group.get('id', '?')} has invalid unit {unit!r}")

        assert not violations, "Metrics with invalid unit values in output:\n" + "\n".join(violations)


@pytest.mark.integration
class TestNoRefInFieldDefinitionFiles:
    """Field definition files (fields/signal_fields/) must not contain ref: entries.

    Refs belong exclusively in interfaces. See C1/N3 findings.
    """

    def test_no_ref_in_signal_fields(self):
        """Files under fields/signal_fields/ must not contain ref: attribute entries.

        Known violations before fix:
        - fields/signal_fields/db.yaml: ref: db.query.text
        - fields/signal_fields/authentication.yaml: ref: authentication.type
        - fields/signal_fields/event.yaml: ref: event.id
        """
        _require_semdict_source()

        signal_fields_dir = SEMDICT_SOURCE / "fields" / "signal_fields"
        if not signal_fields_dir.exists():
            pytest.skip("fields/signal_fields/ directory not found in generated output")

        violations: List[str] = []
        for yaml_file in sorted(signal_fields_dir.glob("*.yaml")):
            doc = _load_yaml(yaml_file)
            rel = str(yaml_file.relative_to(SEMDICT_SOURCE))
            for group in doc.get("groups", []):
                for attr in group.get("attributes", []):
                    if "ref" in attr:
                        violations.append(f"{rel}: contains ref: {attr['ref']} (should be in an interface only)")

        assert not violations, "Signal field definition files with ref: entries:\n" + "\n".join(violations)

    def test_no_ref_in_resource_fields(self):
        """Files under fields/resource_fields/ must not contain ref: attribute entries.

        The dsoa.yaml fix from A4 should have removed these. This test guards
        against regression.
        """
        _require_semdict_source()

        resource_fields_dir = SEMDICT_SOURCE / "fields" / "resource_fields"
        if not resource_fields_dir.exists():
            pytest.skip("fields/resource_fields/ directory not found in generated output")

        violations: List[str] = []
        for yaml_file in sorted(resource_fields_dir.glob("*.yaml")):
            doc = _load_yaml(yaml_file)
            rel = str(yaml_file.relative_to(SEMDICT_SOURCE))
            for group in doc.get("groups", []):
                for attr in group.get("attributes", []):
                    if "ref" in attr:
                        violations.append(f"{rel}: contains ref: {attr['ref']} (should be in an interface only)")

        assert not violations, "Resource field definition files with ref: entries:\n" + "\n".join(violations)


@pytest.mark.integration
class TestYamlIndentation:
    """Generated YAML must use proper block-style indentation (SD convention)."""

    # Pattern that detects compact (incorrect) sequence notation:
    # A key at any indentation followed immediately by '- ' on the NEXT line
    # at the SAME indentation level.
    #
    # Correct (indented):
    #   groups:\n    - id: foo
    # Incorrect (compact):
    #   groups:\n  - id: foo  (when 'groups:' is at indent 0 and '-' is at indent 2
    #                           but parent key is also at indent 0)
    #
    # Detection: if a '-' line is at the same column as the parent key
    # e.g. "groups:\n- id:" (0-indent groups, 0-indent dash = compact)
    _COMPACT_SEQ_RE = re.compile(r"^(\s*)(\w[\w.]*):(?:\s*#.*)?\n(\1- )", re.MULTILINE)

    def _check_file_indentation(self, path: Path) -> List[str]:
        """Check a single YAML file for compact sequence notation.

        Args:
            path: Path to YAML file.

        Returns:
            List of violation descriptions.
        """
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        violations: List[str] = []
        for match in self._COMPACT_SEQ_RE.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            violations.append(f"  line {line_no}: key '{match.group(2)}' has list item at same indent level (compact notation)")
        return violations

    def test_signal_fields_use_block_style_indentation(self):
        """Signal field files must use properly indented block sequences.

        The '-' list item marker must be indented 2 spaces under its parent key.

        INCORRECT (PyYAML compact default):
          attributes:
          - id: foo      <- '-' at same level as 'attributes:'

        CORRECT (SD convention):
          attributes:
            - id: foo    <- '-' indented under 'attributes:'
        """
        _require_semdict_source()

        signal_fields_dir = SEMDICT_SOURCE / "fields" / "signal_fields"
        if not signal_fields_dir.exists():
            pytest.skip("fields/signal_fields/ directory not found in generated output")

        # Check a representative sample (first 5 files)
        sample_files = sorted(signal_fields_dir.glob("*.yaml"))[:5]
        if not sample_files:
            pytest.skip("No signal field files found")

        violations: List[str] = []
        for yaml_file in sample_files:
            file_violations = self._check_file_indentation(yaml_file)
            if file_violations:
                rel = str(yaml_file.relative_to(SEMDICT_SOURCE))
                violations.append(f"{rel}:\n" + "\n".join(file_violations))

        assert not violations, "YAML files with compact sequence indentation:\n" + "\n".join(violations)


@pytest.mark.integration
class TestBooleanTypesInOutput:
    """Fields with __type: boolean in instruments-def must be typed boolean in output."""

    #: Fields confirmed to have __type: boolean in instruments-def after Phase 2 fixes.
    EXPECTED_BOOLEAN_FIELDS: frozenset = frozenset(
        {
            "snowflake.warehouse.has_query_acceleration_enabled",
            "snowflake.warehouse.is_auto_resume",
            "snowflake.warehouse.is_auto_suspend",
            "snowflake.user.has_mfa",
            "snowflake.user.has_password",
            "snowflake.user.is_disabled",
            "snowflake.user.is_locked",
            "snowflake.user.must_change_password",
            "snowflake.query.is_client_generated",
            "snowflake.user.ext_authn.duo",
            "snowflake.grant.option",
            "plugins.query_history.track_ddl_changes",
        }
    )

    def test_boolean_fields_typed_boolean_in_output(self):
        """Fields with __type: boolean in source must have type: boolean in generated YAML.

        A type: string in output for a boolean field indicates the __type annotation
        was not correctly processed by the export pipeline.
        """
        generated = _load_all_generated()

        # Build flat map: field_key → attribute_node
        output_nodes: Dict[str, Dict[str, Any]] = {}
        for doc in generated.values():
            for group in doc.get("groups", []):
                for attr in group.get("attributes", []):
                    key = attr.get("id")
                    if key and key not in output_nodes:
                        output_nodes[key] = attr

        violations: List[str] = []
        for key in self.EXPECTED_BOOLEAN_FIELDS:
            node = output_nodes.get(key)
            if node is None:
                continue  # field may not be present yet (Phase 2 adds it)
            actual_type = node.get("type")
            if actual_type != "boolean":
                violations.append(f"{key}: expected type: boolean in output, got {actual_type!r}")

        assert not violations, "Boolean fields incorrectly typed in output:\n" + "\n".join(violations)


@pytest.mark.integration
class TestDeprecationInOutput:
    """Deprecated fields must have stability: deprecated in generated output."""

    def test_deployment_environment_has_deprecated_stability(self):
        """deployment.environment must have stability: deprecated in generated output.

        The field's own note already says it was renamed in OTel v1.26. The
        generated YAML must reflect this by setting stability: deprecated (not experimental).
        """
        generated = _load_all_generated()

        for doc in generated.values():
            for group in doc.get("groups", []):
                for attr in group.get("attributes", []):
                    if attr.get("id") == "deployment.environment":
                        stability = attr.get("stability")
                        assert stability == "deprecated", f"deployment.environment: expected stability: deprecated, got {stability!r}"
                        return  # found and checked

        pytest.fail("deployment.environment not found in any generated YAML file")


@pytest.mark.integration
class TestOrphanSignalFields:
    """Signal fields must be referenced by at least one model or interface."""

    def test_orphan_signal_field_count_at_or_below_max(self):
        """Signal field id: keys not referenced by any model must be <= MAX_ORPHAN_SIGNAL_FIELDS.

        Target is 0 after log/span models are created (Phase 4). Until then, this
        test guards against regressions by failing if the orphan count INCREASES
        beyond the max.

        Exempt fields (structural OTel attributes not owned by DSOA):
        - observed_timestamp
        """
        generated = _load_all_generated()

        signal_ids = _collect_signal_field_ids(generated)
        referenced = _collect_model_referenced_fields(generated)

        orphans = signal_ids - referenced - EXEMPT_ORPHAN_FIELDS

        assert len(orphans) <= MAX_ORPHAN_SIGNAL_FIELDS, (
            f"Found {len(orphans)} orphan signal fields (max allowed: {MAX_ORPHAN_SIGNAL_FIELDS}).\n"
            f"Orphans (first 30): {sorted(orphans)[:30]}"
        )


@pytest.mark.integration
class TestModelsExistForAllPlugins:
    """Plugins with attributes must have corresponding log (and span) model files."""

    def test_log_models_exist_for_all_attribute_plugins(self):
        """Every plugin with attributes: in instruments-def must have a dsoa.logs.<plugin>.yaml.

        This test will be RED until Phase 4 (log/span model generation) is complete.
        """
        _require_semdict_source()

        model_dir = SEMDICT_SOURCE / "model" / "dsoa"
        if not model_dir.exists():
            pytest.fail("model/dsoa/ directory not found in generated output")

        existing_log_models: Set[str] = set()
        for yaml_file in model_dir.glob("dsoa.logs.*.yaml"):
            # Extract plugin name from filename like dsoa.logs.query_history.yaml
            stem = yaml_file.stem  # e.g. "dsoa.logs.query_history"
            parts = stem.split(".")
            if len(parts) >= 3:
                plugin_name = ".".join(parts[2:])
                existing_log_models.add(plugin_name)

        # Check instruments-def for plugins that actually have attributes
        plugins_needing_models: Set[str] = set()
        for plugin_name, data in load_all_instruments_defs().items():
            if plugin_name == "_core":
                continue
            if data.get("attributes"):
                plugins_needing_models.add(plugin_name)

        missing = plugins_needing_models - existing_log_models
        assert not missing, "Plugins with attributes but no log model:\n" + "\n".join(
            f"  model/dsoa/dsoa.logs.{p}.yaml" for p in sorted(missing)
        )

    def test_span_models_exist_for_span_plugins(self):
        """Span-emitting plugins (query_history, event_log) must have dsoa.spans.<plugin>.yaml."""
        _require_semdict_source()

        model_dir = SEMDICT_SOURCE / "model" / "dsoa"
        if not model_dir.exists():
            pytest.fail("model/dsoa/ directory not found in generated output")

        existing_span_models: Set[str] = set()
        for yaml_file in model_dir.glob("dsoa.spans.*.yaml"):
            stem = yaml_file.stem
            parts = stem.split(".")
            if len(parts) >= 3:
                plugin_name = ".".join(parts[2:])
                existing_span_models.add(plugin_name)

        missing = SPAN_PLUGINS - existing_span_models
        assert not missing, "Span-emitting plugins missing span models:\n" + "\n".join(
            f"  model/dsoa/dsoa.spans.{p}.yaml" for p in sorted(missing)
        )


##endregion

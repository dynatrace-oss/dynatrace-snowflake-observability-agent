"""Cross-plugin semantic quality tests for the DSOA instruments-def.yml files.

Tests that the instruments-def source data has correct cross-plugin semantic
consistency: unit values, divergence notes, dimension coverage, and orphan
field analysis against the generated ``build/_semdict/source/`` output.

Note:
    Tests that read ``build/_semdict/source/`` are skipped with
    ``pytest.skip()`` if the directory does not exist.
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

from typing import Any, Dict, Set

import pytest

from build.export_semantics import (
    INTERFACE_DATABASE_KEYS,
    INTERFACE_WAREHOUSE_KEYS,
    RESOURCE_ATTRIBUTE_KEYS,
    UNIT_MAP,
)
from test.core._semdict_test_utils import (
    INVALID_SD_UNITS,
    SEMDICT_SOURCE,
    collect_model_referenced_fields,
    collect_signal_field_ids,
    load_all_generated_yaml,
    load_all_instruments_defs,
)

##region Fixtures

#: SD-valid unit abbreviations (authoritative subset; checked against unit_registry.py).
VALID_SD_UNITS: frozenset = frozenset(
    {
        "By",
        "KiBy",
        "MiBy",
        "GiBy",
        "TiBy",
        "%",
        "d",
        "s",
        "ms",
        "min",
        "1",
        "ratio",
        "count",
        "US$",
        "h",
        "{request}",
        "{error}",
        "{fault}",
        "{span}",
        "{operation}",
        "{connection}",
        "{thread}",
        "{class}",
        "{bucket}",
        "{packet}",
        "{invocation}",
        "{process}",
        "{message}",
        "{exception}",
        "{event}",
    }
)

#: Fields that SHOULD have a divergence note (OTel divergence documented).
_DIVERGENCE_NOTE_FIELDS: Dict[str, str] = {
    "client.ip": "client.address",
    "db.system": "db.system.name",
}

##endregion


##region Helpers


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


def _collect_all_signal_field_keys(generated_docs: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Wrapper for shared signal field ID collection.

    Args:
        generated_docs: All parsed generated YAML docs.

    Returns:
        Set of field key strings from signal_fields files.
    """
    return collect_signal_field_ids(generated_docs)


def _collect_all_model_referenced_fields(generated_docs: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Wrapper for shared model-referenced field collection.

    Args:
        generated_docs: All parsed generated YAML docs.

    Returns:
        Set of referenced field key strings.
    """
    return collect_model_referenced_fields(generated_docs)


##endregion


##region Tests


@pytest.mark.integration
class TestUnitValueValidity:
    """All unit values in instruments-def.yml must map to valid SD units."""

    def test_no_invalid_unit_values_in_source(self):
        """Every unit: in any metrics section must not contain raw invalid values.

        After UNIT_MAP translation, no output file should contain units like
        'bytes', 'percent', 'rows', etc. — those must be translated.
        The SOURCE instruments-def may still have them; this test verifies
        the UNIT_MAP covers all cases.
        """
        all_defs = _load_all_instruments_defs()

        uncovered = []
        for plugin_name, data in all_defs.items():
            for key, entry in (data.get("metrics") or {}).items():
                raw_unit = entry.get("unit") or entry.get("__unit")
                if raw_unit is None:
                    continue
                unit_str = str(raw_unit).strip('"').strip("'")
                mapped = UNIT_MAP.get(unit_str, unit_str)
                # Mapped unit must be valid SD unit or already a valid SD unit
                if mapped not in VALID_SD_UNITS:
                    uncovered.append(f"{plugin_name}.{key}: unit={unit_str!r} → mapped={mapped!r} (not in VALID_SD_UNITS)")
        assert not uncovered, "Metrics with unmapped unit values:\n" + "\n".join(uncovered)

    def test_no_invalid_units_in_generated_output(self):
        """Generated YAML metric files must not contain invalid unit strings.

        Tests against the actual build/_semdict/source/metrics/ files.
        """
        generated = _load_generated_yaml_files()

        violations = []
        for rel_path, doc in generated.items():
            if "metrics" not in rel_path:
                continue
            for group in doc.get("groups", []):
                unit = group.get("unit")
                if unit and unit in INVALID_SD_UNITS:
                    violations.append(f"{rel_path}: metric {group.get('id', '?')} has invalid unit {unit!r}")
            # Also check metric entries at top level (model-wrapped)
            model = doc.get("model", {})
            for group in model.get("groups", []):
                unit = group.get("unit")
                if unit and unit in INVALID_SD_UNITS:
                    violations.append(f"{rel_path}[model]: metric {group.get('id', '?')} has invalid unit {unit!r}")
        assert not violations, "Generated files with invalid unit values:\n" + "\n".join(violations)


@pytest.mark.integration
class TestDivergenceNotes:
    """OTel-divergent fields must have notes documenting the divergence."""

    def test_divergence_notes_present_in_source(self):
        """client.ip and db.system must have divergence notes in instruments-def.

        These fields diverge from OTel field names and must document the
        divergence so SD reviewers understand the DSOA-specific rationale.
        """
        all_defs = _load_all_instruments_defs()

        # Collect all entries across all sections/plugins
        all_entries: Dict[str, Dict[str, Any]] = {}
        for data in all_defs.values():
            for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
                for key, entry in (data.get(section) or {}).items():
                    if key not in all_entries:
                        all_entries[key] = entry or {}

        violations = []
        for field_key, otel_name in _DIVERGENCE_NOTE_FIELDS.items():
            entry = all_entries.get(field_key)
            if entry is None:
                continue  # field may not exist
            note = entry.get("__semdict_note", "") or ""
            description = entry.get("__description", "") or ""
            combined = (note + " " + description).lower()
            if otel_name.lower() not in combined:
                violations.append(
                    f"{field_key}: missing divergence note referencing OTel field '{otel_name}'. "
                    f"Add __semdict_note mentioning '{otel_name}' to document the divergence."
                )
        assert not violations, "Fields missing OTel divergence notes:\n" + "\n".join(violations)


@pytest.mark.integration
class TestDimensionCoverage:
    """All dimensions in instruments-def must be covered by a model or interface."""

    def test_all_dimensions_covered(self):
        """Every metric-applicable dimension from instruments-def must appear in a metric model.

        A dimension is "metric-applicable" if its context names overlap with any metric
        context names in the same plugin, OR if it has no context names (applies to all contexts).
        Dimensions whose context names only match log/span contexts (and no metric has that
        context) are expected orphans — they are used for log attribute references, not metrics.

        Dimensions covered by global interfaces (i.dsoa_resource, i.dsoa_warehouse,
        i.dsoa_database) are always exempt from this check.

        This test uses the generated output files to verify coverage.
        """
        if not SEMDICT_SOURCE.exists():
            pytest.skip("build/_semdict/source/ not found — run export_semantics.py first")

        all_defs = _load_all_instruments_defs()
        generated = _load_generated_yaml_files()

        # Collect referenced attrs from all metric files
        referenced_in_metrics: Set[str] = set()
        for rel_path, doc in generated.items():
            if "dsoa_metrics_" not in rel_path:
                continue
            model = doc.get("model", {})
            for group in model.get("groups", []):
                for attr in group.get("attributes", []):
                    if "ref" in attr:
                        referenced_in_metrics.add(attr["ref"])
            # Also grab interface-covered fields
            for iface in model.get("interfaces", []):
                if isinstance(iface, dict):
                    ref = iface.get("ref", "")
                    if ref == "i.dsoa_warehouse":
                        referenced_in_metrics |= INTERFACE_WAREHOUSE_KEYS
                    elif ref == "i.dsoa_database":
                        referenced_in_metrics |= INTERFACE_DATABASE_KEYS
                    elif ref == "i.dsoa_resource":
                        referenced_in_metrics |= RESOURCE_ATTRIBUTE_KEYS

        # Build per-plugin metric context names from GENERATED output (not instruments-def)
        # to correctly handle cross-plugin metric dedup: a metric originally in plugin A
        # may be deduped to plugin B, removing it from A's generated model.
        plugin_metric_contexts_generated: Dict[str, Set[str]] = {}
        for rel_path, doc in generated.items():
            if "dsoa_metrics_" not in rel_path:
                continue
            # Extract plugin name from filename like dsoa_metrics_query_history.yaml
            fname = rel_path.split("/")[-1]  # e.g. dsoa_metrics_tasks.yaml
            plugin_nm = fname.replace("dsoa_metrics_", "").replace(".yaml", "")
            model = doc.get("model", {})
            for grp in model.get("groups", []):
                ctx = set(grp.get("__context_names") or [])
                plugin_metric_contexts_generated.setdefault(plugin_nm, set()).update(ctx)

        # Build per-plugin dim sets — only check metric-applicable dimensions.
        # Use instruments-def metric contexts as the primary signal (not generated),
        # but if a plugin's metric was deduped away (not in generated output), skip it.
        violations = []
        for plugin_name, data in all_defs.items():
            if plugin_name == "_core":
                continue
            # Metric contexts from instruments-def (for determining if dim is metric-relevant)
            metric_contexts_src: Set[str] = set()
            for _mk, m_entry in (data.get("metrics") or {}).items():
                metric_contexts_src.update((m_entry or {}).get("__context_names") or [])

            # Metric contexts actually present in generated output (post-dedup)
            metric_contexts_gen = plugin_metric_contexts_generated.get(plugin_name, set())

            for dim_key, dim_entry in (data.get("dimensions") or {}).items():
                if dim_key in RESOURCE_ATTRIBUTE_KEYS:
                    continue  # covered by i.dsoa_resource
                if dim_key in INTERFACE_WAREHOUSE_KEYS:
                    continue  # covered by i.dsoa_warehouse
                if dim_key in INTERFACE_DATABASE_KEYS:
                    continue  # covered by i.dsoa_database
                # Check if this dimension is metric-applicable in the SOURCE:
                # if it has context names, they must overlap with metrics in instruments-def.
                dim_contexts = set((dim_entry or {}).get("__context_names") or [])
                if dim_contexts and not dim_contexts.intersection(metric_contexts_src):
                    continue  # dimension applies to log/span contexts only; not a metric dim
                # Check if the applicable metric contexts survived dedup into generated output.
                # If all applicable metric contexts were deduped away, skip this dimension.
                if dim_contexts:
                    overlap_with_gen = dim_contexts.intersection(metric_contexts_gen)
                else:
                    overlap_with_gen = metric_contexts_gen  # no context restriction = any metric
                if not overlap_with_gen:
                    continue  # applicable metrics were all deduped to another plugin; skip
                if dim_key not in referenced_in_metrics:
                    violations.append(f"{dim_key} (plugin={plugin_name}): dimension not referenced by any metric model")

        assert not violations, "Dimensions defined in instruments-def but missing from metric models:\n" + "\n".join(sorted(violations))


@pytest.mark.integration
class TestOrphanFieldCount:
    """Signal fields must be referenced by at least one model."""

    def test_attribute_orphan_count_at_zero(self):
        """Every signal field id: must be referenced by at least one model or interface.

        After Phase 4 (log/span model generation), the target is reduced to 14 known
        orphans. These are dimension-only signal fields whose context names don't
        overlap with any surviving metric context in their plugin, making them
        unreferenceable in both log models (attributes-only) and metric models.

        Known orphans (14):
        - client.ip, client.type, event.name: login_history dim; log-context only
        - snowflake.grant.name, snowflake.share.name: shares dims
        - snowflake.task.is_internal, snowflake.task.name: tasks dims; credits.used deduped
        - snowflake.warehouse.event.name, snowflake.warehouse.event.state: warehouse_usage dims
        - observed_timestamp: structural OTel field (not custom attribute)
        - anomaly.detector, anomaly.direction, anomaly.subject: workflow metadata fields
          (renamed from ad.source/ad.direction/ad.category; emitted by Dynatrace workflows
          in events, not in metric/log models directly)
        - deployment.environment.name: OTel-stable co-emitted alias (otel-only), not yet
          referenced by any model during the deployment.environment migration window

        This test acts as a REGRESSION GUARD — fail if the count increases.
        """
        generated = _load_generated_yaml_files()

        signal_field_keys = _collect_all_signal_field_keys(generated)
        model_referenced_keys = _collect_all_model_referenced_fields(generated)

        orphans = signal_field_keys - model_referenced_keys

        # 14 known legitimate orphans (dimension-only or structural fields; see docstring above)
        max_allowed = 14
        assert len(orphans) <= max_allowed, (
            f"Found {len(orphans)} orphan signal fields (max allowed: {max_allowed}).\n"
            f"Orphans: {sorted(orphans)[:20]}{'...' if len(orphans) > 20 else ''}"
        )


##endregion

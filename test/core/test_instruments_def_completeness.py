"""Regression tests that validate instruments-def.yml source data quality.

Checks that required annotations (__type, __stability, __semdict_note, __enum, etc.)
are present and correct across all DSOA plugin instruments-def.yml files.

These tests are designed to be RED before Phase 2 fixes and GREEN after.

Note:
    All tests use ``@pytest.mark.integration`` because they read real
    ``instruments-def.yml`` files from the repository.
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

from typing import Any, Dict, List, Tuple

import pytest

from test.core._semdict_test_utils import load_all_instruments_defs

##region Fixtures

#: Fields with is_/has_/must_ prefix that SNOWFLAKE returns as YES/NO strings,
#: not as true/false booleans. These do NOT require __type: boolean.
_SNOWFLAKE_YESNO_STRINGS: frozenset = frozenset(
    {
        "snowflake.table.is_auto_clustering_on",
        "snowflake.table.is_dynamic",
        "snowflake.table.is_hybrid",
        "snowflake.table.is_iceberg",
        "snowflake.table.is_temporary",
        "snowflake.table.is_transient",
    }
)

#: Known boolean fields WITHOUT a conventional boolean prefix (is_/has_/must_).
#: These must still have __type: boolean.
_KNOWN_BOOLEAN_NO_PREFIX: frozenset = frozenset(
    {
        "snowflake.user.ext_authn.duo",
        "snowflake.grant.option",
        "plugins.query_history.track_ddl_changes",
    }
)

#: Timestamp fields that hold epoch nanosecond values — should be __type: long.
_EPOCH_NS_TIMESTAMP_FIELDS: frozenset = frozenset(
    {
        "snowflake.user.created_on",
        "snowflake.user.deleted_on",
        "snowflake.user.last_success_login",
        "snowflake.user.locked_until_time",
        "snowflake.user.expires_at",
        "snowflake.user.password_last_set_time",
        "snowflake.user.bypass_mfa_until",
        "snowflake.session.start",
    }
)

#: Timestamp fields that hold ISO-8601 string values — should have __type annotation.
_ISO8601_TIMESTAMP_FIELDS: frozenset = frozenset(
    {
        "snowflake.warehouse.created_on",
        "snowflake.warehouse.resumed_on",
        "snowflake.warehouse.updated_on",
        "snowflake.cost_attribution.period_start",
        "snowflake.cost_attribution.period_end",
        "snowflake.copy.first_commit_time",
        "snowflake.copy.pipe.received_time",
        "snowflake.grant.created_on",
        "snowflake.table.created_on",
        "snowflake.table.dynamic.graph.valid_from",
        "snowflake.table.dynamic.graph.valid_to",
        "snowflake.table.dynamic.latest.data_timestamp",
        "snowflake.table.dynamic.latest.dependency.data_timestamp",
        "snowflake.table.dynamic.refresh.start",
        "snowflake.table.dynamic.refresh.end",
        "snowflake.table.dynamic.refresh.data_timestamp",
        "snowflake.table.dynamic.refresh.completion_target",
        "snowflake.table.dynamic.scheduling.resumed_on",
        "snowflake.table.dynamic.scheduling.suspended_on",
    }
)

#: Numeric fields that must have __type: long annotation.
_REQUIRED_LONG_FIELDS: frozenset = frozenset(
    {
        "snowflake.query.hash_version",
        "snowflake.query.parametrized_hash_version",
        "snowflake.table.retention_time",
    }
)

#: OTel-only fields that require __semdict_note (provenance annotation).
_OTEL_ONLY_FIELDS_NEEDING_NOTE: frozenset = frozenset(
    {
        "db.namespace",
        "db.collection.name",
        "db.user",
    }
)

#: Fields that must appear in instruments-def.yml (discovered via code audit).
#: Tuple of (plugin_name, field_key).
_REQUIRED_EVENT_PAYLOAD_FIELDS: List[Tuple[str, str]] = [
    ("resource_monitors", "snowflake.warehouse.event"),
    ("login_history", "event.description"),
    ("login_history", "ad.source"),
]

#: Enum candidates: fields that must have __enum definitions.
_REQUIRED_ENUM_FIELDS: frozenset = frozenset(
    {
        "snowflake.copy.status",
        "snowflake.query.accel_est.status",
        "vulnerability.risk.level",
        "snowflake.table.dynamic.latest.state",
        "snowflake.table.dynamic.refresh.state",
        "snowflake.table.dynamic.refresh.action",
        "snowflake.table.dynamic.refresh.trigger",
        "snowflake.table.cold_status",
    }
)

##endregion


##region Helpers


def _load_all_instruments_defs() -> Dict[str, Dict[str, Any]]:
    """Thin wrapper around shared utility — loads all instruments-def.yml files.

    Returns:
        Dict mapping plugin name to parsed YAML data.
    """
    return load_all_instruments_defs()


def _collect_all_fields(all_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Collect all field entries across all sections and plugins.

    For duplicate keys (same field in multiple plugins), the first definition
    encountered is kept — this mirrors the export dedup behaviour.

    Args:
        all_defs: Parsed instruments-def data keyed by plugin name.

    Returns:
        Dict mapping field key to entry dict (including ``__plugin``, ``__section``).
    """
    all_fields: Dict[str, Dict[str, Any]] = {}
    for plugin_name, data in all_defs.items():
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, entry in (data.get(section) or {}).items():
                if key not in all_fields:
                    entry_copy = dict(entry or {})
                    entry_copy["__plugin"] = plugin_name
                    entry_copy["__section"] = section
                    all_fields[key] = entry_copy
    return all_fields


def _collect_fields_per_plugin(all_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Collect all fields keyed by plugin name then field key.

    Args:
        all_defs: Parsed instruments-def data keyed by plugin name.

    Returns:
        Nested dict: {plugin_name: {field_key: entry_dict}}.
    """
    result: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for plugin_name, data in all_defs.items():
        plugin_fields: Dict[str, Dict[str, Any]] = {}
        for section in ("attributes", "dimensions", "metrics", "event_timestamps"):
            for key, entry in (data.get(section) or {}).items():
                plugin_fields[key] = dict(entry or {})
        result[plugin_name] = plugin_fields
    return result


##endregion


##region Tests


@pytest.mark.integration
class TestBooleanTypeAnnotations:
    """Fields with boolean semantics must have __type: boolean."""

    def test_boolean_fields_with_is_has_must_prefix_have_type_annotation(self):
        """Fields with is_/has_/must_ prefix and true/false examples must have __type: boolean.

        Snowflake YES/NO string fields (in _SNOWFLAKE_YESNO_STRINGS) are exempt
        because Snowflake actually returns the string 'YES'/'NO', not true/false.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key, entry in all_fields.items():
            if key.startswith(("is_", "has_", "must_")):
                if key in _SNOWFLAKE_YESNO_STRINGS:
                    continue
                if entry.get("__type") != "boolean":
                    violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type: boolean")
        assert not violations, "Boolean fields missing __type: boolean:\n" + "\n".join(violations)

    def test_known_boolean_fields_without_prefix_have_type_annotation(self):
        """Known boolean fields without is_/has_/must_ prefix must have __type: boolean.

        Covers: snowflake.user.ext_authn.duo, snowflake.grant.option,
        plugins.query_history.track_ddl_changes.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _KNOWN_BOOLEAN_NO_PREFIX:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if entry.get("__type") != "boolean":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type: boolean")
        assert not violations, "Known boolean fields missing annotation:\n" + "\n".join(violations)


@pytest.mark.integration
class TestTimestampTypeAnnotations:
    """Timestamp fields must have explicit __type annotation."""

    def test_epoch_ns_timestamp_fields_have_long_type(self):
        """Epoch nanosecond timestamp fields must have __type: long.

        These are stored as long integers in Grail; the description must
        clarify their semantic meaning as timestamps.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _EPOCH_NS_TIMESTAMP_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                continue  # field may not be present in all repos
            if entry.get("__type") != "long":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: long, got {entry.get('__type')!r}")
        assert not violations, "Epoch-ns timestamp fields with wrong __type:\n" + "\n".join(violations)

    def test_iso8601_timestamp_fields_have_type_annotation(self):
        """ISO-8601 timestamp fields must have a __type annotation (not remain default string).

        These fields hold ISO-8601 datetime strings and should have __type: timestamp
        OR __type: long (if emitted as epoch-ns). Either annotation is acceptable
        as long as the type is not implicitly string (i.e. __type is not None/missing).
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _ISO8601_TIMESTAMP_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                continue  # field may not be in all repos
            raw_type = entry.get("__type")
            if raw_type is None:
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __type annotation (expected long or timestamp)")
        assert not violations, "Timestamp fields missing __type annotation:\n" + "\n".join(violations)


@pytest.mark.integration
class TestNumericTypeAnnotations:
    """Known numeric fields must have __type: long annotation."""

    def test_required_long_fields_have_long_type(self):
        """Fields in _REQUIRED_LONG_FIELDS must have __type: long.

        Covers: snowflake.query.hash_version, parametrized_hash_version,
        snowflake.table.retention_time.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_LONG_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if entry.get("__type") != "long":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __type: long, got {entry.get('__type')!r}")
        assert not violations, "Numeric fields missing __type: long:\n" + "\n".join(violations)


@pytest.mark.integration
class TestOtelStabilityAnnotations:
    """OTel-only fields must have __stability; deployment.environment must be deprecated."""

    def test_deployment_environment_marked_deprecated(self):
        """deployment.environment must have __stability: deprecated."""
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        entry = all_fields.get("deployment.environment")
        assert entry is not None, "deployment.environment not found in any instruments-def.yml"
        assert (
            entry.get("__stability") == "deprecated"
        ), f"deployment.environment must have __stability: deprecated, got {entry.get('__stability')!r}"

    def test_otel_only_fields_have_stability_annotation(self):
        """Every field with __semdict: otel-only must have __stability annotation.

        This ensures we accurately represent OTel stability levels in the SD export.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key, entry in all_fields.items():
            if entry.get("__semdict") == "otel-only":
                if not entry.get("__stability"):
                    violations.append(f"{key} (plugin={entry.get('__plugin')}): __semdict: otel-only but missing __stability")
        assert not violations, "OTel-only fields missing __stability:\n" + "\n".join(violations)


@pytest.mark.integration
class TestOtelProvenanceNotes:
    """OTel-only fields must have provenance notes (__semdict_note)."""

    def test_required_otel_fields_have_semdict_annotation(self):
        """Fields in _OTEL_ONLY_FIELDS_NEEDING_NOTE must have __semdict: otel-only.

        These fields are defined in OTel Semantic Conventions and should be
        annotated for proper SD provenance tracking.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _OTEL_ONLY_FIELDS_NEEDING_NOTE:
            entry = all_fields.get(key)
            if entry is None:
                continue
            if entry.get("__semdict") != "otel-only":
                violations.append(f"{key} (plugin={entry.get('__plugin')}): expected __semdict: otel-only, got {entry.get('__semdict')!r}")
        assert not violations, "OTel fields missing __semdict: otel-only:\n" + "\n".join(violations)

    def test_required_otel_fields_have_provenance_notes(self):
        """Fields db.namespace, db.collection.name, db.user must have __semdict_note.

        The note must explain OTel provenance so SD reviewers can decide
        whether to register the field globally.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _OTEL_ONLY_FIELDS_NEEDING_NOTE:
            entry = all_fields.get(key)
            if entry is None:
                continue
            if not entry.get("__semdict_note"):
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __semdict_note")
        assert not violations, "OTel fields missing __semdict_note:\n" + "\n".join(violations)


@pytest.mark.integration
class TestEventPayloadFieldsCoverage:
    """Event payload fields added programmatically must be in instruments-def.yml."""

    def test_event_payload_fields_documented(self):
        """Fields programmatically added to events by plugin code must appear in instruments-def.

        Discovered via code audit of _prepare_event_payload_* methods:
        - resource_monitors: snowflake.warehouse.event (key from _prepare_event_timestamps_payload_wh)
        - login_history: event.description (human-readable login event description)
        - login_history: ad.source (detection rule identifier; planned rename to rule.id)

        NOTE: 'timestamp' is intentionally excluded — it is a built-in platform attribute.
        """
        all_defs = _load_all_instruments_defs()
        per_plugin = _collect_fields_per_plugin(all_defs)

        violations = []
        for plugin_name, field_key in _REQUIRED_EVENT_PAYLOAD_FIELDS:
            plugin_fields = per_plugin.get(plugin_name, {})
            if field_key not in plugin_fields:
                violations.append(f"{field_key}: missing from {plugin_name}.config/instruments-def.yml")
        assert not violations, "Undocumented event payload fields:\n" + "\n".join(violations)


@pytest.mark.integration
class TestEnumDefinitions:
    """Known categorical fields must have __enum definitions."""

    def test_enum_candidate_fields_have_enum_definitions(self):
        """Fields with well-defined categorical value sets must have __enum.

        Covers: snowflake.copy.status, snowflake.query.accel_est.status,
        vulnerability.risk.level, snowflake.table.dynamic.*.state/action/trigger,
        snowflake.table.cold_status.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_ENUM_FIELDS:
            entry = all_fields.get(key)
            if entry is None:
                violations.append(f"{key}: field not found in any instruments-def.yml")
                continue
            if not entry.get("__enum"):
                violations.append(f"{key} (plugin={entry.get('__plugin')}): missing __enum definition")
        assert not violations, "Enum candidate fields missing __enum:\n" + "\n".join(violations)

    def test_enum_members_have_required_fields(self):
        """Every __enum definition must have members with id, value, brief.

        Validates that enum members follow the SD semconv structure.
        """
        all_defs = _load_all_instruments_defs()
        all_fields = _collect_all_fields(all_defs)

        violations = []
        for key in _REQUIRED_ENUM_FIELDS:
            entry = all_fields.get(key)
            if entry is None or not entry.get("__enum"):
                continue
            enum_def = entry["__enum"]
            members = enum_def.get("members", [])
            if not members:
                violations.append(f"{key}: __enum has no members")
                continue
            for i, m in enumerate(members):
                for required_field in ("id", "value", "brief"):
                    if not m.get(required_field):
                        violations.append(f"{key}[member {i}]: missing '{required_field}' field")
        assert not violations, "Enum members with missing fields:\n" + "\n".join(violations)


@pytest.mark.integration
class TestUnitBriefConsistency:
    """Metrics must have consistent unit and brief descriptions."""

    def test_scanned_from_cache_consistent_unit_and_brief(self):
        """snowflake.data.scanned_from_cache brief and unit must be consistent.

        The raw Snowflake value is a ratio (0.0-1.0). The unit must be 'ratio'
        (SD: '1') not 'percent'. The brief must not claim to multiply by 100.

        RATIONALE: PERCENTAGE_BYTES_SCANNED_FROM_LOCAL_CACHE in Snowflake
        returns a value 0.0-1.0 despite its 'PERCENTAGE' name. The existing
        brief contradicts the unit:percent setting.
        """
        all_defs = _load_all_instruments_defs()

        found = False
        for plugin_name, data in all_defs.items():
            metrics = data.get("metrics") or {}
            entry = metrics.get("snowflake.data.scanned_from_cache")
            if entry:
                found = True
                unit = entry.get("unit") or entry.get("__unit", "")
                description = entry.get("__description", "")

                # The unit must be ratio (SD '1') not 'percent'
                assert unit not in ("percent", "%"), (
                    f"snowflake.data.scanned_from_cache (plugin={plugin_name}): "
                    f"unit must be 'ratio' (SD: '1'), not {unit!r}. "
                    "Snowflake returns 0.0-1.0, not 0-100."
                )
                # The brief must not instruct to multiply by 100 (contradicts unit)
                assert "multiply by 100" not in description.lower(), (
                    f"snowflake.data.scanned_from_cache (plugin={plugin_name}): "
                    "brief says 'multiply by 100' but unit is already a ratio. Fix unit or brief."
                )
                break  # found the field; done
        assert found, "snowflake.data.scanned_from_cache not found in any metrics section"


##endregion
